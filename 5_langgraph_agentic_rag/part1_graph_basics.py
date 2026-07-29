"""Part 1：不用模型，先看懂 State、Node、Edge 和条件路由。

运行：
    .venv/bin/python 5_langgraph_agentic_rag/part1_graph_basics.py
"""

from __future__ import annotations

import json
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


OFFICIAL_SOURCE = (
    "https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph"
)


class LearningState(TypedDict, total=False):
    """节点之间共享的原始状态。"""

    question: str
    route: Literal["knowledge", "smalltalk"]
    answer: str
    steps: list[str]


def classify_question(state: LearningState) -> LearningState:
    """Node 只返回需要更新的字段，不必复制整个 state。"""

    question = state["question"].strip().lower()
    smalltalk = question in {"你好", "您好", "hello", "hi"}
    return {
        "route": "smalltalk" if smalltalk else "knowledge",
        "steps": [*state.get("steps", []), "classify_question"],
    }


def choose_route(
    state: LearningState,
) -> Literal["knowledge", "smalltalk"]:
    """条件边读取 state，然后返回下一节点名称。"""

    return state["route"]


def answer_smalltalk(state: LearningState) -> LearningState:
    return {
        "answer": "你好，下一步可以把问题交给知识库检索。",
        "steps": [*state.get("steps", []), "answer_smalltalk"],
    }


def explain_knowledge_route(state: LearningState) -> LearningState:
    return {
        "answer": (
            f"问题“{state['question']}”被路由到 knowledge；"
            "Part 2 会在这个节点位置接入真实 Chroma Retriever Tool。"
        ),
        "steps": [*state.get("steps", []), "explain_knowledge_route"],
    }


def build_graph():
    workflow = StateGraph(LearningState)
    workflow.add_node("classify_question", classify_question)
    workflow.add_node("answer_smalltalk", answer_smalltalk)
    workflow.add_node("explain_knowledge_route", explain_knowledge_route)
    workflow.add_edge(START, "classify_question")
    workflow.add_conditional_edges(
        "classify_question",
        choose_route,
        {
            "smalltalk": "answer_smalltalk",
            "knowledge": "explain_knowledge_route",
        },
    )
    workflow.add_edge("answer_smalltalk", END)
    workflow.add_edge("explain_knowledge_route", END)
    return workflow.compile()


def main() -> int:
    graph = build_graph()
    results = [
        graph.invoke({"question": "你好", "steps": []}),
        graph.invoke(
            {
                "question": "本地默认 Embedding 模型是什么？",
                "steps": [],
            }
        ),
    ]
    print(
        json.dumps(
            {
                "official_source": OFFICIAL_SOURCE,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

