"""4_rag_knowledge_base_service 的显式配置边界。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


PROJECT_DIR = Path(__file__).resolve().parent


def _load_dotenv_files() -> None:
    """复用根目录配置，目录 4 的文件只补缺；系统环境变量优先级最高。"""

    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv(PROJECT_DIR.parent / ".env", override=False)
    load_dotenv(PROJECT_DIR / ".env", override=False)


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数，当前值为 {raw!r}。") from exc


def _as_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是数字，当前值为 {raw!r}。") from exc


def _resolve_project_path(raw: str, default: Path) -> Path:
    if not raw:
        return default
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


@dataclass(frozen=True)
class Settings:
    """所有可变配置均从环境变量或显式测试参数而来。"""

    mode: Literal["offline", "live"]
    embedding_mode: Literal["local", "hash", "glm"]
    source_dir: Path
    runtime_dir: Path
    collection_name: str
    chunk_size: int
    chunk_overlap: int
    default_top_k: int
    min_relevance_score: float
    min_lexical_overlap: float
    max_context_chars: int
    timeout_seconds: int
    zhipu_api_key: str | None
    zhipu_base_url: str
    chat_model: str
    embedding_model: str
    local_embedding_model: str
    local_embedding_cache: Path
    local_embedding_path: Path
    langsmith_tracing: bool

    @property
    def manifest_path(self) -> Path:
        return self.runtime_dir / "index_manifest.json"

    @property
    def chroma_dir(self) -> Path:
        return self.runtime_dir / "chroma"

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    @classmethod
    def from_env(
        cls,
        *,
        mode: str | None = None,
        embedding_mode: str | None = None,
        source_dir: Path | None = None,
        runtime_dir: Path | None = None,
    ) -> "Settings":
        _load_dotenv_files()
        selected_mode = (mode or os.getenv("RAG_MODE", "offline")).strip().lower()
        if selected_mode not in {"offline", "live"}:
            raise ValueError("RAG_MODE 只允许 offline 或 live。")

        selected_embedding_mode = (
            embedding_mode or os.getenv("RAG_EMBEDDING_MODE", "local")
        ).strip().lower()
        if selected_embedding_mode not in {"local", "hash", "glm"}:
            raise ValueError("RAG_EMBEDDING_MODE 只允许 local、hash 或 glm。")

        key = os.getenv("ZHIPU_API_KEY") or None
        if selected_mode == "live" and not key:
            raise ValueError(
                "RAG_MODE=live 需要 ZHIPU_API_KEY；默认 offline 模式不需要聊天模型密钥。"
            )
        if selected_embedding_mode == "glm" and not key:
            raise ValueError("RAG_EMBEDDING_MODE=glm 需要 ZHIPU_API_KEY。")

        configured_source = _resolve_project_path(
            os.getenv("RAG_SOURCE_DIR", ""), PROJECT_DIR / "data" / "source"
        )
        configured_runtime = _resolve_project_path(
            os.getenv("RAG_RUNTIME_DIR", ""), PROJECT_DIR / "runtime"
        )
        chunk_size = _as_int("RAG_CHUNK_SIZE", 800)
        chunk_overlap = _as_int("RAG_CHUNK_OVERLAP", 120)
        if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("要求 RAG_CHUNK_SIZE > RAG_CHUNK_OVERLAP >= 0。")

        return cls(
            mode=selected_mode,  # type: ignore[arg-type]
            embedding_mode=selected_embedding_mode,  # type: ignore[arg-type]
            source_dir=(source_dir or configured_source).resolve(),
            runtime_dir=(runtime_dir or configured_runtime).resolve(),
            collection_name=os.getenv(
                "RAG_COLLECTION_NAME", "andrew_rag_knowledge_base"
            ),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            default_top_k=_as_int("RAG_TOP_K", 4),
            min_relevance_score=_as_float("RAG_MIN_RELEVANCE", 0.10),
            min_lexical_overlap=_as_float("RAG_MIN_LEXICAL_OVERLAP", 0.12),
            max_context_chars=_as_int("RAG_MAX_CONTEXT_CHARS", 6000),
            timeout_seconds=_as_int("RAG_TIMEOUT_SECONDS", 30),
            zhipu_api_key=key,
            zhipu_base_url=os.getenv(
                "ZHIPU_BASE_URL", "https://ai-hub.digiwincloud.com.cn/v1"
            ),
            chat_model=(
                os.getenv("RAG_CHAT_MODEL")
                or os.getenv("ZHIPU_CHAT_MODEL")
                or "ep-qwen2.5-72b"
            ),
            embedding_model=(
                os.getenv("RAG_EMBEDDING_MODEL")
                or os.getenv("ZHIPU_EMBEDDING_MODEL")
                or "embedding-3"
            ),
            local_embedding_model=os.getenv(
                "LOCAL_EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            ),
            local_embedding_cache=_resolve_project_path(
                os.getenv("LOCAL_EMBEDDING_CACHE", "~/.cache/fastembed"),
                Path.home() / ".cache" / "fastembed",
            ),
            local_embedding_path=_resolve_project_path(
                os.getenv(
                    "LOCAL_EMBEDDING_PATH",
                    "~/.cache/fastembed/paraphrase-multilingual-MiniLM-L12-v2-modelscope",
                ),
                Path.home()
                / ".cache"
                / "fastembed"
                / "paraphrase-multilingual-MiniLM-L12-v2-modelscope",
            ),
            langsmith_tracing=_as_bool(os.getenv("LANGSMITH_TRACING", "false")),
        )
