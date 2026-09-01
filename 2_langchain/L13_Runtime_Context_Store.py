"""L13：区分 Agent State、Runtime Context 与跨线程 Store。

本课完全离线，使用预设 Tool Call 的 Fake ChatModel，重点观察运行时数据边界：

State
    当前 thread 的消息和可变执行状态，由 checkpointer 保存。
Context
    单次 invoke 注入的 user_id、权限等依赖，不会自动写入 State。
Store
    按 namespace/key 保存跨 thread 数据；InMemoryStore 仅跨线程，不跨进程。

agent.invoke(
    input={"messages": [...]},
    config={"configurable": {"thread_id": "thread-write"}},
    context=UserContext(user_id="user-a", ...)
)
                 │
        ┌────────┴────────┐
        │                 │
   thread_id           context.user_id
        │                 │
        ▼                 ▼
 Checkpointer          Store namespace
        │                 │
        ▼                 ▼
 当前 thread 的 State   user-a 的长期业务数据
 messages              default_city=上海
 last_memory_key

thread_id 不保存数据，它只是 Checkpointer 的分区键：
thread-write       → 一份 State
thread-read        → 另一份 State
thread-other-user  → 又一份 State

Checkpointer 真正负责保存这些 State：
InMemorySaver
├─ thread-write       → messages + last_memory_key
├─ thread-read        → 自己的 messages
└─ thread-other-user  → 自己的 messages

agent.get_state(write_config)
就是让 Checkpointer 根据 thread_id="thread-write" 找到最新 State 仅有 thread_id 不够。
如果没有配置 Checkpointer，或者换了一个全新的 InMemorySaver，原来的 State 仍然找不到。

Store 不按 thread_id 隔离，而是按开发者定义的：namespace + key

代码流程>>>>如下
第一次：
thread-write + user-a
→ 写入 user-a/default_city
                   │
                   │ 相同 Store、相同 namespace、相同 key
                   ▼
第二次：
thread-read + user-a
→ 成功读取 user-a/default_city

第三次：
thread-other-user + user-b
→ 查询 user-b/default_city
→ 地址不同，读取失败
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


# 模型返回 remember_preference Tool Call
# LangChain 注入 ToolRuntime
# 检查 memory:write 权限
# 把偏好写入跨线程 Store
# 返回 Command 更新当前 thread 的 State
# messages Reducer 加入 ToolMessage
# 模型根据 ToolMessage 生成最终回答
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
    # runtime.store.put(...) 是 LangGraph BaseStore 提供的键值存储方法
    # store 当前实际对象是 InMemoryStore
    # 可以把存储地址理解为：
    #     namespace                             key
    # ("users", "user-a", "preferences") + "default_city"
    # 相同 namespace + key 再次执行会覆盖原条目，不会使用 Reducer 追加
    # message_count_when_written 只是写入当时的快照，后续 State 增加消息时不会自动更新。
    # 当前是 InMemoryStore，进程结束后数据消失。
    # runtime.store.put(
    #     ("users", "user-a", "preferences"),
    #     "default_city",
    #     {
    #         "value": "上海",
    #         "source_thread": "thread-write",
    #         "message_count_when_written": 2,
    #     },
    # )
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
    # Tool 返回 Command 后，由 LangGraph 把 update 合并进当前 State。
    # 普通返回值由 LangChain 自动构造 ToolMessage；Command 是特殊 State 指令，
    # 会跳过自动构造，所以开发者必须手动放入带匹配 tool_call_id 的 ToolMessage。
    return Command(
        update={
            "last_memory_key": key,
            "messages": [
                ToolMessage(
                    content=content,
                    # 真实模型场景中，这个 ID 一般由模型服务返回。
                    tool_call_id=runtime.tool_call_id or "missing-tool-call-id",
                    # 如果 tool_call_id 与原 Tool Call 的 ID 不匹配，LangGraph 会抛出 ValueError。
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

    # 让预设的 ``AIMessage`` 可以经过 ``create_agent`` 的工具绑定阶段。
    # 它不会根据 messages 的内容选择答案，只会按照调用次数依次返回：
    # 第1次调用模型 → responses[0]
    # 第2次调用模型 → responses[1]
    # | 模型调用次数 | 预设响应 | 用途 |
    # | 1 | `remember_preference` Tool Call | 第一轮保存偏好 |
    # | 2 | `"偏好已经保存。"` | 第一轮最终回答 |
    # | 3 | `recall_preference` Tool Call | 第二轮读取偏好 |
    # | 4 | `"已经从长期记忆读取默认城市。"` | 第二轮最终回答 |
    # | 5 | `recall_preference` Tool Call | 第三轮读取另一个用户 |
    # | 6 | `"该用户没有保存默认城市。"` | 第三轮最终回答 |
    return ToolCallingFakeChatModel(
        responses=[
            AIMessage(
                # 模型暂时不输出最终文本
                content="",
                # 模型请求 Agent 调用 remember_preference,参数为 key="default_city"、value="上海"
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
    return [
        str(message.content) for message in messages if isinstance(message, ToolMessage)
    ]


def run_demo() -> dict[str, Any]:
    # checkpointer：按 thread_id 保存每条线程的 State
    checkpointer = InMemorySaver()
    # store：按 namespace + key 保存跨 thread 的业务数据
    # 后面的三次 agent.invoke() 使用的都是同一个 store 对象
    store = InMemoryStore()

    # agent同时拥有 model 和 tool
    # agent.invoke(...)执行时 会自动执行匹配的 Tool
    # 得到 AIMessage.tool_calls
    # → 找到注册的 remember_preference
    # → 调用 remember_preference(key="default_city", value="上海")
    # → 将 Tool 结果加入 messages
    # → 再调用一次模型
    # → 得到 responses[1]：“偏好已经保存。”
    agent = create_agent(
        # Agent 拥有一个包含六条固定响应的假模型。
        model=_scripted_model(),
        # Agent 知道两个 Tool。
        tools=[remember_preference, recall_preference],
        state_schema=MemoryAgentState,
        context_schema=UserContext,
        # Agent 能按 thread_id 保存 State
        checkpointer=checkpointer,
        # 两个不同 thread 可以使用同一个 Store
        store=store,
    )

    # 准备两个用户
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

    # 第一轮，用户 A 保存偏好
    # 模型调用 #1
    # → 返回 remember_preference Tool Call
    # Agent 执行 remember_preference
    # → 写入 Store：user-a/default_city = 上海
    # → Command 更新 State：last_memory_key = "default_city"
    # → 加入 ToolMessage
    # 模型调用 #2
    # → 返回“偏好已经保存。”
    # → 本轮结束
    # write_result有四条
    # HumanMessage
    # AIMessage(tool_calls)
    # ToolMessage
    # AIMessage("偏好已经保存。")
    write_result = agent.invoke(
        {"messages": [{"role": "user", "content": "记住我的默认城市是上海"}]},
        config=write_config,
        context=user_a_context,
    )

    # 用户 A 换一个 thread 读取
    # 新的 thread_id，所以没有继承第一轮的 messages State
    # 但它仍然使用同一个 Store，并且 Context 还是 user-a

    # 模型调用 #3
    # → 返回 recall_preference Tool Call
    # Agent 执行 recall_preference
    # → 查询 ("users", "user-a", "preferences") 第一次写入就是这个
    # → 找到 default_city=上海
    # → 产生包含真实查询结果的 ToolMessage
    # 模型调用 #4
    # → 返回“已经从长期记忆读取默认城市。”
    # 这证明：State 没有跨 thread，Store 数据跨了 thread
    read_result = agent.invoke(
        {"messages": [{"role": "user", "content": "我的默认城市是什么？"}]},
        config=read_config,
        context=user_a_context,
    )

    # 第六步：用户 B 读取
    # 模型调用 #5
    # → 返回 recall_preference Tool Call
    # Agent 执行 recall_preference
    # → 查询 ("users", "user-b", "preferences")
    # → 找不到 default_city
    # → Tool 返回“user-b 尚未保存 default_city”
    # 模型调用 #6
    # → 返回“该用户没有保存默认城市。”
    # 这证明 Store 虽然跨 thread，但仍然通过用户 namespace 隔离。
    isolated_result = agent.invoke(
        {"messages": [{"role": "user", "content": "我的默认城市是什么？"}]},
        config=isolated_config,
        context=user_b_context,
    )

    memory = store.get(("users", "user-a", "preferences"), "default_city")
    if memory is None:
        raise AssertionError("user-a 的长期记忆没有写入 Store。")

    # write_state = {
    #     "messages": [
    #         HumanMessage("记住我的默认城市是上海"),
    #         AIMessage(tool_calls=[remember_preference]),
    #         ToolMessage(
    #             content="已为 user-a 记录 default_city=上海",
    #             name="remember_preference",
    #             tool_call_id="write-memory-1",
    #         ),
    #         AIMessage("偏好已经保存。"),
    #     ],
    #     "last_memory_key": "default_city",
    # }
    write_state = agent.get_state(write_config).values

    # read_state = {
    #     "messages": [
    #         HumanMessage("我的默认城市是什么？"),
    #         AIMessage(tool_calls=[recall_preference]),
    #         ToolMessage(
    #             content=(
    #                 '{"message_count_when_written": 2, '
    #                 '"source_thread": "thread-write", "value": "上海"}'
    #             ),
    #             name="recall_preference",
    #             tool_call_id="read-memory-1",
    #         ),
    #         AIMessage("已经从长期记忆读取默认城市。"),
    #     ],
    # }
    # 读取到 default_city -> Store 跨 thread 共享业务数据
    # read_state丢失了 write_state 的四条旧消息和 last_memory_key -> State 按 thread_id 隔离会话状态
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
