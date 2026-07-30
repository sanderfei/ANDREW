"""Part 1：不用模型，先看懂 State、Node、Edge 和条件路由。

State     = 流程共享数据
Node      = 读取状态并返回部分更新
Edge      = 固定的下一步
Router    = 读取状态并选择分支
compile   = 把图定义变成可运行对象
invoke    = 使用一份初始状态执行一次完整流程

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


# TypedDict：给类型检查器和编辑器看，描述字典应该有哪些字段。
# total=False 表示类型层面允许只提供部分字段：
class LearningState(TypedDict, total=False):
    """节点之间共享的原始状态。"""

    question: str
    route: Literal["knowledge", "smalltalk"]
    answer: str
    steps: list[str]


# 没有返回 question，因为 LangGraph 会把这个结果作为“部分状态更新”合并回当前状态：
def classify_question(state: LearningState) -> LearningState:
    """Node 只返回需要更新的字段，不必复制整个 state。"""

    question = state["question"].strip().lower()
    smalltalk = question in {"你好", "您好", "hello", "hi"}
    return {
        "route": "smalltalk" if smalltalk else "knowledge",
        # 这里的 [*旧列表, 新元素] 会创建新列表，不会执行 state["steps"].append(...)
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


# State     = 流程共享数据
# Node      = 读取状态并返回部分更新（State 数据流转）
# Edge      = 固定的下一步
# Router    = 读取状态并选择分支
# compile   = 把图定义变成可运行对象
def build_graph():
    # 创建图的定义，并告诉 LangGraph：整张图使用 LearningState 作为状态结构。
    workflow = StateGraph(LearningState)
    # 注册节点：节点名称，实际执行的 Python 函数：
    workflow.add_node("classify_question", classify_question)
    workflow.add_node("answer_smalltalk", answer_smalltalk)
    workflow.add_node("explain_knowledge_route", explain_knowledge_route)
    # 固定边表示：图启动后，固定先执行 classify_question
    workflow.add_edge(START, "classify_question")
    # 条件边
    # classify_question 执行完成。
    # 把更新后的状态传给 choose_route。
    # 根据返回值查找目标节点。
    workflow.add_conditional_edges(
        "classify_question",
        choose_route,
        {
            # 需要注册，但不要求必须在 add_conditional_edges() 之前注册；
            # 只要在 workflow.compile() 之前注册完成即可。
            "smalltalk": "answer_smalltalk",
            "knowledge": "explain_knowledge_route",
        },
    )
    # 结束边：两个回答节点执行完成后，图就结束。
    workflow.add_edge("answer_smalltalk", END)
    workflow.add_edge("explain_knowledge_route", END)
    # StateGraph 是图的设计稿，compile() 返回真正可以运行的 CompiledStateGraph。
    return workflow.compile()


# workflow.add_node(...)  # 描述图
# workflow.compile()      # 生成可运行对象
# graph.invoke(...)       # 真正运行
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
