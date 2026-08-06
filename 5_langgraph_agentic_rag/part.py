"""Part 3 的手写学习草稿；正式可运行入口是 part3_persistence_hitl.py。"""

from typing import Any, Literal, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class ApprovalState(TypedDict, total=False):
    request: str
    report_preview: str
    approved: bool
    reviewer_note: str
    final_message: str


def prepare_report(state: ApprovalState) -> ApprovalState:
    return {
        "report_preview": (
            f"准备执行：{state['request']}。"
            "这是教学预览，不包含真实客户数据。"
        )
    }


def human_review(state: ApprovalState) -> ApprovalState:
    decision = interrupt(
        {
            "action": "export_business_report",
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
    }


def finish(state: ApprovalState) -> ApprovalState:
    if state["approved"]:
        message = "人工已批准；教学报告可以继续生成。"
    else:
        message = "人工已拒绝；没有执行报告导出。"
    return {"final_message": message}


def build_approval_graph():
    workflow = StateGraph(ApprovalState)
    workflow.add_node("prepare_report", prepare_report)
    workflow.add_node("human_review", human_review)
    workflow.add_node("finish", finish)
    workflow.add_edge(START, "prepare_report")
    workflow.add_edge("prepare_report", "human_review")
    workflow.add_edge("human_review", "finish")
    workflow.add_edge("finish", END)
    return workflow.compile(checkpointer=InMemorySaver())


def run_approval_demo(
    decision: Literal["approve", "reject"] = "approve",
    *,
    thread_id: str | None = None,
) -> dict[str, Any]:
    graph = build_approval_graph()
    active_thread_id = thread_id or f"approval-{uuid4().hex}"
    config = {"configurable": {"thread_id": active_thread_id}}
    paused = graph.invoke(
        {"request": "导出华东区已完成订单汇总"},
        config=config,
    )
    interruptions = paused.get("__interrupt__", [])
    if not interruptions:
        raise AssertionError("图应当在 human_review 节点暂停。")

    final_state = graph.invoke(
        Command(
            resume={
                "decision": decision,
                "note": "目录 5 自动化演示中的人工决定。",
            }
        ),
        config=config,
    )
    return dict(final_state)
