"""Part 3：Checkpointer、thread_id、interrupt() 与 Command(resume=...)。

这个例子只生成“待导出报告”，不会发送消息或写入外部系统。

运行：
    .venv/bin/python 5_langgraph_agentic_rag/part3_persistence_hitl.py
    .venv/bin/python 5_langgraph_agentic_rag/part3_persistence_hitl.py --reject
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Literal, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


OFFICIAL_SOURCES = [
    "https://docs.langchain.com/oss/python/langgraph/persistence",
    "https://docs.langchain.com/oss/python/langchain/human-in-the-loop",
]


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


# 恢复时不是简单地从 interrupt() 下一行继续，而是从 human_review() 开头重新执行。
# 恢复时会从发生中断的 Node 开头重新执行
# 所以：interrupt() 前面尽量不要放非幂等的外部副作用。
def human_review(state: ApprovalState) -> ApprovalState:
    # interrupt() 会暂停图；传入的字典是发给图外审核者的信息。
    # 第一次 invoke 执行到这里时，interrupt() 不会正常返回给 decision，而是让 Graph 暂停。
    # 恢复后，decision 就是第二次 invoke 发送的 Command.resume 字典。
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
    # 保存 State 和执行位置
    return workflow.compile(checkpointer=InMemorySaver())


def run_approval_demo(
    decision: Literal["approve", "reject"] = "approve",
    *,
    thread_id: str | None = None,
) -> dict[str, Any]:
    graph = build_approval_graph()
    active_thread_id = thread_id or f"approval-{uuid4().hex}"
    # 第二次调用必须访问同一 Checkpointer，并使用相同 thread_id。
    config = {"configurable": {"thread_id": active_thread_id}}
    paused = graph.invoke(
        {"request": "导出华东区已完成订单汇总"},
        config=config,
    )
    interruptions = paused.get("__interrupt__", [])
    if not interruptions:
        raise AssertionError("图应当在 human_review 节点暂停。")

    final_state = graph.invoke(
        # Command 会发送给 LangGraph，由 LangGraph 提取 resume 字段。
        Command(
            resume={
                "decision": decision,
                "note": "目录 5 自动化演示中的人工决定。",
            }
        ),
        config=config,
    )
    return {
        "thread_id": active_thread_id,
        "paused": True,
        "interrupt_count": len(interruptions),
        "decision": decision,
        "approved": final_state["approved"],
        "reviewer_note": final_state["reviewer_note"],
        "final_message": final_state["final_message"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="演示 LangGraph 人工确认和恢复")
    parser.add_argument(
        "--reject",
        action="store_true",
        help="默认批准；传入该参数演示拒绝分支。",
    )
    args = parser.parse_args(argv)
    result = run_approval_demo("reject" if args.reject else "approve")
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
