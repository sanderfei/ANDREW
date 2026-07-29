"""Part 8：把 RAG、只读 SQL 与 HITL 合成一个受控多工具 Graph。

本课复用而不修改已有实现：

- ``local_rag_adapter.py`` 的目录 4 检索适配；
- ``agentic_rag.py`` 的 retrieval Tool；
- Part 4 的只读业务指标 Tool；
- Part 3 的 interrupt / Command(resume=...) 模式。

这里故意让显式 Graph 决定工具权限。知识问题只能进入检索节点，指标问题只能
选择白名单参数，带“导出”的请求必须先暂停等待人工决定。

运行：
    .venv/bin/python \
      5_langgraph_agentic_rag/part8_controlled_multi_tool_graph.py \
      --question "知识库使用什么向量数据库？"

    .venv/bin/python \
      5_langgraph_agentic_rag/part8_controlled_multi_tool_graph.py \
      --question "导出华东已完成订单营收" --decision approve
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator, Literal, TypedDict
from uuid import uuid4

from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agentic_rag import make_retrieval_tool
from local_rag_adapter import (
    LocalKnowledgeRetriever,
    build_tutorial_settings,
)
from part4_readonly_sql_tools import (
    MetricName,
    RegionName,
    build_business_metric_tool,
    initialize_demo_database,
)


PROJECT_DIR = Path(__file__).resolve().parent
OFFICIAL_SOURCES = [
    "https://docs.langchain.com/oss/python/langgraph/agentic-rag",
    "https://docs.langchain.com/oss/python/langchain/sql-agent",
    "https://docs.langchain.com/oss/python/langchain/human-in-the-loop",
]
RouteName = Literal["knowledge", "business", "export", "smalltalk"]


class ControlledAssistantState(TypedDict, total=False):
    question: str
    turn_count: int
    previous_question: str
    last_question: str
    route: str
    answer: str
    answerable: bool
    grounded: bool
    citations: list[dict[str, Any]]
    metric: MetricName
    region: RegionName
    metric_result: dict[str, Any] | None
    report_preview: str
    approved: bool | None
    reviewer_note: str
    audit_log: list[dict[str, Any]]


def _normalize_question(question: str) -> str:
    normalized = question.strip()
    if not normalized:
        raise ValueError("question 不能为空。")
    return normalized


def _is_smalltalk(question: str) -> bool:
    normalized = (
        question.lower()
        .replace("，", "")
        .replace("。", "")
        .replace("！", "")
        .replace("!", "")
        .replace("？", "")
        .replace("?", "")
        .strip()
    )
    return normalized in {
        "你好",
        "您好",
        "在吗",
        "谢谢",
        "感谢",
        "再见",
        "hi",
        "hello",
        "thanks",
    }


def _metric_from_question(question: str) -> MetricName:
    lowered = question.lower()
    if any(term in lowered for term in ("平均", "客单价", "average")):
        return "average_completed_order_value"
    if any(
        term in lowered
        for term in ("多少单", "订单数", "订单量", "数量", "count")
    ):
        return "completed_order_count"
    return "completed_revenue"


def _region_from_question(question: str) -> RegionName:
    for region in ("华东", "华南", "华北"):
        if region in question:
            return region
    return "all"


def _classify(question: str) -> RouteName:
    lowered = question.lower()
    if _is_smalltalk(question):
        return "smalltalk"
    if any(term in lowered for term in ("导出", "下载报表", "export")):
        return "export"
    if any(
        term in lowered
        for term in (
            "营收",
            "收入",
            "金额",
            "订单数",
            "订单量",
            "多少单",
            "客单价",
            "revenue",
            "order count",
        )
    ):
        return "business"
    return "knowledge"


def _append_audit(
    state: ControlledAssistantState,
    *,
    node: str,
    detail: str,
) -> list[dict[str, Any]]:
    return [
        *state.get("audit_log", []),
        {"node": node, "detail": detail},
    ]


def _citation_from_artifact(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": str(item["chunk_id"]),
        "source": str(item["source"]),
        "source_type": str(item.get("source_type", "unknown")),
        "page": item.get("page"),
        "start_index": item.get("start_index"),
        "quote": str(item["quote"]),
        "relevance_score": float(item["relevance_score"]),
    }


def initial_request(question: str) -> ControlledAssistantState:
    """覆盖上一轮结果字段，同时保留 checkpointer 中的会话记忆字段。"""

    return {
        "question": _normalize_question(question),
        "route": "start",
        "answer": "",
        "answerable": False,
        "grounded": False,
        "citations": [],
        "metric": "completed_revenue",
        "region": "all",
        "metric_result": None,
        "report_preview": "",
        "approved": None,
        "reviewer_note": "",
        "audit_log": [],
    }


def build_controlled_assistant_graph(
    retriever: LocalKnowledgeRetriever,
    database_path: Path,
    *,
    checkpointer: Any | None = None,
    top_k: int = 4,
):
    """构造单 Agent、多 Tool、显式权限分支的教学 Graph。"""

    retrieval_tool = make_retrieval_tool(retriever, top_k=top_k)
    metric_tool = build_business_metric_tool(database_path)

    def route_request(
        state: ControlledAssistantState,
    ) -> ControlledAssistantState:
        question = state["question"]
        selected = _classify(question)
        metric = _metric_from_question(question)
        region = _region_from_question(question)
        writer = get_stream_writer()
        writer(
            {
                "stage": "route",
                "route": selected,
                "detail": "显式 Graph 已选择允许的能力分支。",
            }
        )
        return {
            "route": selected,
            "turn_count": int(state.get("turn_count", 0)) + 1,
            "previous_question": str(state.get("last_question", "")),
            "metric": metric,
            "region": region,
            "audit_log": _append_audit(
                state,
                node="route_request",
                detail=f"route={selected}",
            ),
        }

    def choose_route(state: ControlledAssistantState) -> RouteName:
        route = state["route"]
        if route not in {"knowledge", "business", "export", "smalltalk"}:
            raise ValueError(f"未知 route：{route}")
        return route

    def answer_smalltalk(
        state: ControlledAssistantState,
    ) -> ControlledAssistantState:
        return {
            "route": "smalltalk",
            "answer": "你好，我可以查询本地知识库或只读业务指标。",
            "audit_log": _append_audit(
                state,
                node="answer_smalltalk",
                detail="没有调用 Tool。",
            ),
        }

    def retrieve_knowledge(
        state: ControlledAssistantState,
    ) -> ControlledAssistantState:
        tool_call = {
            "name": retrieval_tool.name,
            "args": {"query": state["question"]},
            "id": f"knowledge-{uuid4().hex[:12]}",
            "type": "tool_call",
        }
        tool_message = retrieval_tool.invoke(tool_call)
        if not isinstance(tool_message, ToolMessage):
            raise TypeError("检索 Tool 应返回带 artifact 的 ToolMessage。")
        artifact = tool_message.artifact
        if not isinstance(artifact, dict):
            artifact = {"accepted": []}
        accepted = artifact.get("accepted", [])
        if not isinstance(accepted, list):
            accepted = []
        used = [item for item in accepted[:2] if isinstance(item, dict)]

        writer = get_stream_writer()
        writer(
            {
                "stage": "tool",
                "tool": retrieval_tool.name,
                "accepted_count": len(used),
            }
        )
        if not used:
            return {
                "route": "knowledge_refused",
                "answer": "我不知道，当前知识库中没有足够相关资料。",
                "answerable": False,
                "grounded": False,
                "citations": [],
                "audit_log": _append_audit(
                    state,
                    node="retrieve_knowledge",
                    detail=f"tool={retrieval_tool.name}; accepted=0",
                ),
            }

        citations = [_citation_from_artifact(item) for item in used]
        answer = "根据本地知识库的相关片段：\n" + "\n\n".join(
            str(item["quote"]) for item in used
        )
        return {
            "route": "knowledge_grounded",
            "answer": answer,
            "answerable": True,
            "grounded": True,
            "citations": citations,
            "audit_log": _append_audit(
                state,
                node="retrieve_knowledge",
                detail=(
                    f"tool={retrieval_tool.name}; "
                    f"accepted={len(citations)}"
                ),
            ),
        }

    def _invoke_metric_tool(
        state: ControlledAssistantState,
    ) -> dict[str, Any]:
        raw = metric_tool.invoke(
            {
                "metric": state["metric"],
                "region": state["region"],
            }
        )
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise TypeError("业务指标 Tool 必须返回 JSON object。")
        return result

    def query_business_metric(
        state: ControlledAssistantState,
    ) -> ControlledAssistantState:
        result = _invoke_metric_tool(state)
        get_stream_writer()(
            {
                "stage": "tool",
                "tool": metric_tool.name,
                "metric": result["metric"],
                "region": result["region"],
            }
        )
        return {
            "route": "business_metric",
            "answer": (
                f"{result['region']} 的 {result['metric']} 为 "
                f"{result['value']} {result['unit']}。"
            ),
            "answerable": True,
            "metric_result": result,
            "audit_log": _append_audit(
                state,
                node="query_business_metric",
                detail=(
                    f"tool={metric_tool.name}; "
                    f"metric={result['metric']}; region={result['region']}"
                ),
            ),
        }

    def prepare_export(
        state: ControlledAssistantState,
    ) -> ControlledAssistantState:
        preview = (
            f"准备导出 region={state['region']}、"
            f"metric={state['metric']} 的教学汇总；"
            "不会创建真实文件或发送外部消息。"
        )
        return {
            "route": "awaiting_approval",
            "report_preview": preview,
            "audit_log": _append_audit(
                state,
                node="prepare_export",
                detail="已生成预览，尚未执行指标 Tool。",
            ),
        }

    def request_export_approval(
        state: ControlledAssistantState,
    ) -> ControlledAssistantState:
        decision = interrupt(
            {
                "action": "export_business_metric",
                "preview": state["report_preview"],
                "allowed_decisions": ["approve", "reject"],
            }
        )
        if not isinstance(decision, dict):
            raise ValueError("恢复参数必须是包含 decision 的字典。")
        selected = decision.get("decision")
        if selected not in {"approve", "reject"}:
            raise ValueError("decision 只允许 approve 或 reject。")
        return {
            "approved": selected == "approve",
            "reviewer_note": str(decision.get("note", "")),
            "audit_log": _append_audit(
                state,
                node="request_export_approval",
                detail=f"decision={selected}",
            ),
        }

    def choose_after_approval(
        state: ControlledAssistantState,
    ) -> Literal["execute_export", "reject_export"]:
        return "execute_export" if state["approved"] else "reject_export"

    def execute_export(
        state: ControlledAssistantState,
    ) -> ControlledAssistantState:
        result = _invoke_metric_tool(state)
        return {
            "route": "export_completed",
            "answer": (
                "人工已批准。教学导出结果："
                f"{result['region']} / {result['metric']} = "
                f"{result['value']} {result['unit']}。"
            ),
            "answerable": True,
            "metric_result": result,
            "audit_log": _append_audit(
                state,
                node="execute_export",
                detail=f"tool={metric_tool.name}; approved=true",
            ),
        }

    def reject_export(
        state: ControlledAssistantState,
    ) -> ControlledAssistantState:
        return {
            "route": "export_rejected",
            "answer": "人工已拒绝；没有执行指标查询或报告导出。",
            "answerable": False,
            "metric_result": None,
            "audit_log": _append_audit(
                state,
                node="reject_export",
                detail="未调用业务指标 Tool。",
            ),
        }

    def record_turn(
        state: ControlledAssistantState,
    ) -> ControlledAssistantState:
        # last_question 不由 initial_request 重置；同一 thread 的下一轮可以读取它。
        return {"last_question": state["question"]}

    workflow = StateGraph(ControlledAssistantState)
    workflow.add_node("route_request", route_request)
    workflow.add_node("answer_smalltalk", answer_smalltalk)
    workflow.add_node("retrieve_knowledge", retrieve_knowledge)
    workflow.add_node("query_business_metric", query_business_metric)
    workflow.add_node("prepare_export", prepare_export)
    workflow.add_node("request_export_approval", request_export_approval)
    workflow.add_node("execute_export", execute_export)
    workflow.add_node("reject_export", reject_export)
    workflow.add_node("record_turn", record_turn)
    workflow.add_edge(START, "route_request")
    workflow.add_conditional_edges(
        "route_request",
        choose_route,
        {
            "knowledge": "retrieve_knowledge",
            "business": "query_business_metric",
            "export": "prepare_export",
            "smalltalk": "answer_smalltalk",
        },
    )
    workflow.add_edge("answer_smalltalk", "record_turn")
    workflow.add_edge("retrieve_knowledge", "record_turn")
    workflow.add_edge("query_business_metric", "record_turn")
    workflow.add_edge("prepare_export", "request_export_approval")
    workflow.add_conditional_edges(
        "request_export_approval",
        choose_after_approval,
        {
            "execute_export": "execute_export",
            "reject_export": "reject_export",
        },
    )
    workflow.add_edge("execute_export", "record_turn")
    workflow.add_edge("reject_export", "record_turn")
    workflow.add_edge("record_turn", END)
    return workflow.compile(
        checkpointer=checkpointer if checkpointer is not None else InMemorySaver()
    )


def _interrupt_values(state: dict[str, Any]) -> list[Any]:
    values: list[Any] = []
    for item in state.get("__interrupt__", []):
        values.append(getattr(item, "value", item))
    return values


def public_response(
    state: dict[str, Any],
    *,
    thread_id: str,
) -> dict[str, Any]:
    interruptions = _interrupt_values(state)
    return {
        "thread_id": thread_id,
        "turn_count": int(state.get("turn_count", 0)),
        "previous_question": state.get("previous_question", ""),
        "status": "interrupted" if interruptions else "completed",
        "route": state.get("route", "unknown"),
        "answer": state.get("answer", ""),
        "answerable": bool(state.get("answerable")),
        "grounded": bool(state.get("grounded")),
        "citations": list(state.get("citations", [])),
        "metric_result": state.get("metric_result"),
        "approved": state.get("approved"),
        "reviewer_note": state.get("reviewer_note", ""),
        "audit_log": list(state.get("audit_log", [])),
        "interrupts": interruptions,
    }


class ControlledAssistantService:
    """给 CLI、FastAPI 和评测共同使用的轻量运行时封装。"""

    def __init__(self, graph: Any):
        self.graph = graph

    @staticmethod
    def config(thread_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": thread_id}}

    def ask(
        self,
        question: str,
        *,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        active_thread = thread_id or f"assistant-{uuid4().hex}"
        state = self.graph.invoke(
            initial_request(question),
            config=self.config(active_thread),
        )
        return public_response(state, thread_id=active_thread)

    def resume(
        self,
        thread_id: str,
        *,
        decision: Literal["approve", "reject"],
        note: str = "",
    ) -> dict[str, Any]:
        state = self.graph.invoke(
            Command(resume={"decision": decision, "note": note}),
            config=self.config(thread_id),
        )
        return public_response(state, thread_id=thread_id)

    def stream(
        self,
        question: str,
        *,
        thread_id: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        active_thread = thread_id or f"assistant-{uuid4().hex}"
        config = self.config(active_thread)
        yield {
            "type": "metadata",
            "ns": (),
            "data": {"thread_id": active_thread},
        }
        yield from self.graph.stream(
            initial_request(question),
            config=config,
            stream_mode=["updates", "custom"],
            version="v2",
        )
        snapshot = self.graph.get_state(config)
        final_state = dict(snapshot.values)
        task_interruptions = [
            item
            for task in snapshot.tasks
            for item in getattr(task, "interrupts", ())
        ]
        if task_interruptions:
            final_state["__interrupt__"] = task_interruptions
        yield {
            "type": "result",
            "ns": (),
            "data": public_response(
                final_state,
                thread_id=active_thread,
            ),
        }


def build_tutorial_service(
    retriever: LocalKnowledgeRetriever,
    database_path: Path,
    *,
    checkpointer: Any | None = None,
) -> ControlledAssistantService:
    graph = build_controlled_assistant_graph(
        retriever,
        database_path,
        checkpointer=checkpointer,
    )
    return ControlledAssistantService(graph)


def build_default_service(
    *,
    reset_index: bool = False,
) -> ControlledAssistantService:
    settings = build_tutorial_settings(
        mode="offline",
        embedding_mode="hash",
    )
    retriever = LocalKnowledgeRetriever(settings)
    retriever.ensure_index(reset=reset_index)
    database_path = PROJECT_DIR / "runtime" / "business_demo.db"
    initialize_demo_database(database_path)
    return build_tutorial_service(retriever, database_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="演示受控 RAG + SQL + HITL Graph")
    parser.add_argument(
        "--question",
        default="知识库服务使用什么向量数据库？",
    )
    parser.add_argument(
        "--decision",
        choices=("approve", "reject"),
        help="只有请求触发人工确认时才使用。",
    )
    args = parser.parse_args(argv)
    service = build_default_service()
    result = service.ask(args.question)
    if result["status"] == "interrupted" and args.decision:
        result = service.resume(
            result["thread_id"],
            decision=args.decision,
            note="目录 5 CLI 教学决定。",
        )
    print(
        json.dumps(
            {
                "official_sources": OFFICIAL_SOURCES,
                "result": result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
