"""Part 5：State Reducer、消息更新、v2 Streaming 与图可视化。

Node 只返回局部更新，Reducer 决定这些更新如何合并；Streaming 让调用者实时观察
Graph 执行过程。本课使用 Annotated 绑定 Reducer，用 operator.add 自动累加列表，
并通过 get_stream_writer() 发送临时进度。draw_mermaid() 生成 Mermaid 文本。

运行：
    .venv/bin/python 5_langgraph_agentic_rag/part5_state_reducers_streaming.py
"""

from __future__ import annotations

import json
import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages


OFFICIAL_SOURCES = [
    "https://docs.langchain.com/oss/python/langgraph/graph-api",
    "https://docs.langchain.com/oss/python/langgraph/streaming",
]


class StreamingState(TypedDict, total=False):
    # 正常字段：新值覆盖旧值
    topic: str
    # 使用 Annotated 给不同 State 字段绑定 Reducer。
    # operator.add 表示每个 Node 返回的新 list 会追加。
    steps: Annotated[list[str], operator.add]
    # add_messages 按消息 ID 合并；没有就新增，相同 ID 就替换。
    # 两个回答 Node 使用相同 ID，因此最终消息会替换草稿消息。
    messages: Annotated[list[BaseMessage], add_messages]
    answer: str


def collect_topic(state: StreamingState) -> StreamingState:
    topic = state["topic"].strip()
    if not topic:
        raise ValueError("topic 不能为空。")
    return {
        "steps": ["collect_topic"],
        "messages": [HumanMessage(content=topic, id="question")],
    }

# writer 这两行是在 Node 内发送一条“自定义实时进度”
# 可以理解成向外层 graph.stream() 发消息：
def write_draft(state: StreamingState) -> StreamingState:
    writer = get_stream_writer()
    writer({"stage": "draft", "detail": "正在生成确定性草稿"})
    return {
        "steps": ["write_draft"],
        "messages": [
            AIMessage(content=f"{state['topic']} 的草稿答案", id="shared-answer")
        ],
    }

# polish 草稿润色
def polish_answer(state: StreamingState) -> StreamingState:
    writer = get_stream_writer()
    writer({"stage": "polish", "detail": "正在替换同 ID 的草稿消息"})
    final_answer = f"{state['topic']}：Node 返回部分状态，Reducer 决定新旧值如何合并。"
    return {
        "steps": ["polish_answer"],
        # 与草稿使用同一个 id，因此 add_messages 会替换草稿，而不是再追加一条。
        "messages": [AIMessage(content=final_answer, id="shared-answer")],
        "answer": final_answer,
    }


def build_streaming_graph():
    workflow = StateGraph(StreamingState)
    workflow.add_node("collect_topic", collect_topic)
    workflow.add_node("write_draft", write_draft)
    workflow.add_node("polish_answer", polish_answer)
    workflow.add_edge(START, "collect_topic")
    workflow.add_edge("collect_topic", "write_draft")
    workflow.add_edge("write_draft", "polish_answer")
    workflow.add_edge("polish_answer", END)
    return workflow.compile()


def _message_summary(message: BaseMessage) -> dict[str, str | None]:
    return {
        "type": message.type,
        "id": message.id,
        "content": str(message.content),
    }


def _event_json_default(value: Any) -> Any:
    if isinstance(value, BaseMessage):
        return value.model_dump(mode="json")
    return str(value)


def run_demo(topic: str = "LangGraph State") -> dict[str, Any]:
    graph = build_streaming_graph()
    event_counts: dict[str, int] = {}
    update_nodes: list[str] = []
    custom_events: list[dict[str, Any]] = []
    final_state: StreamingState = {}

# 具体的 graph执行会产生 event 了解就行
# Node 执行
#   → writer() 可以发送 custom
#   → Node return 产生 updates
#   → Reducer 合并后产生 values
#   → Edge 决定下一个 Node
# event: dict在类型标注层面，它叫 StreamPart，是多种 TypedDict 的联合类型。
# event["type"] 决定 event["data"] 的具体结构。
# ├─ type：事件种类
# ├─ ns：图命名空间；根图通常是 ()
# ├─ data：事件实际数据，结构由 type 决定
# └─ interrupts：部分事件类型具有的额外字段
# values 事件 data 是 Reducer 合并后的完整 State
# updates 事件 data 是 Node 名称 → 该 Node 返回的局部状态更新
# custom 事件 data 就是之前传给 Writer 的原始字典
# 如下是当前代码流程的event流程
# | 顺序 | 执行位置 | Stream Event |
# | --- | --- | --- |
# | 1 | Graph 接收初始输入 | `values`：初始 State |
# | — | `START → collect_topic` | Edge 不产生事件 |
# | 2 | `collect_topic` 返回 | `updates`：局部更新 |
# | 3 | 合并 `collect_topic` 更新 | `values`：完整 State |
# | — | `collect_topic → write_draft` | Edge 不产生事件 |
# | 4 | `write_draft` 调用 `writer()` | `custom`：draft 进度 |
# | 5 | `write_draft` 返回 | `updates`：局部更新 |
# | 6 | 合并 `write_draft` 更新 | `values`：完整 State |
# | — | `write_draft → polish_answer` | Edge 不产生事件 |
# | 7 | `polish_answer` 调用 `writer()` | `custom`：polish 进度 |
# | 8 | `polish_answer` 返回 | `updates`：局部更新 |
# | 9 | 合并 `polish_answer` 更新 | `values`：最终 State |
# | — | `polish_answer → END` | Edge 不产生事件 |
    for event in graph.stream(
        {"topic": topic, "steps": [], "messages": []},
        stream_mode=["updates", "values", "custom"],
        version="v2",
    ):
        print(">>>>>>>>>>>>>>>>>>",type(event))
        print(
            json.dumps(
                event,
                ensure_ascii=False,
                indent=2,
                default=_event_json_default,
            )
        )

        event_type = str(event["type"])
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        data = event["data"]
        if event_type == "updates" and isinstance(data, dict):
            update_nodes.extend(str(name) for name in data)
        elif event_type == "custom" and isinstance(data, dict):
            custom_events.append(data)
        elif event_type == "values" and isinstance(data, dict):
            final_state = data

    messages = list(final_state["messages"])
    shared_answer_messages = [
        message for message in messages if message.id == "shared-answer"
    ]
    return {
        "event_counts": event_counts,
        "update_nodes": update_nodes,
        "custom_events": custom_events,
        "steps": final_state["steps"],
        "messages": [_message_summary(message) for message in messages],
        "same_id_message_count": len(shared_answer_messages),
        "answer": final_state["answer"],
        # draw_mermaid() 只生成 Mermaid 文本，不访问在线绘图服务。
        "mermaid": graph.get_graph().draw_mermaid(),
    }


# 启动命令：.venv/bin/python 5_langgraph_agentic_rag/part5_state_reducers_streaming.py
# 参数枚举：无命令行参数。
def main() -> int:
    result = run_demo()
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
