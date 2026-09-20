"""Part 11：静态并行、fan-in、Reducer、Send 动态 fan-out 与并发上限。

执行图：

START -> plan -> read_docs -----\
                 read_examples --+-> merge_sources -> Send(analyze_subject x N)
                                                       -> finalize -> END

本课还会运行一个错误图，证明并行 Node 同时覆盖无 Reducer 字段会触发
InvalidUpdateError，而不是由最后完成的 Node 随机获胜。
"""

from __future__ import annotations

import argparse
import json
import operator
import threading
import time
from typing import Annotated, Any, TypedDict

from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send


# 多个任务都写同一个列表字段时，用 Annotated[..., operator.add] 累加结果，等价于 Python 的 旧列表 + 新列表。
# 多个并行节点写同一个无 Reducer 字段，会触发 InvalidUpdateError
class ParallelState(TypedDict, total=False):
    topic: str
    subjects: list[str]
    static_results: Annotated[list[dict[str, Any]], operator.add]
    analyses: Annotated[list[dict[str, Any]], operator.add]
    merged_context: str
    answer: str


class WorkerState(TypedDict):
    subject: str


def _timed_result(name: str, detail: str, delay: float = 0.04) -> dict[str, Any]:
    started = time.perf_counter()
    thread_id = threading.get_ident()
    time.sleep(delay)
    finished = time.perf_counter()
    return {
        "name": name,
        "detail": detail,
        "thread_id": thread_id,
        "started": started,
        "finished": finished,
    }


def plan(state: ParallelState) -> ParallelState:
    return {
        "subjects": ["State", "Reducer", "Send"],
        "static_results": [],
        "analyses": [],
    }


def read_docs(state: ParallelState) -> ParallelState:
    return {
        "static_results": [_timed_result("docs", f"{state['topic']} 的官方概念说明")]
    }


def read_examples(state: ParallelState) -> ParallelState:
    return {
        "static_results": [
            _timed_result("examples", f"{state['topic']} 的本地代码示例")
        ]
    }


def merge_sources(state: ParallelState) -> ParallelState:
    ordered = sorted(state["static_results"], key=lambda item: item["name"])
    return {"merged_context": " | ".join(item["detail"] for item in ordered)}


# state["subjects"] == ["State", "Reducer", "Send"]
# 返回三个 Send 对象
# [
#     Send("analyze_subject", {"subject": "State"}),
#     Send("analyze_subject", {"subject": "Reducer"}),
#     Send("analyze_subject", {"subject": "Send"}),
# ]
# Send 动态 fan-out 的例子：每个 subject 都会生成一个 Send，携带不同的输入 State。
# Send(
#     "analyze_subject",      # 要执行的节点
#     {"subject": "State"},   # 这一次任务收到的输入
# )
def fan_out_subjects(state: ParallelState) -> list[Send]:
    """运行时才知道任务数量，因此返回一组不同输入的 Send。"""

    return [
        Send("analyze_subject", {"subject": subject}) for subject in state["subjects"]
    ]


def analyze_subject(state: WorkerState) -> dict[str, list[dict[str, Any]]]:
    result = _timed_result(
        state["subject"],
        f"已分析 {state['subject']}",
        delay=0.02,
    )
    return {"analyses": [result]}


def finalize(state: ParallelState) -> ParallelState:
    subjects = sorted(item["name"] for item in state["analyses"])
    return {
        "answer": (
            f"静态来源={len(state['static_results'])}；"
            f"动态任务={','.join(subjects)}；"
            f"上下文={state['merged_context']}"
        )
    }


