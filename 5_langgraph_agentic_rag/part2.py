from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import RetryPolicy
from pydantic import BaseModel, Field
from agentic_rag import _is_smalltalk, ROUTER_SYSTEM_PROMPT
from local_rag_adapter import LocalKnowledgeRetriever, relevant_quote


def make_retrieval_tool(
    retriever: LocalKnowledgeRetriever,
    *,
    top_k: int,
) -> BaseTool:

    @tool(response_format="content_and_artifact")
    def retriever_context(query: str) -> tuple[str, dict[str, Any]]:
        """从本地知识库检索与 query 直接相关的证据。"""
        bundle = retriever.retrieve(query, top_k=top_k)
        artifact = bundle.to_artifact()  # 给程序保留的原始对象
        if bundle.accepted:
            serialized = "\n\n".join(
                f"【{i + 1}】{item.quote}\n{item.content}"
                for i, item in enumerate(bundle.accepted)
            )  # 给模型读取的content
            return serialized, artifact

    return retriever_context


class GradeDocuments(BaseModel):
    """负责约束证据判断结果。"""

    binary_score: Literal["yes", "no"] = Field(
        description="检索证据相关且足以回答时为 yes，否则为 no。"
    )


class GroundedAnswer(BaseModel):
    """答案文本和模型声称实际使用的证据 ID。负责约束最终模型输出："""

    answer: str = Field(description="只依据上下文生成的最终答案。")
    cited_chunk_ids: list[str] = Field(
        description="回答实际使用的 chunk_id；只能取自允许列表。"
    )


class AgenticRAGState(MessagesState, total=False):
    """Agentic RAG 工作流的状态对象。"""

    original_question: str
    active_query: str
    answer: str
    answerable: bool
    grounded: bool  # 最终回答是否由本次检索证据支撑并通过 citation ID 校验。
    route: str
    retrieval_attempts: int  # 每执行一次 assess_evidence 加 1
    rewrite_count: int  # 每执行一次 rewrite_question 加 1。
    max_rewrites: int
    grade_relevant: bool  # 最近一次 assess_evidence 判断证据是否相关且足以回答。
    retrieval_trace: list[dict[str, Any]]  # 每次检索的完整审计记录
    used_evidence: list[dict[str, Any]]  # 真正进入回答 Prompt 的证据。
    citations: list[
        dict[str, Any]
    ]  # 根据校验通过的 chunk_id 从真实 used_evidence 构造的对外引用。
    invalid_cited_chunk_ids: list[str]


def _latest_human_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return _message_text(message)
    return ""


def _message_text(message: BaseMessage) -> str:
    """兼容字符串 content 与 provider 返回的 content blocks。"""

    content = message.content
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts).strip()


def build_agentic_rag_graph(
    retriever: LocalKnowledgeRetriever,
    *,
    model: Any | None = None,
    top_k: int = 4,
    max_context_chars: int = 6000,
):
    """构建一个可执行的 Agentic RAG 工作流。"""

    retrieval_tool = make_retrieval_tool(retriever, top_k=top_k)
    model_with_tools = model.bind_tools([retrieval_tool]) if model is not None else None

    grader = (
        model.with_structured_output(
            GradeDocuments,
            method="function_calling",
            include_raw=False,
        )
        if model is not None
        else None
    )
    answer_model = (
        model.with_structured_output(
            GroundedAnswer,
            method="function_calling",
        )
        if model is not None
        else None
    )

    def generate_query_or_respond(
        state: AgenticRAGState,
    ) -> dict[str, Any]:
        messages = list(state["messages"])
        original_question = state["original_question"]
        active_query = state.get("active_query") or _latest_human_text(messages)

        if model_with_tools is None:
            if _is_smalltalk(original_question):
                response = AIMessage(content="你好，我可以帮你查询本地知识库。")
            else:
                response = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": retrieval_tool.name,
                            "args": {"query": active_query},
                            "id": f"offline-{uuid4().hex[:12]}",
                            "type": "tool_call",
                        }
                    ],
                )
        else:
            response = model_with_tools.invoke(
                [
                    SystemMessage(content=ROUTER_SYSTEM_PROMPT),
                    *messages,
                ]
            )
            if not response.tool_calls and not _is_smalltalk(original_question):
                response = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": retrieval_tool.name,
                            "args": {"query": active_query},
                            "id": f"offline-{uuid4().hex[:12]}",
                            "type": "tool_call",
                        }
                    ],
                )

        if response.tool_calls:
            tool_call = response.tool_calls[0]
            response = AIMessage(
                content=response.content,
                tool_calls=[
                    {
                        "name": retrieval_tool.name,
                        "args": {"query": active_query},
                        "id": str(
                            tool_call.get("id") or f"retrieve-{uuid4().hex[:12]}"
                        ),
                        "type": "tool_call",
                    }
                ],
            )

        update: dict[str, Any] = {"messages": [response]}
        if response.tool_calls:
            query = response.tool_calls[0].get("args", {}).get("query")
            update.update(
                {
                    "active_query": (str(query).strip() if query else active_query),
                    "route": "retrieve",
                }
            )
        else:
            update.update(
                {
                    "answer": _message_text(response),
                    "answerable": False,
                    "grounded": False,
                    "route": "direct",
                    "citations": [],
                }
            )
        return update

    def route_on_tool_calls(
        state: AgenticRAGState,
    ) -> Literal["retrieve", "direct"]:
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "retrieve"
        return "direct"
