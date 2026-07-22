"""FastAPI 与 CLI 共用的稳定输入/输出契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: str
    source: str
    source_type: str
    page: int | None = None
    start_index: int | None = None
    quote: str
    relevance_score: float
    vector_score: float
    lexical_overlap: float


class RetrievalMatch(BaseModel):
    rank: int
    chunk_id: str
    source: str
    page: int | None = None
    relevance_score: float
    vector_score: float
    lexical_overlap: float
    accepted: bool
    content_preview: str


class RetrievalTrace(BaseModel):
    top_k: int
    min_relevance_score: float
    min_lexical_overlap: float
    returned_count: int
    accepted_count: int
    matches: list[RetrievalMatch]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=8)


class AskResponse(BaseModel):
    request_id: str
    answer: str
    answerable: bool
    citations: list[Citation]
    retrieval: RetrievalTrace
    mode: str
    embedding_mode: str


class ReindexRequest(BaseModel):
    reset: bool = Field(
        default=False,
        description="chunk/embedding 配置变化时显式清空并重建整个索引。",
    )


class ReindexResponse(BaseModel):
    request_id: str
    reset: bool
    scanned_files: int
    added_files: int
    updated_files: int
    unchanged_files: int
    removed_files: int
    indexed_chunks: int
    deleted_chunks: int
    total_indexed_chunks: int
    index_fingerprint: str


class HealthResponse(BaseModel):
    status: str
    mode: str
    embedding_mode: str
    embedding_model: str
    collection: str
    index_ready: bool
    index_config_matches: bool
    source_document_count: int
    indexed_chunk_count: int
    index_fingerprint: str | None = None
    request_id: str