def build_parallel_graph():
    workflow = StateGraph(ParallelState)
    workflow.add_node("plan", plan)
    workflow.add_node("read_docs", read_docs)
    workflow.add_node("read_examples", read_examples)
    workflow.add_node("merge_sources", merge_sources)
    workflow.add_node("analyze_subject", analyze_subject)
    workflow.add_node("finalize", finalize)

    workflow.add_edge(START, "plan")
    # 同一个 superstep 同时调度两个 Node，形成静态 fan-out。
    # 静态并行 fan-out：plan 后同时调度 read_docs 和 read_examples。
    workflow.add_edge("plan", "read_docs")
    workflow.add_edge("plan", "read_examples")
    # list[str] 形式的起点表示两个 Node 都完成后才执行 merge_sources。
    workflow.add_edge(["read_docs", "read_examples"], "merge_sources")
    # state["subjects"] == ["State", "Reducer", "Send"]
    workflow.add_conditional_edges(
        "merge_sources",
        fan_out_subjects,
        ["analyze_subject"],
    )
    workflow.add_edge("analyze_subject", "finalize")
    workflow.add_edge("finalize", END)
    return workflow.compile()


def _has_overlap(results: list[dict[str, Any]]) -> bool:
    if len(results) < 2:
        return False
    for index, left in enumerate(results):
        for right in results[index + 1 :]:
            if max(left["started"], right["started"]) < min(
                left["finished"], right["finished"]
            ):
                return True
    return False


def conflict_demo() -> dict[str, str]:
    """并行覆盖同一个 LastValue 字段，捕获框架给出的冲突错误。"""

    # 同一轮执行中， Node branch_a 和 branch_b 都更新了 value，而这个字段没有定义如何合并多个结果。
    class ConflictState(TypedDict, total=False):
        value: str

    def branch_a(_state: ConflictState) -> ConflictState:
        return {"value": "A"}

    def branch_b(_state: ConflictState) -> ConflictState:
        return {"value": "B"}

    workflow = StateGraph(ConflictState)
    # 两个子节点 Node
    workflow.add_node("branch_a", branch_a)
    workflow.add_node("branch_b", branch_b)
    # 两个子任务 同时执行
    workflow.add_edge(START, "branch_a")
    workflow.add_edge(START, "branch_b")
    workflow.add_edge("branch_a", END)
    workflow.add_edge("branch_b", END)

    try:
        workflow.compile().invoke({})
    except InvalidUpdateError as exc:
        return {"error_type": type(exc).__name__, "detail": str(exc)}
    raise AssertionError("缺少 Reducer 的并行写入应该产生 InvalidUpdateError。")


def run_demo(max_concurrency: int = 2) -> dict[str, Any]:
    graph = build_parallel_graph()
    result = graph.invoke(
        {
            "topic": "LangGraph 并行执行",
            "static_results": [],
            "analyses": [],
        },
        # 限制同时执行的任务数
        config={"max_concurrency": max_concurrency},
    )
    static_results = sorted(result["static_results"], key=lambda item: item["name"])
    analyses = sorted(result["analyses"], key=lambda item: item["name"])

    output = {
        "max_concurrency": max_concurrency,
        "static_parallel": {
            "overlap_observed": _has_overlap(static_results),
            "results": static_results,
        },
        "dynamic_send": {
            "task_count": len(analyses),
            "overlap_observed": _has_overlap(analyses),
            "results": analyses,
        },
        "final_answer": result["answer"],
        "conflict_without_reducer": conflict_demo(),
        "semantics": [
            "同一 superstep 的并行更新先分别产生，再由 Reducer 合并。",
            "Send 为每个动态任务携带自己的输入 State。",
            "max_concurrency 限制同时执行的任务数，不改变 Graph 拓扑。",
        ],
    }
    assert output["dynamic_send"]["task_count"] == 3
    assert output["conflict_without_reducer"]["error_type"] == "InvalidUpdateError"
    return output


# 启动命令：
#   .venv/bin/python 5_langgraph_agentic_rag/part11_parallel_send.py
#   .venv/bin/python 5_langgraph_agentic_rag/part11_parallel_send.py --max-concurrency 1
# 参数枚举：--max-concurrency 1 / 2（默认）/ 3。
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LangGraph 并行分支与 Send 教学")
    parser.add_argument(
        "--max-concurrency",
        type=int,
        choices=(1, 2, 3),
        default=2,
        help="最大并发任务数",
    )
    args = parser.parse_args(argv)
    print(json.dumps(run_demo(args.max_concurrency), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
