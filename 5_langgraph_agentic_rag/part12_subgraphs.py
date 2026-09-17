"""Part 12：父图/子图通信、独立 State Schema 与 checkpoint 作用域。

本课在一条父图中放入三种子图：

1. checkpointer=True：remembering_child 在同一 thread 的多次调用间保留内部状态；
2. checkpointer=None：research_child 每次父图调用使用新的业务状态，但继承父图持久化能力；
3. checkpointer=False：formatter_child 作为普通无状态函数调用，不保存 checkpoint。
"""

from __future__ import annotations

import json
import operator
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


class ParentState(TypedDict, total=False):
    question: str
    child_turn_seen: int
    research_step_seen: int
    format_step_seen: int
    draft: str
    formatted: str
    answer: str
    audit: Annotated[list[str], operator.add]


class MemoryChildState(TypedDict, total=False):
    question: str
    # parent 没有这个 key，因此它只存在于子图内部 checkpoint。
    private_child_turn: int
    child_turn_seen: int
    audit: Annotated[list[str], operator.add]


def build_remembering_child():
    def count_child_turn(state: MemoryChildState) -> MemoryChildState:
        current = state.get("private_child_turn", 0) + 1
        return {
            "private_child_turn": current,
            "child_turn_seen": current,
            "audit": [f"remembering_child:turn={current}"],
        }

    workflow = StateGraph(MemoryChildState)
    workflow.add_node("count_child_turn", count_child_turn)
    workflow.add_edge(START, "count_child_turn")
    workflow.add_edge("count_child_turn", END)
    # True 表示该子图在同一 thread 内跨调用保留自己的内部 State。
    return workflow.compile(checkpointer=True)


class ResearchInput(TypedDict):
    question: str


class ResearchOutput(TypedDict, total=False):
    draft: str
    research_step_seen: int
    audit: list[str]


class ResearchState(ResearchInput, ResearchOutput, total=False):
    # input_schema/output_schema 都不暴露这个内部工作字段。
    private_research_step: int


def build_research_child():
    def research(state: ResearchState) -> ResearchState:
        current = state.get("private_research_step", 0) + 1
        return {
            "private_research_step": current,
            "research_step_seen": current,
            "draft": f"研究草稿：{state['question']}",
            "audit": [f"research_child:local_step={current}"],
        }

    workflow = StateGraph(
        ResearchState,
        input_schema=ResearchInput,
        output_schema=ResearchOutput,
    )
    workflow.add_node("research", research)
    workflow.add_edge(START, "research")
    workflow.add_edge("research", END)
    # None 是子图默认模式：每次调用的业务状态相互隔离，但可继承父图 checkpointer。
    return workflow.compile(checkpointer=None)


class FormatterState(TypedDict, total=False):
    title: str
    text: str
    private_format_step: int
    rendered: str
    format_step_seen: int


def build_formatter_child():
    def format_markdown(state: FormatterState) -> FormatterState:
        current = state.get("private_format_step", 0) + 1
        return {
            "private_format_step": current,
            "format_step_seen": current,
            "rendered": f"# {state['title']}\n\n{state['text']}",
        }

    workflow = StateGraph(FormatterState)
    workflow.add_node("format_markdown", format_markdown)
    workflow.add_edge(START, "format_markdown")
    workflow.add_edge("format_markdown", END)
    return workflow.compile(checkpointer=False)


def build_parent_graph(checkpointer: InMemorySaver):
    remembering_child = build_remembering_child()
    research_child = build_research_child()
    formatter_child = build_formatter_child()

    def call_formatter(state: ParentState) -> ParentState:
        """父子 State 不同，通过 wrapper 显式完成输入输出映射。"""

        child_result = formatter_child.invoke(
            {"title": "子图报告", "text": state["draft"]}
        )
        return {
            "formatted": child_result["rendered"],
            "format_step_seen": child_result["format_step_seen"],
            "audit": ["parent:formatter_mapped"],
        }

    def finish(state: ParentState) -> ParentState:
        return {
            "answer": (
                f"child_turn={state['child_turn_seen']}; "
                f"research_step={state['research_step_seen']}; "
                f"format_step={state['format_step_seen']}"
            ),
            "audit": ["parent:finish"],
        }

    workflow = StateGraph(ParentState)
    # 子图与父图共享 question/child_turn_seen/audit，直接作为 Node。
    workflow.add_node("remembering_child", remembering_child)
    workflow.add_node("research_child", research_child)
    # formatter 的字段完全不同，所以父图添加的是转换 wrapper。
    workflow.add_node("call_formatter", call_formatter)
    workflow.add_node("finish", finish)
    workflow.add_edge(START, "remembering_child")
    workflow.add_edge("remembering_child", "research_child")
    workflow.add_edge("research_child", "call_formatter")
    workflow.add_edge("call_formatter", "finish")
    workflow.add_edge("finish", END)
    return workflow.compile(checkpointer=checkpointer)


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    data = event["data"]
    summary: dict[str, Any] = {
        "type": event["type"],
        "ns": list(event["ns"]),
    }
    if isinstance(data, dict):
        summary["keys"] = sorted(str(key) for key in data)
    else:
        summary["data_type"] = type(data).__name__
    return summary


