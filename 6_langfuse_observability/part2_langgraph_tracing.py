"""Part 2：通过 CallbackHandler 追踪目录 5 Part 13 的异步图。

- 本例 langfuse langGraph组合，实现逻辑如下：
- CallbackHandler 放入 config["callbacks"]，自动记录图、节点和模型调用，不修改 State。
- LangChain Core 定义回调接口，LangGraph／LangChain 执行时触发回调；Langfuse handler
  接收开始、结束、错误等通知，创建或更新 observation，由 SDK 上报、平台保存展示。
  追踪在执行过程中记录，无需在 async for 循环中手动上报。

- session_id 聚合多次调用的 Trace；
- trace_id 标识一次调用，由 SDK 自动生成。
- 本例独立运行时，每次正常执行 --mode langfuse 都创建一条新 Trace。
  使用相同的 --session-id wf-session 运行两次，会产生两个不同的 trace_id，
  并归入同一个 Session；Sessions 页面中的 Total traces 显示累计的 Trace 数量。
- 一条 Trace 内包含多个 observation：本例一次正常运行产生 6 条，分别是
  part2-langgraph、LangGraph、fetch_docs、fetch_examples、generate_answer 和 FakeListChatModel。
  这些 observation 共享本次运行的 trace_id，不会各自创建一条 Trace。
- thread_id 用于 LangGraph 检查点；本例与 session_id 共用字符串，没有自动绑定。

- 先进入 propagate_attributes，再创建根 observation；图和模型记录继承会话及追踪上下文。
- get_current_trace_id() 只读取已有 Trace ID。
- 两条 START 普通边都生效；本例 max_concurrency=2，两个资料节点并发执行，汇合后回答。
- research_notes 使用 operator.add 合并两个节点的列表更新；answer 使用覆盖更新。

- astream 提供异步事件流，async for 逐条处理；并发节点间的事件先后顺序可能变化。
- event类型：values 是完整 State，updates 是节点部分更新；messages 是模型片段，custom 是自定义进度。
- v2 事件为 {"type": ..., "ns": ..., "data": ...}；ns=() 表示根图。
  messages 的 data 为 (消息片段, metadata)，读取片段 content 后拼接回答。
- writer 的 custom 事件由 astream 消费，与 CallbackHandler 上报 Langfuse 是不同通道。

- root.update(output=final_state) 记录最终状态到根 observation，不更新图的 State。
- FakeListChatModel 返回固定回答，逐字符输出；片段数不是真实 Token 用量，也无模型费用。
- 每次新建 InMemorySaver，不恢复上次进程的 State；offline 不上报，trace_id 为 None。
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import nullcontext
import json
import sys
from uuid import uuid4

from _runtime import PROJECT_ROOT, add_mode_argument, open_client, require_env

sys.path.insert(0, str(PROJECT_ROOT / "5_langgraph_agentic_rag"))
from langgraph.checkpoint.memory import InMemorySaver
from part13_async_streaming import build_async_graph


# 流程：准备客户端与追踪 → 并发取资料 → 模拟模型回答 → 收集事件 → 更新根输出。
# 平台模式退出 open_client 时 flush、shutdown。
async def run_demo(mode: str = "offline", session_id: str | None = None) -> dict:
    session_id = session_id or f"langfuse-lesson-{uuid4().hex}"
    with open_client(mode) as client:
        callbacks = []

        # 离线模式使用空上下文。
        attributes = nullcontext()
        root_context = nullcontext()
        if client is not None:
            from langfuse import propagate_attributes
            from langfuse.langchain import CallbackHandler

            # 回调自动记录图和模型执行。
            callbacks = [CallbackHandler(public_key=require_env("LANGFUSE_PUBLIC_KEY"))]
            
            # propagate_attributes() 是 Langfuse 提供的“属性传播”功能：
            # 让一段执行范围内创建的观测记录，自动带上公共属性。 这些属性方便你按用户、会话或课程筛选记录
            # 向后续观测记录传播会话属性。公共属性设置一次，后续观测记录自动继承，无需每个 Span 都重复填写
            attributes = propagate_attributes(
                session_id=session_id,
                user_id="tutorial-user",
                tags=["lesson", "langgraph"],
                metadata={"lesson": "part2"},
            )
            # 创建根观测上下文。
            root_context = client.start_as_current_observation(
                name="part2-langgraph",
                as_type="agent", #智能体的决策、调度过程
                input={"topic": "Langfuse 追踪 LangGraph"},
            )

        graph = build_async_graph(InMemorySaver())
        # callbacks 只观察执行；thread_id 对应检查点。
        config = {
            "configurable": {"thread_id": session_id},
            "callbacks": callbacks,
            "tags": ["lesson", "async"],
            "metadata": {"lesson": "langfuse-part2"},
            "max_concurrency": 2,
        }
        counts = Counter()
        chunks = []
        final_state = {}

        # 先进入属性上下文，再进入根观测上下文；退出顺序相反。等价如下执行
# with attributes:                   # 先启用公共属性
#     with root_context as root:     # 再创建根 observation
#         # 执行 LangGraph
        with attributes, root_context as root:
            async for event in graph.astream(
                {"topic": "Langfuse 追踪 LangGraph", "research_notes": []},
                config=config,
                stream_mode=["updates", "values", "messages", "custom"],
                version="v2",
            ):
                counts[event["type"]] += 1
                if event["type"] == "values" and event["ns"] == ():
                    final_state = event["data"]
                elif event["type"] == "messages":
                    chunks.append(str(event["data"][0].content))
            trace_id = client.get_current_trace_id() if client else None
            if root is not None:
                root.update(output=final_state)
        return {
            "mode": mode,
            "session_id": session_id,
            "trace_id": trace_id,
            "event_counts": dict(counts),
            "streamed_answer": "".join(chunks),
            "final_state": final_state,
            "model": "FakeListChatModel；没有真实模型费用或真实 token 用量统计",
        }


# 启动命令：.venv/bin/python 6_langfuse_observability/part2_langgraph_tracing.py
# 平台模式：同上追加 --mode langfuse --session-id lesson-session
# 参数枚举：--mode offline（默认）/ langfuse；--session-id 任意会话标识（默认生成）。
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_mode_argument(parser)
    parser.add_argument("--session-id")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(run_demo(args.mode, args.session_id))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
