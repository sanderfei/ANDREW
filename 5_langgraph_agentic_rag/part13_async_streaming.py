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
    return {
        "research_notes": [
            await _fetch_note("docs", state["topic"], config)
        ]
    }


async def fetch_examples(state: AsyncState, config: RunnableConfig) -> AsyncState:
    return {
        "research_notes": [
            await _fetch_note("examples", state["topic"], config)
        ]
    }


def build_async_graph(checkpointer: InMemorySaver):
    # FakeListChatModel 的流式实现会逐字符产生 AIMessageChunk，全程不调用网络。
    model = FakeListChatModel(responses=["异步资料汇总完成"])

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
        await graph.ainvoke({"count": 0}, config={"recursion_limit": 3})
    except GraphRecursionError as exc:
        return {
            "error_type": type(exc).__name__,
            "recursion_limit": 3,
            "detail": str(exc),
        }
    raise AssertionError("无限回路应该被 recursion_limit 终止。")


async def node_timeout_demo() -> dict[str, Any]:
    class TimeoutState(TypedDict, total=False):
        status: str

    async def slow_node(_state: TimeoutState) -> TimeoutState:
        await asyncio.sleep(0.05)
        return {"status": "finished"}

    workflow = StateGraph(TimeoutState)
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
        "tags": ["lesson", "async"],
        "metadata": {"lesson": "part13", "purpose": "offline-demo"},
    }
    event_summaries: list[dict[str, Any]] = []
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
        event_type = str(event["type"])
        event_counts[event_type] += 1
        summary = _event_summary(event)
        event_summaries.append(summary)
        if event_type == "messages":
            token_chunks.append(summary["content"])
        elif event_type == "values" and event["ns"] == ():
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
