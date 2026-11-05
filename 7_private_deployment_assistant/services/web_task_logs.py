"""只读访问 Web 容器数据挂载中的完整任务日志。"""

import codecs
from collections import deque
import errno
import json
import posixpath
import re
import stat

from services.ingestion import redact


class WebTaskLogError(RuntimeError):
    """可返回客户端的日志读取错误，不包含 SSH 的原始错误信息。"""


def _segment(value, label):
    if (not isinstance(value, str) or not value or len(value.encode("utf-8")) > 255
            or value in {".", ".."} or "/" in value or "\\" in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise WebTaskLogError(f"{label}格式不合法。")
    return value


class WebTaskLogs:
    """client 为已连接的 Paramiko SSHClient；其生命周期由调用方管理。"""

    def __init__(self, client, timeout=20):
        self.client = client
        self.timeout = timeout
        self._root = None

    def _data_root(self):
        if self._root is not None:
            return self._root
        command = "nerdctl -n k8s.io inspect --format '{{json .Mounts}}' g_web_installer"
        output = None
        for candidate in (command, "sudo -n " + command):
            try:
                stdin, stdout, stderr = self.client.exec_command(candidate, timeout=self.timeout, get_pty=False)
                stdin.close()
                raw = stdout.read(65537)
                code = stdout.channel.recv_exit_status()
                stderr.close()
                stdout.close()
            except Exception:
                continue
            if code == 0 and len(raw) <= 65536:
                output = raw
                break
        if output is None:
            raise WebTaskLogError("无法读取 Web 容器挂载，请检查 g_web_installer、nerdctl 和当前账号权限。")
        try:
            mounts = json.loads(output)
            matches = [item.get("Source") for item in mounts
                       if isinstance(item, dict) and item.get("Destination") == "/g_web_installer/data"]
            if len(matches) != 1 or not isinstance(matches[0], str) or not matches[0].startswith("/"):
                raise ValueError()
            with self.client.open_sftp() as sftp:
                root = sftp.normalize(matches[0])
                if not root.startswith("/") or not stat.S_ISDIR(sftp.lstat(root).st_mode):
                    raise ValueError()
        except Exception:
            raise WebTaskLogError("未找到可读取的 Web 数据挂载目录。") from None
        self._root = root
        return root

    @staticmethod
    def _directory(sftp, root, parts, missing_ok=False):
        path = root
        for part in parts:
            path = posixpath.join(path, part)
            try:
                attrs = sftp.lstat(path)
            except OSError as exc:
                if missing_ok and exc.errno == errno.ENOENT:
                    return None
                raise
            if not stat.S_ISDIR(attrs.st_mode):
                raise WebTaskLogError("日志目录不是普通目录，无法读取。")
        return path

    @staticmethod
    def _parts(cluster_name, scope):
        if scope == "cluster":
            return ["cluster", _segment(cluster_name, "集群名称"), "history"]
        if scope == "obs":
            return ["obs", "history"]
        raise WebTaskLogError("日志范围只能是 cluster 或 obs。")

    def list_clusters(self):
        """读取 Web 实际保存的集群目录，避免假定 YAML metadata.name 即目录名。"""
        root = self._data_root()
        try:
            with self.client.open_sftp() as sftp:
                directory = self._directory(sftp, root, ["cluster"], missing_ok=True)
                if directory is None:
                    return []
                clusters = []
                for entry in sftp.listdir_attr(directory):
                    if stat.S_ISDIR(entry.st_mode):
                        try:
                            clusters.append(_segment(entry.filename, "集群名称"))
                        except WebTaskLogError:
                            continue
                return sorted(clusters)
        except WebTaskLogError:
            raise
        except Exception:
            raise WebTaskLogError("读取 Web 集群目录失败，请检查目录和账号权限。") from None

    def list_logs(self, cluster_name):
        """返回该集群任务及全局 OBS 任务列表；OBS 不默认属于该集群。"""
        _segment(cluster_name, "集群名称")
        root = self._data_root()
        items = []
        try:
            with self.client.open_sftp() as sftp:
                for scope in ("cluster", "obs"):
                    history = self._directory(sftp, root, self._parts(cluster_name, scope), missing_ok=True)
                    if history is None:
                        continue
                    for entry in sftp.listdir_attr(history):
                        if not stat.S_ISDIR(entry.st_mode):
                            continue
                        try:
                            pid = _segment(entry.filename, "任务 ID")
                        except WebTaskLogError:
                            continue
                        path = posixpath.join(history, pid, "execute.log")
                        try:
                            log = sftp.lstat(path)
                        except OSError as exc:
                            if exc.errno == errno.ENOENT:
                                continue
                            raise
                        if stat.S_ISREG(log.st_mode):
                            items.append({"scope": scope, "pid": pid, "size": log.st_size,
                                          "modified_at": log.st_mtime,
                                          "cluster_name": cluster_name if scope == "cluster" else None})
        except WebTaskLogError:
            raise
        except Exception:
            raise WebTaskLogError("读取 Web 任务日志目录失败，请检查目录和账号权限。") from None
        return sorted(items, key=lambda item: (item["modified_at"], item["pid"]), reverse=True)

    def _log_path(self, sftp, root, cluster_name, scope, pid):
        parts = [*self._parts(cluster_name, scope), _segment(pid, "任务 ID")]
        directory = self._directory(sftp, root, parts)
        path = posixpath.join(directory, "execute.log")
        if not stat.S_ISREG(sftp.lstat(path).st_mode):
            raise WebTaskLogError("任务日志不是普通文件。")
        return path

    def read_log(self, cluster_name, scope, pid, offset=0, limit=65536):
        """按字节分页，next_offset 可连续读取完整 UTF-8 日志。"""
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 4 <= limit <= 262144:
            raise WebTaskLogError("日志偏移量或分页大小不合法。")
        root = self._data_root()
        try:
            with self.client.open_sftp() as sftp:
                path = self._log_path(sftp, root, cluster_name, scope, pid)
                with sftp.open(path, "rb") as file:
                    size = file.stat().st_size
                    if offset > size:
                        raise WebTaskLogError("日志偏移量超过文件大小，请从头读取。")
                    file.seek(offset)
                    raw = file.read(limit)
                decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
                eof = offset + len(raw) >= size
                text = decoder.decode(raw, final=eof)
                pending = decoder.getstate()[0]
                next_offset = offset + len(raw) - len(pending)
                return {"scope": scope, "pid": pid, "content": text, "offset": offset,
                        "next_offset": next_offset, "size": size, "eof": eof}
        except WebTaskLogError:
            raise
        except Exception:
            raise WebTaskLogError("读取任务日志失败，请检查日志是否存在及账号权限。") from None

    def relevant_logs(self, cluster_name, query, *, scope=None, pid=None, secrets=(), max_chars=6000):
        """从选定任务或最近相关任务完整扫描错误行；结果脱敏后供模型使用。"""
        if not isinstance(query, str) or len(query) > 12000:
            raise WebTaskLogError("问题格式不合法。")
        if type(max_chars) is not int or not 256 <= max_chars <= 24000:
            raise WebTaskLogError("日志摘要大小不合法。")
        if (scope is None) != (pid is None):
            raise WebTaskLogError("scope 和 pid 必须同时指定。")
        items = self.list_logs(cluster_name)
        if scope is not None:
            items = [item for item in items if item["scope"] == scope and item["pid"] == pid]
            if not items:
                raise WebTaskLogError("未找到指定任务日志。")
        else:
            # 全局 OBS 日志不属于某个集群，只有问题涉及 OBS 时才自动纳入。
            terms = re.findall(r"[a-z0-9_-]{3,}", query.lower())
            for chinese, english in (("备份", "backup"), ("恢复", "restore"), ("导入", "import"),
                                     ("安装", "install"), ("扩容", "add"), ("删除节点", "remove")):
                if chinese in query:
                    terms.append(english)
            obs = "obs" in query.lower()
            items = [item for item in items if item["scope"] == "cluster" or obs]
            items.sort(key=lambda item: (any(term in item["pid"].lower() for term in terms), item["modified_at"]), reverse=True)
            items = items[:3]
        root = self._data_root()
        pattern = re.compile(r"error|failed|failure|fatal|exception|timeout|denied|失败|错误|异常|超时", re.I)
        words = [word for word in re.findall(r"[a-z0-9_.:/-]{4,}", query.lower()) if len(word) <= 100][:12]
        secret_parts = [part for secret in secrets if isinstance(secret, str)
                        for part in secret.splitlines() if part]
        evidence = []
        try:
            with self.client.open_sftp() as sftp:
                for item in items:
                    path = self._log_path(sftp, root, cluster_name, item["scope"], item["pid"])
                    lines = deque(maxlen=100)
                    before = deque(maxlen=3)
                    after = 0
                    last_added = 0
                    private_key = False
                    with sftp.open(path, "rb") as file:
                        for number, raw in enumerate(file, 1):
                            line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
                            if re.search(r"-----BEGIN [^-]*PRIVATE KEY-----", line):
                                private_key = not bool(re.search(r"-----END [^-]*PRIVATE KEY-----", line))
                                line = "[REDACTED_PRIVATE_KEY]"
                            elif private_key:
                                if re.search(r"-----END [^-]*PRIVATE KEY-----", line):
                                    private_key = False
                                continue
                            for secret in secret_parts:
                                line = line.replace(secret, "[REDACTED]")
                            line = redact(line.rstrip())[:2000]
                            matches = pattern.search(line) or any(word in line.lower() for word in words)
                            if matches:
                                for previous_number, previous in before:
                                    if previous_number > last_added:
                                        lines.append(f"{previous_number}: {previous}")
                                after = 3
                            if matches or after:
                                lines.append(f"{number}: {line}")
                                last_added = number
                                if not matches:
                                    after -= 1
                            before.append((number, line))
                    text = "\n".join(lines)[-max_chars:]
                    evidence.append({"scope": item["scope"], "pid": item["pid"],
                                     "cluster_name": item["cluster_name"], "matched_lines": text,
                                     "complete_scan": True, "snippet_only": True})
        except WebTaskLogError:
            raise
        except Exception:
            raise WebTaskLogError("提取任务日志线索失败，请检查日志读取权限。") from None
        return evidence
