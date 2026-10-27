"""读取向量库和助手配置；数据库密码与模型密钥只从环境读取。"""

import math
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values


PROJECT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    static_dir: Path = PROJECT_DIR / "static"
    document_dir: Path = PROJECT_DIR / "documents" / "source"
    support_matrix: dict[str, list[str]] = field(
        default_factory=lambda: {
            "1.23.10": ["Ubuntu", "CentOS"],
            "1.32.8": ["Ubuntu"],
        }
    )


@dataclass(frozen=True)
class VectorSettings:
    backend: str
    namespace: str
    dimension: int
    model: str
    model_path: Path
    cache_dir: Path
    qdrant_url: str
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str = field(repr=False)
    chunk_size: int = 800
    chunk_overlap: int = 120
    allowed_roots: tuple[Path, ...] = (PROJECT_DIR / "documents" / "source",)


@dataclass(frozen=True)
class AssistantSettings:
    mode: str = "framework"
    model: str = "glm-4-flash"
    base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    api_key: str = field(default="", repr=False)
    temperature: float = 0.1
    timeout: float = 60.0
    max_retries: int = 1
    top_k: int = 5
    max_remote_rounds: int = 2


@dataclass(frozen=True)
class BusinessSettings:
    runtime_dir: Path = PROJECT_DIR / "runtime"
    source_dir: Path = PROJECT_DIR / "documents" / "source"
    auto_index: bool = True
    index_interval: float = 15.0
    connection_ttl: int = 1800
    command_timeout: int = 20
    max_output_chars: int = 24000
    known_hosts_path: str | None = None
    langfuse_enabled: bool = False
    langfuse_base_url: str = "http://127.0.0.1:3000"
    langfuse_public_key: str = field(default="", repr=False)
    langfuse_secret_key: str = field(default="", repr=False)


def load_business_settings(config_path: Path | None = None) -> BusinessSettings:
    path = Path(config_path) if config_path else PROJECT_DIR / "config.toml"
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    business = config.get("business", {})
    telemetry = config.get("langfuse", {})
    environment = {**dotenv_values(PROJECT_DIR.parent / ".env"),
                   **dotenv_values(PROJECT_DIR / "runtime" / "local.env"), **os.environ}
    settings = BusinessSettings(
        runtime_dir=(PROJECT_DIR / Path(business.get("runtime_dir", "runtime")).expanduser()).resolve(),
        source_dir=Settings().document_dir.resolve(),
        auto_index=business.get("auto_index", True),
        index_interval=float(business.get("index_interval", 15)),
        connection_ttl=int(business.get("connection_ttl", 1800)),
        command_timeout=int(business.get("command_timeout", 20)),
        max_output_chars=int(business.get("max_output_chars", 24000)),
        known_hosts_path=business.get("known_hosts_path"),
        langfuse_enabled=telemetry.get("enabled", False),
        langfuse_base_url=environment.get("LANGFUSE_BASE_URL") or telemetry.get("base_url", "http://127.0.0.1:3000"),
        langfuse_public_key=environment.get("LANGFUSE_PUBLIC_KEY") or "",
        langfuse_secret_key=environment.get("LANGFUSE_SECRET_KEY") or "",
    )
    if type(settings.auto_index) is not bool or type(settings.langfuse_enabled) is not bool:
        raise ValueError("auto_index 和 langfuse.enabled 必须为布尔值。")
    if not math.isfinite(settings.index_interval) or settings.index_interval < 1:
        raise ValueError("index_interval 必须至少为 1 秒。")
    if not 1 <= settings.connection_ttl <= 86400 or not 1 <= settings.command_timeout <= 120:
        raise ValueError("连接有效期或命令超时超出允许范围。")
    if not 1024 <= settings.max_output_chars <= 100000:
        raise ValueError("诊断输出上限必须为 1024～100000 字符。")
    return settings


