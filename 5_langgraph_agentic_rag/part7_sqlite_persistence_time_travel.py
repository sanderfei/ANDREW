"""Part 7：SQLite Checkpointer、历史、恢复与时间旅行。

Part 3 的 InMemorySaver 只在当前进程内有效。本课把同一个小图编译到
SqliteSaver，依次演示：

- 同一 thread_id 的多轮状态累积；
- 关闭并重新创建 Graph 后继续旧线程；
- get_state_history() 查看 checkpoint；
- 从旧 checkpoint replay；
- update_state() 创建分叉后执行另一条路径。

运行：
    .venv/bin/python \
      5_langgraph_agentic_rag/part7_sqlite_persistence_time_travel.py
"""

from __future__ import annotations

import argparse
import json
import operator
from pathlib import Path
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


PROJECT_DIR = Path(__file__).resolve().parent
OFFICIAL_SOURCES = [
    "https://docs.langchain.com/oss/python/langgraph/persistence",
    "https://docs.langchain.com/oss/python/langgraph/use-time-travel",
]


class CounterState(TypedDict, total=False):
    amount: int
    value: int
    operations: Annotated[list[str], operator.add]


def apply_increment(state: CounterState) -> CounterState:
    amount = int(state["amount"])
    return {
        "value": int(state.get("value", 0)) + amount,
        "operations": [f"add {amount}"],
    }


def build_counter_workflow() -> StateGraph:
    workflow = StateGraph(CounterState)
    workflow.add_node("apply_increment", apply_increment)
    workflow.add_edge(START, "apply_increment")
    workflow.add_edge("apply_increment", END)
    return workflow


def _config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def _checkpoint_id(config: dict[str, Any]) -> str:
    configurable = config.get("configurable", {})
    return str(configurable.get("checkpoint_id", ""))


def run_demo(
    database_path: Path,
    *,
    thread_id: str | None = None,
) -> dict[str, Any]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    active_thread_id = thread_id or f"sqlite-persistence-{uuid4().hex}"
    config = _config(active_thread_id)
    workflow = build_counter_workflow()

    # 第一段生命周期：执行两轮后关闭 SQLite 连接。
    with SqliteSaver.from_conn_string(str(database_path)) as checkpointer:
        graph = workflow.compile(checkpointer=checkpointer)
        first = graph.invoke(
            {"amount": 2, "operations": []},
            config=config,
        )
        second = graph.invoke({"amount": 3}, config=config)

    # 第二段生命周期：重新创建 checkpointer 和 Graph，仍能读取同一 thread。
    with SqliteSaver.from_conn_string(str(database_path)) as checkpointer:
        graph = workflow.compile(checkpointer=checkpointer)
        recovered_before_third = dict(graph.get_state(config).values)
        third = graph.invoke({"amount": 1}, config=config)
        history = list(graph.get_state_history(config))

        # 选中“第二轮 apply_increment 即将执行”的 checkpoint。
        before_second = next(
            snapshot
            for snapshot in history
            if snapshot.values.get("value") == 2
            and snapshot.values.get("amount") == 3
            and snapshot.next == ("apply_increment",)
        )

        # replay 会按当时的 amount=3 重新执行，结果仍是 5。
        replayed = graph.invoke(None, config=before_second.config)

        # fork 先把旧 checkpoint 的 amount 改为 10，再从相同位置继续执行。
        fork_config = graph.update_state(
            before_second.config,
            {"amount": 10},
        )
        forked = graph.invoke(None, config=fork_config)

        history_after_fork = list(graph.get_state_history(config))

    return {
        "database": str(database_path),
        "thread_id": active_thread_id,
        "first": first,
        "second": second,
        "recovered_after_graph_rebuild": recovered_before_third,
        "third": third,
        "history_count_before_fork": len(history),
        "selected_checkpoint_id": _checkpoint_id(before_second.config),
        "replayed_from_old_checkpoint": replayed,
        "fork_checkpoint_id": _checkpoint_id(fork_config),
        "forked_with_amount_10": forked,
        "history_count_after_fork": len(history_after_fork),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="演示 SQLite 持久化、checkpoint 历史和时间旅行"
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=PROJECT_DIR / "runtime" / "checkpoint_demo.sqlite",
    )
    args = parser.parse_args(argv)
    print(
        json.dumps(
            {
                "official_sources": OFFICIAL_SOURCES,
                "result": run_demo(args.database),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
