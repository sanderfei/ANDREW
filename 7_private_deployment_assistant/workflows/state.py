"""工作流中间状态与模型输出合同；不存放 SSH 密码或模型密钥。"""

from operator import add
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field


class EnvironmentFacts(BaseModel):
    kubernetes_version: Literal["1.23.10", "1.32.8"] | None = None
    operating_system: Literal["Ubuntu", "CentOS"] | None = None
    install_mode: Literal["online", "offline"] | None = None


class InputAnalysis(BaseModel):
    summary: str = Field(min_length=1, max_length=1500)
    query: str = Field(min_length=1, max_length=2000)
    environment: EnvironmentFacts = Field(default_factory=EnvironmentFacts)
    missing_information: list[str] = Field(default_factory=list, max_length=4)
    is_fault: bool = True


class EvidenceAssessment(BaseModel):
    sufficient: bool
    reason: str = Field(min_length=1, max_length=1500)
    source_ids: list[int] = Field(default_factory=list, max_length=20)


class AnswerDraft(BaseModel):
    answer: str = Field(min_length=1, max_length=20000)
    source_ids: list[int] = Field(min_length=1, max_length=20)
    verification_steps: list[str] = Field(default_factory=list, max_length=6)
    root_cause: str | None = Field(default=None, max_length=4000)


class DiagnosticCheck(BaseModel):
    name: Literal["host_summary", "cluster_nodes", "pods", "events", "pod_describe", "pod_logs", "helm_status"]
    parameters: dict = Field(default_factory=dict)


class DiagnosisDraft(BaseModel):
    analysis: str = Field(min_length=1, max_length=6000)
    hypotheses: list[str] = Field(default_factory=list, max_length=4)
    next_checks: list[str] = Field(default_factory=list, max_length=4)
    questions: list[str] = Field(default_factory=list, max_length=4)
    proposed_solution: str | None = Field(default=None, max_length=6000)
    verification_steps: list[str] = Field(default_factory=list, max_length=6)
    needs_remote_evidence: bool = False
    requested_checks: list[DiagnosticCheck] = Field(default_factory=list, max_length=4)
    root_cause: str | None = Field(default=None, max_length=4000)


class WorkflowState(TypedDict, total=False):
    thread_id: str
    question: str
    history: list[dict]
    context: dict
    explicit_context: dict
    analysis: dict
    missing_information: list[str]
    query: str
    documents: list[dict]
    retrieval_status: str
    assessment: dict
    draft: dict
    answer: str
    workflow_status: str
    sources: list[dict]
    request_id: str
    action: str
    connection_id: str | None
    remote_rounds: int
    executed_checks: list[str]
    evidence: list[dict]
    proposal: dict
    verification_request: dict
    verification: dict
    case: dict | None
    trace_id: str
    # 每个节点只返回本节点的名称，Reducer 按执行顺序累积。
    steps: Annotated[list[str], add]
