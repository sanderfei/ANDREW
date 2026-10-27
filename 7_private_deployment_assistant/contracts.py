"""界面与后续 RAG、集群上下文之间的数据合同。"""

from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator


class ClusterContext(BaseModel):
    server_url: str | None = None
    cluster_name: str | None = None
    kubernetes_version: str | None = None
    operating_system: str | None = None
    install_mode: str | None = None
    fetched_at: str | None = None


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=48000, strict=True)


class VerificationRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=128)
    confirmed: bool
    method: Literal["user_confirmation", "remote_check"] = "user_confirmation"
    evidence: str = Field(min_length=8, max_length=8000)
    root_cause: str = Field(min_length=2, max_length=4000)
    resolution_steps: list[str] = Field(min_length=1, max_length=20)


class AssistantRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=12000)
    context: ClusterContext = Field(default_factory=ClusterContext)
    # 只传当前 question 之前已成功完成的轮次，不包含提示、报错或未完成问题。
    history: list[AssistantMessage] = Field(default_factory=list, max_length=40)
    request_id: str | None = Field(default=None, min_length=1, max_length=128)
    connection_id: str | None = Field(default=None, max_length=128)
    action: Literal["message", "verify_resolution"] = "message"
    verification: VerificationRequest | None = None

    @field_validator("history")
    @classmethod
    def validate_complete_turns(cls, history: list[AssistantMessage]) -> list[AssistantMessage]:
        if len(history) % 2 or any(
            message.role != ("user" if index % 2 == 0 else "assistant")
            for index, message in enumerate(history)
        ):
            raise ValueError("历史消息必须由已完成的 user、assistant 成对轮次组成。")
        return history


class AssistantResponse(BaseModel):
    thread_id: str = Field(min_length=1, max_length=128)
    answer: str = Field(min_length=1, max_length=48000, strict=True)
    status: Literal["completed"] = "completed"
    workflow_status: Literal[
        "needs_information", "framework_ready", "awaiting_evidence", "awaiting_verification",
        "awaiting_remote_authorization", "resolved"
    ] = "framework_ready"
    retrieval_status: Literal["not_run", "matched", "no_matches"] = "not_run"
    steps: list[str] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    trace_id: str | None = None
    case: dict | None = None
    proposal: dict | None = None


class ConnectionRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=253)
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(exclude=True)
    port: int = Field(default=22, ge=1, le=65535)
    host_key_sha256: str | None = Field(default=None, max_length=128)


class DiagnosticsRequest(BaseModel):
    thread_id: str = Field(min_length=1, max_length=128)
    connection_id: str = Field(min_length=1, max_length=128)
    checks: list[dict] = Field(min_length=1, max_length=10)


class FeedbackRequest(BaseModel):
    trace_id: str = Field(min_length=1, max_length=128)
    score: float = Field(ge=0, le=1)
    comment: str = Field(default="", max_length=2000)


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
