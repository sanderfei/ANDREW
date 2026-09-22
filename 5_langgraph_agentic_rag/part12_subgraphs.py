"""Part 12：父图/子图通信、独立 State Schema 与 checkpoint 作用域。
LangGraph 的子图组织与状态管理教程，如何把一个大流程拆成多个子流程，以及父子流程怎样传递数据、保存各自的状态

本课在一条父图中放入三种子图 （三种 checkpoint 模式）：
1. checkpointer=True：remembering_child 在同一 thread 的多次调用间保留内部状态；
2. checkpointer=None：research_child 每次父图调用使用新的业务状态，但继承父图持久化能力；
3. checkpointer=False：formatter_child 仍有本次执行的 State，但不保存子图 checkpoint。

None 与 False 的关键区别是子图是否保存执行进度（checkpoint 持久化能力）。
假设父图已配置 checkpointer，有一条两节点子图：
    START -> prepare（准备数据）-> approve（interrupt 等待确认）-> END
prepare 已完成、approve 中断后，通过父图的 Command(resume=...) 恢复：
- checkpointer=None：继承父图的存储能力，保存子图内部进度；从 approve 节点重新执行，不重跑 prepare。
- checkpointer=False：不保存子图内部进度；父图仍可承接中断，但恢复时从子图入口重跑 prepare -> approve。
两种模式下，approve 节点都会从头重新执行；None 可以避免重跑之前已经完成的 prepare。
本课的 research_child 和 formatter_child 每次新调用的私有计数都从默认 0 变为 1，
只观察计数看不出上述差别。父图使用 InMemorySaver，checkpoint 保存在内存中，退出进程后不会保留。

子图作为节点：将编译好的子图传给父图的 add_node()。父图执行这个节点时，会运行子图内部的流程。
共享字段与内部字段：父子图可以通过共同字段通信；子图还可以维护自己的内部字段，例如 private_child_turn。
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
    # 没有 Reducer，子图默认覆盖父图
    # 要求该字段同一轮最多收到一次更新。同一轮多个并行任务同时写它，仍会像 conflict_demo 一样报错。
    child_turn_seen: int
    research_step_seen: int
    format_step_seen: int
    draft: str
    formatted: str
    answer: str
    # 有 operator.add Reducer，子图返回拼接列表
    # 子图输出中要包含该字段，才会触发更新；只是定义了同名字段，不代表一定会更新。
    audit: Annotated[list[str], operator.add]


class MemoryChildState(TypedDict, total=False):
    question: str
    # parent 没有这个 key，因此它只存在于子图内部 checkpoint。
    private_child_turn: int
    child_turn_seen: int
    audit: Annotated[list[str], operator.add]


def build_remembering_child():
    """子图记录调用次数"""

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
    """生成研究草稿"""

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
    # checkpointer=True
    #   本次执行过程中保存 checkpoint
    #   下一次调用延续子图内部状态，同一会话中持续积累
    #   每执行一次就+=1
    remembering_child = build_remembering_child()
    # checkpointer=None
    #   本次执行过程使用父图提供的存储能力保存
    #   下一次调用重新开始，每次子图调用相互隔离
    #   每次都是0->1
    research_child = build_research_child()
    # checkpointer=False
    #   本次执行过程不保存 checkpoint
    #   下一次调用重新开始，子图内部状态不延续
    #   每次都是0->1
    formatter_child = build_formatter_child()

    # 字段不一致时，call_formatter 负责转换
    def call_formatter(state: ParentState) -> ParentState:
        """父子 State 不同，通过 wrapper 显式完成输入输出映射。"""

        # 父图的 draft → 子图输入的 text
        child_result = formatter_child.invoke(
            {"title": "子图报告", "text": state["draft"]}
        )
        return {
            # 子图输出的 rendered → 父图的 formatted
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
    # 父子图字段一致时，可以直接嵌入子图，子图作为 Node
    # 父子图共同定义了 question、child_turn_seen、audit 子图返回的共同字段可以更新父图；
    # 父图按自己的字段规则处理更新，例如 audit 使用列表拼接 Reducer。
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
        # 更新父图状态，再执行父图的 parent_finish 节点。 最终状态变为 handled:escalated
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

    # first_result = {
    #     "question": "LangGraph 子图如何通信？",
    #     "child_turn_seen": 1,
    #     "research_step_seen": 1,
    #     "format_step_seen": 1,
    #     "draft": "研究草稿：LangGraph 子图如何通信？",
    #     "formatted": "# 子图报告\n\n研究草稿：LangGraph 子图如何通信？",
    #     "answer": "child_turn=1; research_step=1; format_step=1",
    #     "audit": [
    #         "remembering_child:turn=1",
    #         "research_child:local_step=1",
    #         "parent:formatter_mapped",
    #         "parent:finish",
    #     ],
    # }
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
    # 用同一个 graph 和 config 调用 invoke()
    # 因为父图有 checkpoint，框架先恢复第一次运行结束的父图 State，再应用新输入

    # 第二次进入 remembering_child 时
    # 从子图 checkpoint 恢复,所以 count_child_turn 实际收到：
    # state = {
    #     "question": "第二次调用仍然隔离哪些子图状态？",
    #     "private_child_turn": 1,
    #     "child_turn_seen": 1,
    #     "audit": C1 + A1,  # 此时已有 5 条
    # }
    second_result = graph.invoke(
        {"question": "第二次调用仍然隔离哪些子图状态？"},
        config=config,
    )
    snapshot = graph.get_state(config, subgraphs=True)

    nested_namespaces = sorted(
        {namespace for event in events for namespace in event["ns"] if namespace}
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
