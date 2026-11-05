"""会话内的 KK 节点连接与 Web 任务日志入口。"""

from contextlib import contextmanager
from datetime import datetime, timezone
import threading

from services.cluster_config import ClusterConfigError, ClusterConfigService
from services.ingestion import redact
from services.remote_diagnostics import RemoteDiagnosticError
from services.web_task_logs import WebTaskLogError, WebTaskLogs


class ClusterAccess:
    def __init__(self, remote, ttl_seconds=1800):
        self.remote = remote
        self.configs = ClusterConfigService(ttl_seconds)
        self._connections = {}
        self._selected = {}
        self._selected_logs = {}
        self._lock = threading.RLock()

    def _release(self, thread_id):
        with self._lock:
            connections = self._connections.pop(thread_id, {})
            self._selected.pop(thread_id, None)
            self._selected_logs.pop(thread_id, None)
        for item in connections.values():
            try:
                self.remote.revoke(item["connection_id"], thread_id)
            except RemoteDiagnosticError:
                pass

    def import_config(self, thread_id, yaml_text, host_key_sha256=None):
        """解析成功即保存配置；连接或日志失败不影响再次尝试。"""
        summary = self.configs.set(thread_id, yaml_text)
        self._release(thread_id)
        result = {"cluster": summary, "logs": {"items": [], "cluster_options": [], "selected_cluster": None}}
        try:
            connection = self.connect(thread_id, summary["master_name"], host_key_sha256)
            result["connection_id"] = connection["connection_id"]
            result["connection"] = connection
            result["logs"] = self.list_logs(thread_id)
        except (ClusterConfigError, RemoteDiagnosticError, WebTaskLogError) as exc:
            result["logs"]["error"] = str(exc)
        return result

    def get_config(self, thread_id):
        summary = self.configs.get(thread_id).public()
        with self._lock:
            summary["web_cluster_name"] = self._selected.get(thread_id)
            selected_log = self._selected_logs.get(thread_id)
            summary["selected_log"] = selected_log.copy() if selected_log is not None else None
        return summary

    def snapshot(self, thread_id):
        """恢复内存配置和节点连接；读取日志失败不影响配置摘要。"""
        config = self.configs.get(thread_id)
        with self._lock:
            existing = self._connections.get(thread_id, {}).get(config.master_name)
            connection = {key: value for key, value in existing.items() if key != "_fingerprint"} if existing else None
            selected = self._selected.get(thread_id)
        result = {"cluster": self.get_config(thread_id),
                  "logs": {"items": [], "cluster_options": [], "selected_cluster": selected}}
        if connection is None or datetime.fromisoformat(connection["expires_at"]).timestamp() <= datetime.now(timezone.utc).timestamp():
            result["logs"]["error"] = "第一个 master 的连接不可用，请重新粘贴配置。"
        else:
            result["node_name"] = config.master_name
            result["connection"] = {**connection, "node_name": config.master_name}
            result["connection_id"] = connection["connection_id"]
            try:
                result["logs"] = self.list_logs(thread_id)
            except (ClusterConfigError, RemoteDiagnosticError, WebTaskLogError) as exc:
                result["logs"]["error"] = str(exc)
            result["cluster"] = self.get_config(thread_id)
        with self._lock:
            selected_log = self._selected_logs.get(thread_id)
            if selected_log is not None:
                result["selected_log"] = selected_log.copy()
        return result

    def credential(self, thread_id, category, name):
        """仅按用户指定项返回临时保存在内存中的账号密码。"""
        config = self.configs.get(thread_id)
        if category == "node":
            item = config.nodes.get(name)
            if item is None:
                raise ClusterConfigError("该节点不在当前集群配置中。")
        elif category in {"component", "registry"}:
            choices = config.components if category == "component" else config.registries
            matches = [item for item in choices if item.name == name]
            if len(matches) != 1:
                raise ClusterConfigError("指定的账号不存在或存在重复项。")
            item = matches[0]
        else:
            raise ClusterConfigError("账号类型只能为 node、component 或 registry。")
        return {"username": item.username, "password": item.password}

    def connect(self, thread_id, node_name, host_key_sha256=None):
        config = self.configs.get(thread_id)
        node = config.nodes.get(node_name)
        if node is None:
            raise ClusterConfigError("该节点不在当前集群配置中。")
        if not (node.password or node.private_key):
            if node.private_key_path:
                raise ClusterConfigError("节点配置仅提供私钥路径，助手无法读取该路径，请提供密码或内联私钥。")
            raise ClusterConfigError("该节点没有配置 SSH 密码或内联私钥。")
        with self._lock:
            by_node = self._connections.setdefault(thread_id, {})
            cached = by_node.get(node_name)
            if cached:
                deadline = datetime.fromisoformat(cached["expires_at"]).timestamp()
                if deadline > datetime.now(timezone.utc).timestamp() and (
                    host_key_sha256 is None or host_key_sha256 == cached.get("_fingerprint")
                ):
                    return {key: value for key, value in cached.items() if key != "_fingerprint"}
                try:
                    self.remote.revoke(cached["connection_id"], thread_id)
                except RemoteDiagnosticError:
                    pass
            connection = self.remote.create_connection(
                thread_id, node.address, node.username, node.password, port=node.port,
                host_key_sha256=host_key_sha256, private_key=node.private_key,
            )
            by_node[node_name] = {**connection, "_fingerprint": host_key_sha256}
            return connection

    @contextmanager
    def _logs(self, thread_id):
        config = self.configs.get(thread_id)
        connection = self.connect(thread_id, config.master_name)
        client = self.remote.open_connection(connection["connection_id"], thread_id)
        try:
            yield WebTaskLogs(client, timeout=self.remote.command_timeout)
        finally:
            client.close()

    def _resolve(self, thread_id, logs):
        config = self.configs.get(thread_id)
        options = logs.list_clusters()
        with self._lock:
            previous = self._selected.get(thread_id)
            selected = previous
            if selected not in options:
                selected = config.cluster_name if config.cluster_name in options else (options[0] if len(options) == 1 else None)
                if selected is not None:
                    self._selected[thread_id] = selected
                else:
                    self._selected.pop(thread_id, None)
                if selected != previous:
                    self._selected_logs.pop(thread_id, None)
        return options, selected

    def list_logs(self, thread_id):
        with self._logs(thread_id) as logs:
            options, selected = self._resolve(thread_id, logs)
            result = {"items": [], "cluster_options": options, "selected_cluster": selected}
            if selected is None:
                result["error"] = "未找到 Web 集群目录。" if not options else "发现多个集群目录，请选择对应集群。"
            else:
                result["items"] = logs.list_logs(selected)
            return result

    def select_cluster(self, thread_id, cluster_name):
        with self._logs(thread_id) as logs:
            options = logs.list_clusters()
            if cluster_name not in options:
                raise WebTaskLogError("所选集群不在 Web 数据目录中。")
            with self._lock:
                if self._selected.get(thread_id) != cluster_name:
                    self._selected_logs.pop(thread_id, None)
                self._selected[thread_id] = cluster_name
            return {"items": logs.list_logs(cluster_name), "cluster_options": options,
                    "selected_cluster": cluster_name}

    def _selected_name(self, thread_id, logs):
        options, selected = self._resolve(thread_id, logs)
        if selected is None:
            if options:
                raise WebTaskLogError("发现多个集群目录，请先选择对应集群。")
            raise WebTaskLogError("未找到 Web 集群目录。")
        return selected

    def read_log(self, thread_id, scope, pid, offset=0):
        with self._logs(thread_id) as logs:
            return logs.read_log(self._selected_name(thread_id, logs), scope, pid, offset=offset)

    def select_log(self, thread_id, scope, pid):
        with self._logs(thread_id) as logs:
            cluster_name = self._selected_name(thread_id, logs)
            if not any(item["scope"] == scope and item["pid"] == pid for item in logs.list_logs(cluster_name)):
                raise WebTaskLogError("所选任务日志不存在。")
            with self._lock:
                self._selected_logs[thread_id] = {"scope": scope, "pid": pid}
        return {"scope": scope, "pid": pid}

    def evidence(self, thread_id, query):
        config = self.configs.get(thread_id)
        secrets = []
        for node in config.nodes.values():
            secrets.extend([node.password, node.private_key])
        secrets.extend(item.password for item in (*config.components, *config.registries))
        secrets = sorted({part for secret in secrets if secret for part in (secret, *secret.splitlines()) if part},
                         key=len, reverse=True)
        with self._logs(thread_id) as logs:
            cluster_name = self._selected_name(thread_id, logs)
            with self._lock:
                selected_log = self._selected_logs.get(thread_id)
            rows = logs.relevant_logs(cluster_name, query, secrets=secrets,
                                      **(selected_log or {}))
        def clean(value):
            if not isinstance(value, str):
                return value
            for secret in secrets:
                value = value.replace(secret, "[REDACTED]")
            return redact(value)
        return [{"source": "web_task_log", "scope": row["scope"], "pid": clean(row["pid"]),
                 "cluster_name": clean(row["cluster_name"]), "stdout": clean(row["matched_lines"]),
                 "stderr": "", "complete_scan": row["complete_scan"],
                 "snippet_only": row["snippet_only"]} for row in rows]

    def close(self):
        with self._lock:
            threads = tuple(self._connections)
        for thread_id in threads:
            self._release(thread_id)
        self.configs.close()
