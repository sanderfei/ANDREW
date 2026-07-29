"""Part 5：State Reducer、消息更新、v2 Streaming 与图可视化。

这几个概念都围绕“状态如何变化、变化如何被观察”，因此放在同一课。
示例完全确定性，不调用模型和网络。

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
    topic: str
    # operator.add 表示每个 Node 返回的新 list 会追加，而不是覆盖旧 list。
    steps: Annotated[list[str], operator.add]
    # add_messages 既能追加消息，也能根据 message id 替换已有消息。
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


def write_draft(state: StreamingState) -> StreamingState:
    writer = get_stream_writer()
    writer({"stage": "draft", "detail": "正在生成确定性草稿"})
    return {
        "steps": ["write_draft"],
        "messages": [
            AIMessage(
                content=f"{state['topic']} 的草稿答案",
                id="shared-answer",
            )
        ],
    }


def polish_answer(state: StreamingState) -> StreamingState:
    writer = get_stream_writer()
    writer({"stage": "polish", "detail": "正在替换同 ID 的草稿消息"})
    final_answer = (
        f"{state['topic']}：Node 返回部分状态，Reducer 决定新旧值如何合并。"
    )
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


def run_demo(topic: str = "LangGraph State") -> dict[str, Any]:
    graph = build_streaming_graph()
    event_counts: dict[str, int] = {}
    update_nodes: list[str] = []
    custom_events: list[dict[str, Any]] = []
    final_state: StreamingState = {}

    for event in graph.stream(
        {"topic": topic, "steps": [], "messages": []},
        stream_mode=["updates", "values", "custom"],
        version="v2",
    ):
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