def command_parent_demo() -> dict[str, Any]:
    """子图用 Command.PARENT 更新共享 State，并跳转到父图 Node。"""

    class HandoffState(TypedDict, total=False):
        status: str
        audit: Annotated[list[str], operator.add]

    def handoff_to_parent(_state: HandoffState) -> Command:
        return Command(
            graph=Command.PARENT,
            goto="parent_finish",
            update={"status": "escalated", "audit": ["child:handoff"]},
        )

    child_builder = StateGraph(HandoffState)
    child_builder.add_node("handoff_to_parent", handoff_to_parent)
    child_builder.add_edge(START, "handoff_to_parent")
    child_builder.add_edge("handoff_to_parent", END)
    child = child_builder.compile()

    def parent_finish(state: HandoffState) -> HandoffState:
        return {
            "status": f"handled:{state['status']}",
            "audit": ["parent:finish"],
        }

    parent_builder = StateGraph(HandoffState)
    # destinations 只补充可视化目标；真正的运行时跳转来自 Command.PARENT。
    parent_builder.add_node(
        "child",
        child,
        destinations=("parent_finish",),
    )
    parent_builder.add_node("parent_finish", parent_finish)
    parent_builder.add_edge(START, "child")
    parent_builder.add_edge("child", END)
    parent_builder.add_edge("parent_finish", END)
    result = parent_builder.compile().invoke({"audit": []})
    assert result["audit"] == ["child:handoff", "parent:finish"]
    return result


def run_demo() -> dict[str, Any]:
    checkpointer = InMemorySaver()
    graph = build_parent_graph(checkpointer)
    config = {"configurable": {"thread_id": "subgraph-demo"}}

    events: list[dict[str, Any]] = []
    first_result: ParentState = {}
    for event in graph.stream(
        {"question": "LangGraph 子图如何通信？", "audit": []},
        config=config,
        subgraphs=True,
        stream_mode=["updates", "values"],
        version="v2",
    ):
        events.append(_event_summary(event))
        if event["type"] == "values" and event["ns"] == ():
            first_result = event["data"]

    # 同一个父图 thread 再运行一次：True 子图继续计数，None/False 子图重新从 1 开始。
    second_result = graph.invoke(
        {"question": "第二次调用仍然隔离哪些子图状态？"},
        config=config,
    )
    snapshot = graph.get_state(config, subgraphs=True)

    nested_namespaces = sorted(
        {
            namespace
            for event in events
            for namespace in event["ns"]
            if namespace
        }
    )
    result = {
        "first_run": {
            "answer": first_result["answer"],
            "formatted": first_result["formatted"],
            "audit": first_result["audit"],
        },
        "second_run": {
            "answer": second_result["answer"],
            "child_turn_seen": second_result["child_turn_seen"],
            "research_step_seen": second_result["research_step_seen"],
            "format_step_seen": second_result["format_step_seen"],
        },
        "stream": {
            "event_count": len(events),
            "nested_namespaces": nested_namespaces,
            "events": events,
        },
        "parent_snapshot": {
            "next": list(snapshot.next),
            "task_count": len(snapshot.tasks),
            "answer": snapshot.values["answer"],
        },
        "command_parent": command_parent_demo(),
        "checkpoint_modes": {
            "true": "同一 thread 跨调用保存子图内部 State。",
            "none": "每次调用业务状态隔离，同时继承父图的持久化能力。",
            "false": "完全无 checkpoint，不能在子图内部 interrupt/resume。",
        },
    }

    assert first_result["child_turn_seen"] == 1
    assert second_result["child_turn_seen"] == 2
    assert second_result["research_step_seen"] == 1
    assert second_result["format_step_seen"] == 1
    assert nested_namespaces
    return result


# 启动命令：
#   .venv/bin/python 5_langgraph_agentic_rag/part12_subgraphs.py
# 参数枚举：无。
def main() -> int:
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