def load_assistant_settings(config_path: Path | None = None) -> AssistantSettings:
    """默认只运行框架；密钥不会写入 TOML，也不会出现在配置对象 repr 中。"""
    path = Path(config_path) if config_path is not None else PROJECT_DIR / "config.toml"
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    assistant = config.get("assistant", {})
    if not isinstance(assistant, dict):
        raise ValueError("assistant 必须为 TOML 配置节。")
    # 不修改进程环境；同名变量优先级为进程 > 教程 7 本地环境 > 仓库环境。
    environment = {
        **dotenv_values(PROJECT_DIR.parent / ".env"),
        **dotenv_values(PROJECT_DIR / "runtime" / "local.env"),
        **os.environ,
    }
    defaults = AssistantSettings()
    settings = AssistantSettings(
        mode=assistant.get("mode", defaults.mode),
        model=environment.get("ZHIPU_CHAT_MODEL") or assistant.get("model", defaults.model),
        base_url=environment.get("ZHIPU_BASE_URL") or assistant.get("base_url", defaults.base_url),
        api_key=environment.get("ZHIPU_API_KEY") or "",
        temperature=float(assistant.get("temperature", defaults.temperature)),
        timeout=float(assistant.get("timeout", defaults.timeout)),
        max_retries=int(assistant.get("max_retries", defaults.max_retries)),
        top_k=int(assistant.get("top_k", defaults.top_k)),
        max_remote_rounds=int(assistant.get("max_remote_rounds", defaults.max_remote_rounds)),
    )
    if settings.mode not in {"framework", "glm"}:
        raise ValueError("assistant.mode 只能为 framework 或 glm。")
    if not isinstance(settings.model, str) or not settings.model.strip():
        raise ValueError("必须配置聊天模型名称。")
    if not isinstance(settings.base_url, str) or not settings.base_url.strip():
        raise ValueError("必须配置聊天模型接口地址。")
    if not math.isfinite(settings.temperature) or not 0 <= settings.temperature <= 2:
        raise ValueError("assistant.temperature 必须为 0～2 的有限数值。")
    if not math.isfinite(settings.timeout) or settings.timeout <= 0:
        raise ValueError("assistant.timeout 必须为正数。")
    if settings.max_retries < 0:
        raise ValueError("assistant.max_retries 不能为负数。")
    if not 1 <= settings.top_k <= 20:
        raise ValueError("assistant.top_k 必须为 1～20。")
    if not 1 <= settings.max_remote_rounds <= 5:
        raise ValueError("assistant.max_remote_rounds 必须为 1～5。")
    return settings


def load_vector_settings(path: Path | None = None) -> VectorSettings:
    config_path = path or PROJECT_DIR / "config.toml"
    with config_path.open("rb") as stream:
        config = tomllib.load(stream)
    vector = config["vector_store"]
    embedding = config["embedding"]
    qdrant = config["qdrant"]
    postgres = config["pgvector"]
    local_env = dotenv_values(PROJECT_DIR / "runtime" / "local.env")
    password_env = postgres["password_env"]
    settings = VectorSettings(
        backend=vector["backend"],
        namespace=vector["namespace"],
        dimension=embedding["dimension"],
        model=embedding["model"],
        model_path=Path(embedding["model_path"]).expanduser(),
        cache_dir=Path(embedding["cache_dir"]).expanduser(),
        qdrant_url=qdrant["url"],
        pg_host=postgres["host"],
        pg_port=postgres["port"],
        pg_database=postgres["database"],
        pg_user=postgres["user"],
        pg_password=os.environ.get(password_env) or local_env.get(password_env) or "",
        chunk_size=config["ingestion"]["chunk_size"],
        chunk_overlap=config["ingestion"]["chunk_overlap"],
        allowed_roots=tuple(
            (PROJECT_DIR / Path(root).expanduser()).resolve()
            for root in config["ingestion"].get("allowed_roots", ["documents/source"])
        ),
    )
    if settings.backend not in {"qdrant", "pgvector"}:
        raise ValueError("vector_store.backend 只能为 qdrant 或 pgvector。")
    if settings.dimension != 384:
        raise ValueError("当前本地 MiniLM 模型的向量维度固定为 384。")
    if settings.chunk_size <= 0 or not 0 <= settings.chunk_overlap < settings.chunk_size:
        raise ValueError("切块大小必须为正数，重叠长度必须小于切块大小。")
    if not settings.namespace or len(settings.namespace) > 80:
        raise ValueError("namespace 必须为 1～80 个字符。")
    if not settings.allowed_roots:
        raise ValueError("必须配置至少一个允许录入的本地目录。")
    return settings
