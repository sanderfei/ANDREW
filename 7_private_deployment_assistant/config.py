"""从 TOML 选择向量后端；数据库密码仅从本地环境文件或环境变量读取。"""

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
