"""L13：区分 Agent State、Runtime Context 与跨线程 Store。

本课完全离线，使用预设 Tool Call 的 Fake ChatModel，重点观察运行时数据边界：

State
    当前 thread 的消息和可变执行状态，由 checkpointer 保存。
Context
    单次 invoke 注入的 user_id、权限等依赖，不会自动写入 State。
Store
    按 namespace/key 保存跨 thread 数据；InMemoryStore 仅跨线程，不跨进程。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command
from typing_extensions import NotRequired

from _offline_chat_model import ToolCallingFakeChatModel


@dataclass(frozen=True)
class UserContext:
    """本次运行的静态依赖；同一个 Agent 每次 invoke 都可以传不同 Context。"""

    user_id: str
    permissions: tuple[str, ...]


class MemoryAgentState(AgentState):
    """在标准 messages State 外增加 Tool 可以更新的业务字段。"""

    last_memory_key: NotRequired[str]


def _thread_id(runtime: ToolRuntime[UserContext, dict[str, Any]]) -> str:
    configurable = runtime.config.get("configurable", {})
    return str(configurable.get("thread_id", "unknown-thread"))


def _require_permission(
    runtime: ToolRuntime[UserContext, dict[str, Any]], permission: str
) -> None:
    if permission not in runtime.context.permissions:
        raise PermissionError(f"用户缺少权限: {permission}")


@tool
def remember_preference(
    key: str,
    value: str,
    runtime: ToolRuntime[UserContext, MemoryAgentState],
) -> Command:
    """把当前用户的一项偏好写入跨线程 Store。"""

    _require_permission(runtime, "memory:write")
    if runtime.store is None:
        raise RuntimeError("Agent 未配置 Store。")

    namespace = ("users", runtime.context.user_id, "preferences")
    runtime.store.put(
        namespace,
        key,
        {
            "value": value,
            "source_thread": _thread_id(runtime),
            "message_count_when_written": len(runtime.state.get("messages", [])),
        },
    )
    content = f"已为 {runtime.context.user_id} 记录 {key}={value}"
    # Tool 返回 Command 时，除了业务 State 更新，还必须补齐本次 tool_call 的 ToolMessage。
    return Command(
        update={
            "last_memory_key": key,
            "messages": [
                ToolMessage(
                    content=content,
                    tool_call_id=runtime.tool_call_id or "missing-tool-call-id",
                )
            ],
        }
    )


@tool
def recall_preference(
    key: str,
    runtime: ToolRuntime[UserContext, dict[str, Any]],
) -> str:
    """从跨线程 Store 读取当前用户的一项偏好。"""

    _require_permission(runtime, "memory:read")
    if runtime.store is None:
        raise RuntimeError("Agent 未配置 Store。")

    namespace = ("users", runtime.context.user_id, "preferences")
    memory = runtime.store.get(namespace, key)
    if memory is None:
        return f"{runtime.context.user_id} 尚未保存 {key}"
    return json.dumps(memory.value, ensure_ascii=False, sort_keys=True)


def _scripted_model() -> ToolCallingFakeChatModel:
    """三次 invoke：用户 A 写、用户 A 跨线程读、用户 B 隔离读取。"""

    return ToolCallingFakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "remember_preference",
                        "args": {"key": "default_city", "value": "上海"},
                        "id": "write-memory-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="偏好已经保存。"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "recall_preference",
                        "args": {"key": "default_city"},
                        "id": "read-memory-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="已经从长期记忆读取默认城市。"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "recall_preference",
                        "args": {"key": "default_city"},
                        "id": "read-memory-2",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="该用户没有保存默认城市。"),
        ]
    )


def _tool_messages(messages: list[BaseMessage]) -> list[str]:
    return [str(message.content) for message in messages if isinstance(message, ToolMessage)]


def run_demo() -> dict[str, Any]:
    checkpointer = InMemorySaver()
    store = InMemoryStore()
    agent = create_agent(
        model=_scripted_model(),
        tools=[remember_preference, recall_preference],
        state_schema=MemoryAgentState,
        context_schema=UserContext,
        checkpointer=checkpointer,
        store=store,
    )

    user_a_context = UserContext(
        user_id="user-a",
        permissions=("memory:read", "memory:write"),
    )
    user_b_context = UserContext(
        user_id="user-b",
        permissions=("memory:read",),
    )
    write_config = {"configurable": {"thread_id": "thread-write"}}
    read_config = {"configurable": {"thread_id": "thread-read"}}
    isolated_config = {"configurable": {"thread_id": "thread-other-user"}}

    write_result = agent.invoke(
        {"messages": [{"role": "user", "content": "记住我的默认城市是上海"}]},
        config=write_config,
        context=user_a_context,
    )
    read_result = agent.invoke(
        {"messages": [{"role": "user", "content": "我的默认城市是什么？"}]},
        config=read_config,
        context=user_a_context,
    )
    isolated_result = agent.invoke(
        {"messages": [{"role": "user", "content": "我的默认城市是什么？"}]},
        config=isolated_config,
        context=user_b_context,
    )

    memory = store.get(("users", "user-a", "preferences"), "default_city")
    if memory is None:
        raise AssertionError("user-a 的长期记忆没有写入 Store。")

    write_state = agent.get_state(write_config).values
    read_state = agent.get_state(read_config).values
    user_a_memories = store.search(("users", "user-a", "preferences"))
    result = {
        "state": {
            "thread_write_message_count": len(write_state["messages"]),
            "thread_read_message_count": len(read_state["messages"]),
            "separate_threads": write_config != read_config,
            "tool_command_update": write_state["last_memory_key"],
        },
        "context": {
            "write_user": user_a_context.user_id,
            "isolated_user": user_b_context.user_id,
            "persisted_in_state": "user_id" in write_state,
        },
        "store": {
            "namespace": ["users", "user-a", "preferences"],
            "key": "default_city",
            "value": memory.value,
            "search_result_count": len(user_a_memories),
            "cross_thread_tool_result": _tool_messages(read_result["messages"]),
            "other_user_tool_result": _tool_messages(isolated_result["messages"]),
        },
        "write_tool_result": _tool_messages(write_result["messages"]),
        "boundary": (
            "InMemorySaver 和 InMemoryStore 都会随进程结束而消失；"
            "前者按 thread 保存 State，后者可以按 namespace 跨 thread 共享数据。"
        ),
    }

    assert result["context"]["persisted_in_state"] is False
    assert result["state"]["tool_command_update"] == "default_city"
    assert "上海" in result["store"]["cross_thread_tool_result"][0]
    assert result["store"]["search_result_count"] == 1
    assert "尚未保存" in result["store"]["other_user_tool_result"][0]
    return result


# 启动命令：
#   .venv/bin/python 2_langchain/L13_Runtime_Context_Store.py
# 参数枚举：无。
def main() -> int:
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
