"""界面与后续 RAG、集群上下文之间的数据合同。"""

from typing import Literal

from pydantic import BaseModel, Field


class ClusterContext(BaseModel):
    server_url: str | None = None
    cluster_name: str | None = None
    kubernetes_version: str | None = None
    operating_system: str | None = None
    install_mode: str | None = None
    fetched_at: str | None = None


class AssistantRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=12000)
    context: ClusterContext = Field(default_factory=ClusterContext)


class DocumentMetadata(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Literal["document", "case"] | None = None
    kubernetes_versions: list[Literal["1.23.10", "1.32.8", "any"]] | None = Field(default=None, min_length=1)
    operating_systems: list[Literal["Ubuntu", "CentOS", "any"]] | None = Field(default=None, min_length=1)
    install_modes: list[Literal["online", "offline", "any"]] | None = Field(default=None, min_length=1)
    verification_status: Literal["source_document", "verified", "unverified"] | None = None


class IngestRequest(BaseModel):
    file_path: str = Field(min_length=1, max_length=2000)
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)


class VectorSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    kubernetes_version: Literal["1.23.10", "1.32.8"] | None = None
    operating_system: Literal["Ubuntu", "CentOS"] | None = None
    install_mode: Literal["online", "offline"] | None = None
