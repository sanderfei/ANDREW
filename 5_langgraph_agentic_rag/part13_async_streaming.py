"""Part 13：异步 Node、并发 astream、完整 v2 StreamMode 与运行配置。

本课覆盖：

- ``async def`` Node、``ainvoke``、``astream``；
- ``RunnableConfig`` 的 thread_id、tags、metadata、max_concurrency；
- values/updates/messages/custom/checkpoints/tasks/debug 事件；
- ``messages`` 模式产生的模型 Token Chunk；
- ``recursion_limit`` 对无限 Graph 回路的最后保护。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import operator
import time
from collections import Counter
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.errors import GraphRecursionError, NodeTimeoutError
from langgraph.graph import END, START, StateGraph


class AsyncState(TypedDict, total=False):
    topic: str
    research_notes: Annotated[list[dict[str, Any]], operator.add]
    answer: str


async def _fetch_note(
    source: str,
    topic: str,
    config: RunnableConfig,
) -> dict[str, Any]:
    # writer(...) 把数据送进 LangGraph 当前这次运行的内存事件队列
    # 再由外面的 graph.astream(...) 输出，让 async for 读到。 队列由框架管理
    # writer 写入的数据就是读取就是 custom 类型的 event 事件类型
    writer = get_stream_writer()
    writer(
        {
            "stage": "fetch:start",
            "source": source,
            "tags": list(config.get("tags", [])),
            "lesson": config.get("metadata", {}).get("lesson"),
        }
    )
    started = time.perf_counter()
    await asyncio.sleep(0.03)
    finished = time.perf_counter()
    writer({"stage": "fetch:finish", "source": source})
    return {
        "source": source,
        "content": f"{source} 提供了 {topic} 的资料",
        "started": started,
        "finished": finished,
    }


async def fetch_docs(state: AsyncState, config: RunnableConfig) -> AsyncState:
    return {"research_notes": [await _fetch_note("docs", state["topic"], config)]}


async def fetch_examples(state: AsyncState, config: RunnableConfig) -> AsyncState:
    return {"research_notes": [await _fetch_note("examples", state["topic"], config)]}


def build_async_graph(checkpointer: InMemorySaver):
    # LangChain 提供的“模拟聊天模型”，用于测试和教学
    # FakeListChatModel 的流式实现会逐字符产生 AIMessageChunk，全程不调用网络。
    model = FakeListChatModel(responses=["异步资料汇总完成"])

    # 定义并注册异步节点
    # 等到运行这张包含异步节点的图时，再使用异步接口：如下代码async for event in graph.astream
    async def generate_answer(state: AsyncState) -> AsyncState:
        context = "；".join(
            item["content"]
            for item in sorted(state["research_notes"], key=lambda item: item["source"])
        )
        response = await model.ainvoke(f"主题={state['topic']}；资料={context}")
        return {"answer": str(response.content)}

    workflow = StateGraph(AsyncState)
    workflow.add_node("fetch_docs", fetch_docs)
    workflow.add_node("fetch_examples", fetch_examples)
    workflow.add_node("generate_answer", generate_answer)
    workflow.add_edge(START, "fetch_docs")
    workflow.add_edge(START, "fetch_examples")
    workflow.add_edge(["fetch_docs", "fetch_examples"], "generate_answer")
    workflow.add_edge("generate_answer", END)
    return workflow.compile(checkpointer=checkpointer)


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    event_type = str(event["type"])
    data = event["data"]
    summary: dict[str, Any] = {
        "type": event_type,
        "ns": list(event["ns"]),
    }
    if event_type == "messages":
        chunk, metadata = data
        summary.update(
            {
                "content": str(chunk.content),
                "node": metadata.get("langgraph_node"),
            }
        )
    elif event_type == "custom":
        summary["data"] = data
    elif event_type == "updates" and isinstance(data, dict):
        summary["nodes"] = sorted(str(key) for key in data)
    elif event_type == "values" and isinstance(data, dict):
        summary["state_keys"] = sorted(str(key) for key in data)
    elif isinstance(data, dict):
        summary["data_keys"] = sorted(str(key) for key in data)
        if "name" in data:
            summary["name"] = str(data["name"])
        if "error" in data:
            summary["has_error"] = data["error"] is not None
    else:
        summary["data_type"] = type(data).__name__
    return summary


def _has_overlap(notes: list[dict[str, Any]]) -> bool:
    if len(notes) != 2:
        return False
    left, right = notes
    return max(left["started"], right["started"]) < min(
        left["finished"], right["finished"]
    )


async def recursion_limit_demo() -> dict[str, Any]:
    """用没有退出条件的自环，演示 Graph 的 superstep 上限。

    本例 count 从 0 开始，loop 执行三轮后依次变为 1、2、3；还要继续下一轮时，
    recursion_limit=3 使框架抛出 GraphRecursionError。它限制图的执行轮数，
    不是 Python 函数递归深度，也不是每个节点各自允许执行三次。
    不显式传 recursion_limit 仍有框架默认上限，并不代表可以无限执行。

    如果在 loop -> loop 之外，再添加 workflow.add_edge("loop", END)：
    - 可以正常编译。两条普通边都无条件生效，框架不需要在其中二选一。
    - END 是结束标记，不是会取消其他分支的全局退出指令；自环仍安排下一轮 loop。
    - 因此仍会循环到 recursion_limit，不能靠额外添加一条 END 边退出。

    若想在 count 达到 3 时正常结束，应替换 loop 的普通出边，改用条件路由：
        def route(state: LoopState):
            return END if state["count"] >= 3 else "loop"

        workflow.add_conditional_edges("loop", route, ["loop", END])
    不要同时保留无条件的 loop -> loop，否则即使路由选择 END，自环仍会继续。
    条件退出示例运行时可设置 recursion_limit=10，为正常结束留足步数；
    下面的实际代码保留无限自环，专门验证异常保护。
    """

    class LoopState(TypedDict, total=False):
        count: int

    async def loop(state: LoopState) -> LoopState:
        await asyncio.sleep(0)
        return {"count": state.get("count", 0) + 1}

    workflow = StateGraph(LoopState)
    workflow.add_node("loop", loop)
    workflow.add_edge(START, "loop")
    workflow.add_edge("loop", "loop")
    graph = workflow.compile()
    try:
        # 启动时，设置最多运行 3 个执行轮次
        await graph.ainvoke({"count": 0}, config={"recursion_limit": 3})
    except GraphRecursionError as exc:
        return {
            "error_type": type(exc).__name__,
            "recursion_limit": 3,
            "detail": str(exc),
        }
    raise AssertionError("无限回路应该被 recursion_limit 终止。")


async def node_timeout_demo() -> dict[str, Any]:
    """节点超时示例：等待 50 毫秒，但只允许本次节点执行尝试运行 10 毫秒。

    timeout 限制绑定节点的一次执行尝试，节点内部的前置处理、await 调用、
    返回前的处理都计入同一时间预算，不是只计算模型请求耗时。
    before_model 是否包含在内，要看它实际位于哪一层：
    - 普通节点内部调用前置处理，再 await model.ainvoke(...)：前置处理计入该节点超时。
    - 当前 create_agent() 将 before_model 注册为独立节点；只限制内部 model 节点时，
      不包含之前那个 before_model 节点，model 内部的 wrap_model_call 则包含在内。
    - 外层节点 await agent.ainvoke(...)：限制外层节点会覆盖整个 Agent 调用，
      包括内部 before_model、模型调用和其他尚未完成的内部流程。
    离线验证：before_model 等待 80 毫秒，只给内部 model 设置 30 毫秒超时可成功；
    改为给调用整个 Agent 的外层节点设置 30 毫秒超时，会触发 NodeTimeoutError。
    超时依赖 asyncio 取消；阻塞事件循环的同步代码可能使超时检测延迟。
    """

    class TimeoutState(TypedDict, total=False):
        status: str

    async def slow_node(_state: TimeoutState) -> TimeoutState:
        await asyncio.sleep(0.05)
        return {"status": "finished"}

    workflow = StateGraph(TimeoutState)
    # 数字 timeout 表示单次执行尝试的 run_timeout，单位为秒；本例在异步等待中超时。
    workflow.add_node("slow_node", slow_node, timeout=0.01)
    workflow.add_edge(START, "slow_node")
    workflow.add_edge("slow_node", END)
    try:
        await workflow.compile().ainvoke({})
    except NodeTimeoutError as exc:
        return {
            "error_type": type(exc).__name__,
            "node_timeout_seconds": 0.01,
            "detail": str(exc),
        }
    raise AssertionError("slow_node 应该被 Node timeout 终止。")


async def run_demo(max_concurrency: int = 2) -> dict[str, Any]:
    checkpointer = InMemorySaver()
    graph = build_async_graph(checkpointer)
    config: RunnableConfig = {
        "configurable": {"thread_id": "async-stream-demo"},
        "max_concurrency": max_concurrency,
        "tags": ["lesson", "async"],  # 给这次运行附加标签
        "metadata": {
            "lesson": "part13",
            "purpose": "offline-demo",
        },  # 附加课程名、用途等信息
    }
    event_summaries: list[dict[str, Any]] = []
    # Counter 的特点是：不存在的键，读取计数时默认得到 0。因此可以直接执行：
    # event_counts["custom"] += 1
    event_counts: Counter[str] = Counter()
    token_chunks: list[str] = []
    final_state: AsyncState = {}

    async for event in graph.astream(
        {"topic": "LangGraph Streaming", "research_notes": []},
        config=config,
        stream_mode=[
            "values",
            "updates",
            "messages",
            "custom",
            "checkpoints",
            "tasks",
        ],
        version="v2",
    ):
        # 事件类型，例如 updates、values、custom
        event_type = str(event["type"])
        event_counts[event_type] += 1
        summary = _event_summary(event)
        event_summaries.append(summary)
        # 遇到 messages，就收集文本：
        if event_type == "messages":
            token_chunks.append(summary["content"])
        elif event_type == "values" and event["ns"] == ():
            # 遇到根图的 values，就保存当前 State：
            final_state = event["data"]

    # debug 会包含更详细的 checkpoint/task 信息，教学输出只统计，不打印全部载荷。
    debug_count = 0
    debug_config: RunnableConfig = {
        "configurable": {"thread_id": "async-debug-demo"},
        "max_concurrency": max_concurrency,
    }
    async for _event in graph.astream(
        {"topic": "Debug", "research_notes": []},
        config=debug_config,
        stream_mode="debug",
        version="v2",
    ):
        debug_count += 1

    notes = sorted(final_state["research_notes"], key=lambda item: item["source"])
    snapshot = await graph.aget_state(config)
    result = {
        "config": {
            "thread_id": config["configurable"]["thread_id"],
            "tags": config["tags"],
            "metadata": config["metadata"],
            "max_concurrency": max_concurrency,
        },
        "parallel_nodes": {
            "overlap_observed": _has_overlap(notes),
            "notes": notes,
        },
        "stream": {
            "event_counts": dict(sorted(event_counts.items())),
            "token_chunks": token_chunks,
            "joined_tokens": "".join(token_chunks),
            "events": event_summaries,
            "debug_event_count": debug_count,
        },
        "final_state": final_state,
        "snapshot": {
            "next": list(snapshot.next),
            "answer": snapshot.values["answer"],
        },
        "recursion_control": await recursion_limit_demo(),
        "timeout_control": await node_timeout_demo(),
    }
    assert result["stream"]["joined_tokens"] == "异步资料汇总完成"
    assert result["snapshot"]["next"] == []
    assert result["recursion_control"]["error_type"] == "GraphRecursionError"
    assert result["timeout_control"]["error_type"] == "NodeTimeoutError"
    return result


# 启动命令：
#   .venv/bin/python 5_langgraph_agentic_rag/part13_async_streaming.py
#   .venv/bin/python 5_langgraph_agentic_rag/part13_async_streaming.py --max-concurrency 1
# 参数枚举：--max-concurrency 1 / 2（默认）。
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LangGraph 异步与完整 Streaming 教学")
    parser.add_argument(
        "--max-concurrency",
        type=int,
        choices=(1, 2),
        default=2,
        help="异步并行 Node 的最大并发数",
    )
    args = parser.parse_args(argv)
    print(
        json.dumps(
            asyncio.run(run_demo(args.max_concurrency)),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
