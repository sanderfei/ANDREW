"""解析用户提供的 KK 配置，并在本进程短暂保留节点连接资料。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import time
from uuid import uuid4

import yaml


class ClusterConfigError(ValueError):
    """可以直接返回给用户的配置错误；不包含原始配置内容。"""


def _mapping(value, name):
    if not isinstance(value, dict):
        raise ClusterConfigError(f"{name} 必须是配置对象。")
    return value


def _string(value, name, *, default=""):
    if value is None:
        return default
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ClusterConfigError(f"{name} 必须是字符串。")
    return str(value).strip()


def _secret(value, name):
    if value is None:
        return ""
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ClusterConfigError(f"{name} 必须是字符串。")
    return str(value)


@dataclass(repr=False)
class ClusterNode:
    name: str
    address: str
    internal_address: str
    port: int
    username: str
    roles: list[str]
    password: str = field(default="", repr=False)
    private_key: str = field(default="", repr=False)
    private_key_path: str = field(default="", repr=False)

    def public(self):
        return {
            "name": self.name, "address": self.address, "internal_address": self.internal_address,
            "port": self.port, "username": self.username, "roles": self.roles.copy(),
            "has_password": bool(self.password), "has_private_key": bool(self.private_key),
            "private_key_path": self.private_key_path,
        }


@dataclass(repr=False)
class ClusterCredential:
    name: str
    username: str
    password: str = field(default="", repr=False)

    def public(self):
        return {"name": self.name, "username": self.username, "has_password": bool(self.password)}


@dataclass(repr=False)
class ClusterConfig:
    generation: str
    cluster_name: str
    kubernetes_version: str
    container_manager: str
    install_mode: str
    control_plane_endpoint: dict
    network: dict
    registry: dict
    nodes: dict[str, ClusterNode]
    master_name: str
    components: list[ClusterCredential]
    registries: list[ClusterCredential]
    expires_at: float
    deadline: float

    @property
    def master(self) -> ClusterNode:
        return self.nodes[self.master_name]

    def public(self):
        return {
            "generation": self.generation, "cluster_name": self.cluster_name, "kubernetes_version": self.kubernetes_version,
            "container_manager": self.container_manager, "install_mode": self.install_mode,
            "control_plane_endpoint": self.control_plane_endpoint.copy(), "network": self.network.copy(),
            "registry": self.registry.copy(), "nodes": [node.public() for node in self.nodes.values()],
            "master_name": self.master_name, "components": [item.public() for item in self.components],
            "registries": [{"address": item.name, "username": item.username,
                            "has_password": bool(item.password)} for item in self.registries],
            "expires_at": datetime.fromtimestamp(self.expires_at, timezone.utc).isoformat(),
        }

    def clear_secrets(self):
        for node in self.nodes.values():
            node.password = ""
            node.private_key = ""
        for credential in (*self.components, *self.registries):
            credential.password = ""


def parse_cluster_config(yaml_text: str, *, ttl_seconds: float = 1800) -> ClusterConfig:
    """只提取所需字段，不保留原始 YAML。"""
    if not isinstance(yaml_text, str) or not yaml_text.strip() or len(yaml_text) > 1_000_000:
        raise ClusterConfigError("请粘贴不超过 100 万字符的 KK 配置。")
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        raise ClusterConfigError("配置不是有效的 YAML，请检查格式。") from None
    root = _mapping(data, "配置")
    spec = _mapping(root.get("spec"), "spec")
    metadata = _mapping(root.get("metadata") or {}, "metadata")
    system = _mapping(spec.get("system") or {}, "spec.system")
    kubernetes = _mapping(spec.get("kubernetes") or {}, "spec.kubernetes")
    registry = _mapping(spec.get("registry") or {}, "spec.registry")
    endpoint = _mapping(spec.get("controlPlaneEndpoint") or {}, "spec.controlPlaneEndpoint")
    network = _mapping(spec.get("network") or {}, "spec.network")
    groups = _mapping(spec.get("roleGroups"), "spec.roleGroups")
    hosts = spec.get("hosts")
    if not isinstance(hosts, list) or not hosts:
        raise ClusterConfigError("配置中没有 spec.hosts 节点。")
    masters = groups.get("control-plane")
    if not isinstance(masters, list) or not masters:
        raise ClusterConfigError("配置中没有 control-plane 节点。")
    groups = {role: [] if names is None else names for role, names in groups.items()}
    for role, names in groups.items():
        if not isinstance(role, str) or not isinstance(names, list) or any(not isinstance(name, str) for name in names):
            raise ClusterConfigError("spec.roleGroups 的角色必须对应节点名称列表。")
    nodes = {}
    for raw_node in hosts:
        raw_node = _mapping(raw_node, "节点")
        name = _string(raw_node.get("name"), "节点名称")
        address = _string(raw_node.get("address"), "节点地址")
        if not name or not address:
            raise ClusterConfigError("每个节点都需要 name 和 address。")
        if name in nodes:
            raise ClusterConfigError("节点名称不能重复。")
        raw_port = raw_node.get("port") or 22
        try:
            port = int(raw_port)
        except (TypeError, ValueError, OverflowError):
            raise ClusterConfigError("节点 SSH 端口必须为 1 到 65535 的整数。") from None
        if isinstance(raw_port, bool) or str(raw_port).strip() != str(port) or not 1 <= port <= 65535:
            raise ClusterConfigError("节点 SSH 端口必须为 1 到 65535 的整数。")
        nodes[name] = ClusterNode(
            name=name, address=address,
            internal_address=_string(raw_node.get("internalAddress"), "节点内网地址"), port=port,
            username=_string(raw_node.get("user"), "节点用户") or "root",
            roles=[role for role, names in groups.items() if name in names],
            password=_secret(raw_node.get("password"), "节点密码"),
            private_key=_secret(raw_node.get("privateKey"), "节点私钥"),
            private_key_path=_string(raw_node.get("privateKeyPath"), "节点私钥路径"),
        )
    master_name = masters[0]
    if master_name not in nodes:
        raise ClusterConfigError("第一个 control-plane 节点未在 spec.hosts 中找到。")
    raw_components = system.get("components") or []
    if not isinstance(raw_components, list):
        raise ClusterConfigError("spec.system.components 必须是列表。")
    components = []
    for raw in raw_components:
        raw = _mapping(raw, "组件")
        components.append(ClusterCredential(_string(raw.get("name"), "组件名称"),
            _string(raw.get("username"), "组件用户"), _secret(raw.get("password"), "组件密码")))
    auths = _mapping(registry.get("auths") or {}, "spec.registry.auths")
    registries = []
    for address, raw in auths.items():
        raw = _mapping(raw or {}, "镜像仓库认证")
        registries.append(ClusterCredential(_string(address, "镜像仓库地址"),
            _string(raw.get("username"), "镜像仓库用户"), _secret(raw.get("password"), "镜像仓库密码")))
    return ClusterConfig(
        generation=uuid4().hex,
        cluster_name=_string(metadata.get("name"), "集群名称"),
        kubernetes_version=_string(kubernetes.get("version"), "Kubernetes 版本").removeprefix("v"),
        container_manager=_string(kubernetes.get("containerManager"), "容器运行时"),
        install_mode=_string(system.get("install"), "安装方式"), nodes=nodes, master_name=master_name,
        control_plane_endpoint={"domain": _string(endpoint.get("domain"), "控制面域名"),
                                "address": _string(endpoint.get("address"), "控制面地址"),
                                "port": _string(endpoint.get("port"), "控制面端口")},
        network={"plugin": _string(network.get("plugin"), "网络插件"),
                 "kube_pods_cidr": _string(network.get("kubePodsCIDR"), "Pod 网段"),
                 "kube_service_cidr": _string(network.get("kubeServiceCIDR"), "Service 网段")},
        registry={"type": _string(registry.get("type"), "仓库类型"),
                  "private_registry": _string(registry.get("privateRegistry"), "仓库地址")},
        components=components, registries=registries, expires_at=time.time() + ttl_seconds,
        deadline=time.monotonic() + ttl_seconds,
    )


class ClusterConfigService:
    """每个会话只保留一份配置，过期或关闭时清理连接凭据。"""

    def __init__(self, ttl_seconds=1800):
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)) or not 1 <= ttl_seconds <= 86400:
            raise ValueError("配置有效期必须为 1 到 86400 秒。")
        self.ttl_seconds = ttl_seconds
        self._configs = {}
        self._timers = {}
        self._lock = threading.RLock()

    def set(self, thread_id: str, yaml_text: str) -> dict:
        if not isinstance(thread_id, str) or not 1 <= len(thread_id) <= 128 or any(ord(c) < 32 for c in thread_id):
            raise ClusterConfigError("会话标识格式不合法。")
        config = parse_cluster_config(yaml_text, ttl_seconds=self.ttl_seconds)
        with self._lock:
            self.revoke(thread_id)
            self._configs[thread_id] = config
            timer = threading.Timer(self.ttl_seconds, self._expire, args=(thread_id, config))
            timer.daemon = True
            self._timers[thread_id] = timer
            timer.start()
        return config.public()

    def get(self, thread_id: str) -> ClusterConfig:
        with self._lock:
            config = self._configs.get(thread_id)
            if config is None:
                raise ClusterConfigError("集群配置不存在或已过期，请重新粘贴配置。")
            if time.monotonic() >= config.deadline:
                self.revoke(thread_id)
                raise ClusterConfigError("集群配置已过期，请重新粘贴配置。")
            return config

    def _expire(self, thread_id, config):
        with self._lock:
            if self._configs.get(thread_id) is config:
                self.revoke(thread_id)

    def revoke(self, thread_id: str):
        with self._lock:
            config = self._configs.pop(thread_id, None)
            timer = self._timers.pop(thread_id, None)
            if timer is not None:
                timer.cancel()
            if config is not None:
                config.clear_secrets()

    def close(self):
        with self._lock:
            for thread_id in tuple(self._configs):
                self.revoke(thread_id)
