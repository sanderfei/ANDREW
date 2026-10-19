"""受限的 SSH 只读取证；连接凭据仅保存在当前进程内存，不进入工作流状态。"""

from base64 import b64decode, b64encode
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import ipaddress
from pathlib import Path
import re
import secrets
import shlex
import socket
import threading
import time
from typing import Callable

from services.ingestion import redact


CHECK_CATALOG = {
    "host_summary": {"description": "主机系统、负载、根分区和内存概况", "parameters": {}},
    "cluster_nodes": {"description": "集群节点与版本状态", "parameters": {}},
    "pods": {"description": "Pod 状态", "parameters": {"namespace": "可选；省略时查询全部命名空间"}},
    "events": {"description": "按发生时间读取集群事件", "parameters": {"namespace": "可选；省略时查询全部命名空间"}},
    "pod_describe": {"description": "Pod 详细状态和事件", "parameters": {"pod": "必填", "namespace": "默认 default"}},
    "pod_logs": {"description": "读取有限数量的 Pod 日志", "parameters": {
        "pod": "必填", "namespace": "默认 default", "container": "可选", "tail_lines": "默认 200，范围 1..1000", "previous": "默认 false",
    }},
    "helm_status": {"description": "Helm Release 状态", "parameters": {"release": "必填", "namespace": "默认 default"}},
}


class RemoteDiagnosticError(RuntimeError):
    """可以安全返回给用户的远程诊断错误；不附带底层 SSH 异常内容。"""


@dataclass(slots=True, repr=False)
class _Connection:
    thread_id: str
    host: str
    username: str
    port: int
    expires_at: float
    deadline: float
    fingerprint: str | None
    _password: str = field(repr=False)
    timer: threading.Timer | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        return "<RemoteConnection credentials=hidden>"


class _HostKeyPolicy:
    def __init__(self, fingerprint: str | None):
        self.fingerprint = fingerprint

    def missing_host_key(self, client, hostname, key) -> None:
        if self.fingerprint is None:
            raise RemoteDiagnosticError("SSH 主机不在可信 known_hosts 中；请先核验主机或提供 SHA256 指纹。")
        actual = "SHA256:" + b64encode(sha256(key.asbytes()).digest()).decode().rstrip("=")
        if not hmac.compare_digest(actual, self.fingerprint):
            raise RemoteDiagnosticError("SSH 主机指纹不匹配，连接已拒绝。")


