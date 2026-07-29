"""把目录 4 的真实知识库能力适配为目录 5 可调用的检索组件。

目录 5 不重新实现 Loader、Embedding 或 Chroma 持久化，而是复用目录 4 的
``Settings`` 和 ``IncrementalIndexer``。这里仅增加 Agentic RAG 需要的结构化
检索结果、可回答性 gate 和严格的证据选择边界。
"""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


PROJECT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = PROJECT_DIR.parent
RAG_SERVICE_DIR = REPOSITORY_ROOT / "4_rag_knowledge_base_service"
DEFAULT_SOURCE_DIR = RAG_SERVICE_DIR / "data" / "source"

# 目录 4 当前是可直接运行的脚本式模块，内部使用 ``from config import ...``。
# 把它放到模块搜索路径最前面，才能在不修改目录 4 的情况下复用真实实现。
if str(RAG_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_SERVICE_DIR))

from config import Settings  # noqa: E402
from embeddings import (  # noqa: E402
    build_chat_model,
    grounding_tokens,
    technical_tokens,
)
from indexer import IncrementalIndexer, IndexStats  # noqa: E402


def _preview(text: str, limit: int = 280) -> str:
    normalized = " ".join(text.split())
    return normalized if len(normalized) <= limit else normalized[: limit - 1] + "…"


def relevant_quote(text: str, question: str, limit: int = 420) -> str:
    """从真正进入上下文的文本中截取与问题词项最接近的片段。"""

    normalized = " ".join(text.split())
    terms = grounding_tokens(question)
    lowered = normalized.lower()
    positions = [
        position
        for term in terms
        if (position := lowered.find(term.lower())) >= 0
    ]
    if not positions:
        return _preview(normalized, limit)
    position = min(positions)
    start = max(0, position - limit // 4)
    end = min(len(normalized), start + limit)
    if end - start < limit:
        start = max(0, end - limit)
    prefix = "…" if start else ""
    suffix = "…" if end < len(normalized) else ""
    return prefix + normalized[start:end] + suffix


@dataclass(frozen=True)
class Evidence:
    """一条通过本地可回答性 gate 的真实 Chroma 文档块。"""

    chunk_id: str
    source: str
    source_type: str
    page: int | None
    start_index: int | None
    content: str
    quote: str
    relevance_score: float
    vector_score: float
    lexical_overlap: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalBundle:
    """一次检索的审计结果和通过 gate 的证据。"""

    query: str
    matches: list[dict[str, Any]]
    accepted: list[Evidence]

    def to_artifact(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "matches": self.matches,
            "accepted": [item.to_dict() for item in self.accepted],
        }


def build_tutorial_settings(
    *,
    mode: Literal["offline", "live"] = "offline",
    embedding_mode: Literal["local", "hash", "glm"] = "hash",
    source_dir: Path | None = None,
    runtime_dir: Path | None = None,
) -> Settings:
    """创建目录 5 的配置，同时复用目录 4 的来源和环境变量合同。"""

    active_runtime = runtime_dir or PROJECT_DIR / "runtime" / embedding_mode
    return Settings.from_env(
        mode=mode,
        embedding_mode=embedding_mode,
        source_dir=source_dir or DEFAULT_SOURCE_DIR,
        runtime_dir=active_runtime,
    )


class LocalKnowledgeRetriever:
    """目录 4 的 Chroma 检索器，加上可解释的本地 relevance gate。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.indexer = IncrementalIndexer(settings)

    def ensure_index(self, *, reset: bool = False) -> IndexStats:
        """增量同步来源；首次运行或显式 reset 时创建完整索引。"""

        return self.indexer.reindex(reset=reset)

    def retrieve(self, query: str, *, top_k: int | None = None) -> RetrievalBundle:
        """检索候选、计算分数，并只接受满足目录 4 gate 的文档块。"""

        manifest = self.indexer.read_manifest()
        if not manifest["sources"]:
            return RetrievalBundle(query=query, matches=[], accepted=[])

        query_tokens = grounding_tokens(query)
        query_technical_tokens = technical_tokens(query)
        retrieved = self.indexer.search(
            query,
            top_k=top_k or self.settings.default_top_k,
        )

        candidates: list[dict[str, Any]] = []
        for rank, (document, raw_score) in enumerate(retrieved, start=1):
            vector_score = max(0.0, min(1.0, float(raw_score)))
            document_tokens = grounding_tokens(document.page_content)
            lexical_overlap = len(query_tokens.intersection(document_tokens)) / max(
                1, len(query_tokens)
            )
            relevance_score = 0.25 * vector_score + 0.75 * lexical_overlap
            technical_match = bool(
                query_technical_tokens.intersection(
                    technical_tokens(document.page_content)
                )
            )
            candidates.append(
                {
                    "rank": rank,
                    "document": document,
                    "vector_score": vector_score,
                    "lexical_overlap": lexical_overlap,
                    "relevance_score": relevance_score,
                    "technical_match": technical_match,
                }
            )

        best_relevance = max(
            (float(item["relevance_score"]) for item in candidates),
            default=0.0,
        )
        matches: list[dict[str, Any]] = []
        accepted: list[Evidence] = []
        for item in candidates:
            document = item["document"]
            relevance_score = float(item["relevance_score"])
            lexical_overlap = float(item["lexical_overlap"])
            vector_score = float(item["vector_score"])
            technical_match = bool(item["technical_match"])
            is_accepted = (
                relevance_score >= self.settings.min_relevance_score
                and lexical_overlap >= self.settings.min_lexical_overlap
                and relevance_score >= best_relevance * 0.85
                and (not query_technical_tokens or technical_match)
            )
            metadata = document.metadata
            page = metadata.get("page")
            start_index = metadata.get("start_index")
            match = {
                "rank": int(item["rank"]),
                "chunk_id": str(metadata.get("chunk_id", "")),
                "source": str(metadata.get("source", "unknown")),
                "page": int(page) if isinstance(page, int) else None,
                "relevance_score": round(relevance_score, 6),
                "vector_score": round(vector_score, 6),
                "lexical_overlap": round(lexical_overlap, 6),
                "technical_match": technical_match,
                "accepted": is_accepted,
                "content_preview": _preview(document.page_content),
            }
            matches.append(match)
            if is_accepted:
                accepted.append(
                    Evidence(
                        chunk_id=match["chunk_id"],
                        source=match["source"],
                        source_type=str(
                            metadata.get("source_type", "unknown")
                        ),
                        page=match["page"],
                        start_index=(
                            int(start_index)
                            if isinstance(start_index, int)
                            else None
                        ),
                        content=document.page_content.strip(),
                        quote=relevant_quote(document.page_content, query),
                        relevance_score=match["relevance_score"],
                        vector_score=match["vector_score"],
                        lexical_overlap=match["lexical_overlap"],
                    )
                )

        accepted.sort(key=lambda item: item.relevance_score, reverse=True)
        return RetrievalBundle(query=query, matches=matches, accepted=accepted)


__all__ = [
    "DEFAULT_SOURCE_DIR",
    "Evidence",
    "IndexStats",
    "LocalKnowledgeRetriever",
    "RetrievalBundle",
    "Settings",
    "build_chat_model",
    "build_tutorial_settings",
    "relevant_quote",
]

