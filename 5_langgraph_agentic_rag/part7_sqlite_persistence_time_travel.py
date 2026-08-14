"""Part 7：SQLite Checkpointer、历史、恢复与时间旅行。

Part 3 的 InMemorySaver 只在当前进程内有效。
把 Part 3 的“进程内暂停/恢复”升级成“SQLite 持久化 + 任意 checkpoint 的 replay/fork
SqliteSaver     ->      将 State 和执行位置持久化到 SQLite
checkpoint_id   ->      每个 checkpoint 的唯一标识符,精确定位线程中的某个历史时刻
StateSnapshot   ->      描述某个 checkpoint 的 State、下一节点和父节点
graph.get_state()               ->      读取某个 checkpoint
graph.update_state()            ->      从某个 checkpoint 分叉，修改 State 并建立 fork 起点
graph.get_state_history()       ->      获取当前线程的所有历史 checkpoint

get_state       = 读取某个 checkpoint
get_state_history = 查找历史 checkpoint
代码执行逻辑如下：
replay =
旧 checkpoint.config
+ invoke(None)
fork =
旧 checkpoint.config
+ update_state(部分更新)
+ invoke(None)


本课把同一个小图编译到 SqliteSaver，依次演示：

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

    # with 是自动打开和关闭资源的同步语法  类似 try ... finally 的作用
    # with 结束时关闭数据库连接, 哪怕 graph.invoke()抛出异常。也会先关闭连接再把异常向外抛。
    with SqliteSaver.from_conn_string(str(database_path)) as checkpointer:
        graph = workflow.compile(checkpointer=checkpointer)
        first = graph.invoke(
            {"amount": 2, "operations": []},
            config=config,
        )
        second = graph.invoke({"amount": 3}, config=config)
    # 第一段生命周期：执行两轮后关闭 SQLite 连接。
    # {
    #     "amount": 3,
    #     "value": 5,
    #     "operations": ["add 2", "add 3"],
    # }

    with SqliteSaver.from_conn_string(str(database_path)) as checkpointer:
        # 相同的 SQLite 文件，因此能读到以前保存的 checkpoint 重新编译 Graph
        graph = workflow.compile(checkpointer=checkpointer)
        # 此 config 只有 thread_id，没有 checkpoint_id，获取该 thread 当前最新的 checkpoint
        recovered_before_third = dict(graph.get_state(config).values)

        # {
        #     "amount": 1, amount 没有 reducer，在新 State 中 amount 覆盖为 1
        #     "value": 6,
        #     "operations": ["add 2", "add 3", "add 1"],
        # }
        third = graph.invoke({"amount": 1}, config=config)

        # 获取第三轮之后的完整历史
        history = list(graph.get_state_history(config))

        # next(...) 是 Python 内置函数，负责从生成器表达式中取出第一个满足条件的元素
        # before_second.values == {
        #     "amount": 3,
        #     "value": 2,
        #     "operations": ["add 2"],
        # }
        before_second = next(
            snapshot
            for snapshot in history
            # 第二轮 Node 执行前”的 checkpoint
            if snapshot.values.get("value") == 2
            and snapshot.values.get("amount") == 3
            and snapshot.next == ("apply_increment",)
        )

        # before_second 是三条 checkpoint 历史的共同分叉点：
        # before_second：value=2, amount=3, next=apply_increment
        # ├─ 原始主线：+3 -> value=5 -> 第三轮 +1 -> value=6
        # ├─ replay 分支：重新执行 +3 -> value=5
        # └─ fork 分支：amount 改成 10 -> 执行 +10 -> value=12
        # None 表示没有新的外部 State 输入
        # 会新增一条分支，Replay 会重新执行旧 checkpoint 后的 Node，不是简单读取旧输出。
        # before_second 旧 checkpoint 没变，原始主线 value=6 没变
        replayed = graph.invoke(None, config=before_second.config)
        # 由于 before_second.next == ("apply_increment",) 重新执行 +3
        # replayed == {
        #     "amount": 3,
        #     "value": 5,
        #     "operations": ["add 2", "add 3"],
        # }

        # fork 先把旧 checkpoint 的 amount 改为 10，再从相同位置继续执行。
        # {
        #     "amount": 10,             # 新分支中 3 被覆盖为 10
        #     "value": 2,               # 没提供，保留
        #     "operations": ["add 2"],  # 没提供，保留
        # }
        fork_config = graph.update_state(
            before_second.config,
            {"amount": 10},
        )
        # 输入None 不覆盖继续执行
        forked = graph.invoke(None, config=fork_config)
        # forked == {
        #     "amount": 10,
        #     "value": 12,
        #     "operations": ["add 2", "add 10"],
        # }

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


# 启动命令：.venv/bin/python 5_langgraph_agentic_rag/part7_sqlite_persistence_time_travel.py [--database PATH]
# 参数枚举：--database PATH 可选，指定 SQLite 文件；默认为 runtime/checkpoint_demo.sqlite。
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