class RemoteDiagnosticsService:
    """一个服务实例管理本进程内的临时连接；connector 是零参数 SSHClient 工厂。"""

    def __init__(self, ttl_seconds=1800, command_timeout=20, max_output_chars=24000,
                 known_hosts_path=None, connector: Callable | None = None):
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)) or not 1 <= ttl_seconds <= 86400:
            raise ValueError("连接有效期必须为 1..86400 秒。")
        if isinstance(command_timeout, bool) or not isinstance(command_timeout, (int, float)) or not 0 < command_timeout <= 120:
            raise ValueError("诊断命令超时必须大于 0 且不超过 120 秒。")
        if isinstance(max_output_chars, bool) or not isinstance(max_output_chars, int) or not 256 <= max_output_chars <= 100000:
            raise ValueError("诊断输出上限必须为 256..100000 字符。")
        self.ttl_seconds = ttl_seconds
        self.command_timeout = command_timeout
        self.max_output_chars = max_output_chars
        self.known_hosts_path = Path(known_hosts_path).expanduser() if known_hosts_path else None
        self._connector = connector
        self._connections: dict[str, _Connection] = {}
        self._lock = threading.RLock()

    def create_connection(self, thread_id, host, username, password, port=22, host_key_sha256=None) -> dict:
        """登记临时连接；网络连接延迟到 collect，返回结果中不包含密码。"""
        self._validate_thread(thread_id)
        if not isinstance(host, str) or not host or len(host) > 253:
            raise RemoteDiagnosticError("SSH 主机地址格式不合法。")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", host) or ".." in host:
                raise RemoteDiagnosticError("SSH 主机地址格式不合法。")
        if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", username):
            raise RemoteDiagnosticError("SSH 用户名格式不合法。")
        if not isinstance(password, str) or not password or len(password) > 4096:
            raise RemoteDiagnosticError("请输入有效的 SSH 密码。")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise RemoteDiagnosticError("SSH 端口必须为 1..65535 的整数。")
        fingerprint = self._fingerprint(host_key_sha256)
        connection_id = secrets.token_urlsafe(32)
        entry = _Connection(thread_id, host, username, port, time.time() + self.ttl_seconds,
                            time.monotonic() + self.ttl_seconds, fingerprint, password)
        timer = threading.Timer(self.ttl_seconds, self._expire, args=(connection_id,))
        timer.daemon = True
        entry.timer = timer
        with self._lock:
            self._connections[connection_id] = entry
            timer.start()
        return {
            "connection_id": connection_id, "thread_id": thread_id, "host": host,
            "username": username, "port": port, "expires_at": self._iso(entry.expires_at),
        }

    def revoke(self, connection_id, thread_id) -> None:
        self._entry(connection_id, thread_id)
        self._expire(connection_id)

    def close(self) -> None:
        """清空临时凭据并取消到期计时器；允许重复关闭空实例。"""
        with self._lock:
            for connection_id in tuple(self._connections):
                self._expire(connection_id)

    def collect(self, connection_id, thread_id, checks: list[dict]) -> list[dict]:
        entry = self._entry(connection_id, thread_id)
        if not isinstance(checks, list) or not 1 <= len(checks) <= 10:
            raise RemoteDiagnosticError("每次需要提供 1..10 项诊断检查。")
        prepared = [self._prepare(check) for check in checks]
        client = None
        try:
            client = self._open(entry)
            results = []
            for check, command in prepared:
                self._entry(connection_id, thread_id)
                results.append(self._execute(client, entry, check, command))
            return results
        except RemoteDiagnosticError:
            raise
        except Exception:
            raise RemoteDiagnosticError("远程诊断失败，请检查连接、主机信任配置和远程工具权限。") from None
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    def _entry(self, connection_id, thread_id) -> _Connection:
        self._validate_thread(thread_id)
        if not isinstance(connection_id, str):
            raise RemoteDiagnosticError("远程连接不存在或已过期，请重新授权连接。")
        with self._lock:
            entry = self._connections.get(connection_id)
            if entry is None or not hmac.compare_digest(entry.thread_id, thread_id):
                raise RemoteDiagnosticError("远程连接不存在、已过期或不属于当前会话。")
            if time.monotonic() >= entry.deadline:
                self._expire(connection_id)
                raise RemoteDiagnosticError("远程连接已过期，请重新授权连接。")
            return entry

    def _expire(self, connection_id) -> None:
        with self._lock:
            entry = self._connections.pop(connection_id, None)
            if entry is not None:
                entry._password = ""
                if entry.timer is not None:
                    entry.timer.cancel()

    @staticmethod
    def _validate_thread(thread_id) -> None:
        if not isinstance(thread_id, str) or not 1 <= len(thread_id) <= 200 or any(ord(char) < 32 for char in thread_id):
            raise RemoteDiagnosticError("会话标识格式不合法。")

    @staticmethod
    def _fingerprint(value) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.startswith("SHA256:"):
            raise RemoteDiagnosticError("主机指纹必须使用 SHA256: 格式。")
        encoded = value[7:].rstrip("=")
        try:
            raw = b64decode(encoded + "=" * (-len(encoded) % 4), validate=True)
        except (ValueError, TypeError):
            raise RemoteDiagnosticError("主机 SHA256 指纹格式不合法。") from None
        if len(raw) != 32 or b64encode(raw).decode().rstrip("=") != encoded:
            raise RemoteDiagnosticError("主机 SHA256 指纹格式不合法。")
        return "SHA256:" + encoded

    def _open(self, entry):
        if self._connector is None:
            try:
                from paramiko import SSHClient
            except ImportError:
                raise RemoteDiagnosticError("远程诊断需要安装 paramiko，请先安装项目依赖。") from None
            client = SSHClient()
        else:
            client = self._connector()
        try:
            if entry.fingerprint is None:
                client.load_system_host_keys()
                if self.known_hosts_path is not None:
                    client.load_host_keys(str(self.known_hosts_path))
            client.set_missing_host_key_policy(_HostKeyPolicy(entry.fingerprint))
            client.connect(hostname=entry.host, port=entry.port, username=entry.username,
                           password=entry._password, timeout=self.command_timeout,
                           auth_timeout=self.command_timeout, banner_timeout=self.command_timeout,
                           look_for_keys=False, allow_agent=False)
            if entry.fingerprint is not None:
                key = client.get_transport().get_remote_server_key()
                _HostKeyPolicy(entry.fingerprint).missing_host_key(client, entry.host, key)
            return client
        except Exception:
            client.close()
            raise

    @staticmethod
    def _name(value, field_name, maximum=253):
        label = r"[a-z0-9](?:[-a-z0-9]*[a-z0-9])?"
        pattern = label + r"(?:\." + label + r")*" if field_name == "pod" else label
        if not isinstance(value, str) or len(value) > maximum or not re.fullmatch(pattern, value):
            raise RemoteDiagnosticError(f"诊断参数 {field_name} 不是合法的资源名称。")
        return value

    def _prepare(self, check):
        if not isinstance(check, dict) or set(check) - {"name", "parameters"}:
            raise RemoteDiagnosticError("诊断检查仅支持 name 和 parameters 字段。")
        name = check.get("name")
        if not isinstance(name, str) or name not in CHECK_CATALOG:
            raise RemoteDiagnosticError("不支持该诊断检查；不能执行任意 Shell 命令。")
        parameters = check.get("parameters", {})
        if not isinstance(parameters, dict) or set(parameters) - set(CHECK_CATALOG[name]["parameters"]):
            raise RemoteDiagnosticError("诊断检查包含不支持的参数。")
        if name == "host_summary":
            return {"name": name, "parameters": {}}, "uname -a; cat /etc/os-release; uptime; df -h /; free -m"
        parts = ["kubectl", "--request-timeout=15s"]
        normalized = {}
        if name == "cluster_nodes":
            parts += ["get", "nodes", "-o", "wide"]
        else:
            namespace = parameters.get("namespace")
            if name not in {"pods", "events"}:
                namespace = "default" if namespace is None else namespace
            if namespace is not None:
                namespace = self._name(namespace, "namespace", 63)
                normalized["namespace"] = namespace
            if name in {"pods", "events"}:
                parts += ["get", name]
                parts += ["--namespace", namespace] if namespace else ["--all-namespaces"]
                parts += ["-o", "wide"] if name == "pods" else ["--sort-by=.metadata.creationTimestamp"]
            elif name in {"pod_describe", "pod_logs"}:
                pod = self._name(parameters.get("pod"), "pod")
                normalized["pod"] = pod
                if name == "pod_describe":
                    parts += ["describe", "pod", pod, "--namespace", namespace]
                else:
                    tail = parameters.get("tail_lines", 200)
                    previous = parameters.get("previous", False)
                    if isinstance(tail, bool) or not isinstance(tail, int) or not 1 <= tail <= 1000:
                        raise RemoteDiagnosticError("tail_lines 必须为 1..1000 的整数。")
                    if not isinstance(previous, bool):
                        raise RemoteDiagnosticError("previous 必须是布尔值。")
                    normalized.update(tail_lines=tail, previous=previous)
                    parts += ["logs", pod, "--namespace", namespace, f"--tail={tail}", "--timestamps=true"]
                    if parameters.get("container") is not None:
                        container = self._name(parameters["container"], "container", 63)
                        normalized["container"] = container
                        parts += ["--container", container]
                    if previous:
                        parts.append("--previous")
            elif name == "helm_status":
                release = self._name(parameters.get("release"), "release", 53)
                normalized["release"] = release
                parts = ["helm", "status", release, "--namespace", namespace]
        return {"name": name, "parameters": normalized}, shlex.join(parts)

    def _execute(self, client, entry, check, command):
        channel = None
        deadline = time.monotonic() + self.command_timeout
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=self.command_timeout, get_pty=False)
            stdin.close()
            channel = stdout.channel
            channel.settimeout(self.command_timeout)
            budget = self.max_output_chars * 4
            output = [bytearray(), bytearray()]
            retained = 0
            truncated = False
            while True:
                if time.monotonic() >= entry.deadline or not entry._password:
                    raise RemoteDiagnosticError("远程连接已过期或被撤销；本次检查已停止。")
                if time.monotonic() >= deadline:
                    raise RemoteDiagnosticError("远程诊断命令执行超时；本次检查已停止。")
                for stream, ready, receive in (
                    (0, channel.recv_ready, channel.recv),
                    (1, channel.recv_stderr_ready, channel.recv_stderr),
                ):
                    if ready():
                        data = receive(32768)
                        available = max(0, budget - retained)
                        output[stream].extend(data[:available])
                        retained += min(len(data), available)
                        truncated = truncated or len(data) > available
                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    break
                time.sleep(0.01)
            exit_code = channel.recv_exit_status()
            decoded = []
            remaining = self.max_output_chars
            # 与撤销/到期清理互斥，避免密码先被清空而漏掉输出中的密码替换。
            with self._lock:
                if time.monotonic() >= entry.deadline or not entry._password:
                    raise RemoteDiagnosticError("远程连接已过期或被撤销；本次检查已停止。")
                for value in output:
                    text = value.decode("utf-8", errors="replace").replace(entry._password, "[REDACTED]")
                    text = redact(text)
                    truncated = truncated or len(text) > remaining
                    decoded.append(text[:remaining])
                    remaining -= len(decoded[-1])
            return {"check": check, "command": command, "exit_code": exit_code,
                    "stdout": decoded[0], "stderr": decoded[1], "truncated": truncated,
                    "collected_at": self._iso(time.time())}
        except (TimeoutError, socket.timeout):
            raise RemoteDiagnosticError("远程诊断命令执行超时；本次检查已停止。") from None
        finally:
            if channel is not None:
                channel.close()

    @staticmethod
    def _iso(timestamp):
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
