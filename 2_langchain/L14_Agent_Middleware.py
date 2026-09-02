"""L14：用可离线执行的路径学习 Agent Middleware 生命周期与策略。

覆盖四条互相独立的路径：

1. lifecycle：before/after hooks、model/tool wrapper、动态 Prompt/Tool/Model；
2. retry/limits：Model/Tool 重试和调用次数限制；
3. context：SummarizationMiddleware 压缩旧消息，PIIMiddleware 脱敏；
4. HITL：HumanInTheLoopMiddleware 在敏感 Tool 前暂停并 approve/reject。

这 5 个 Demo 都通过 create_agent() 创建 Agent，因此都运行在 LangChain 内部构建并编译的
LangGraph 上，并不只有 hitl_demo() 使用 Graph：

- lifecycle_demo()：Graph 完成 Model → Tools → Model 回环；
- model_retry_demo()：Graph 负责 Model Node 的执行，重试发生在该 Node 内的包装器中；
- summarization_demo()：Graph 在 Model 前执行摘要 Middleware；
- pii_demo()：Graph 在 Model 前后执行输入、输出脱敏 Middleware；
- hitl_demo()：Graph 还显式使用 Checkpointer、interrupt 和 Command(resume=...) 暂停与恢复。

为什么本教程放在 LangChain，而不是 LangGraph：

应用代码使用的是 langchain.agents.create_agent 和 langchain.agents.middleware 这组高层 API，
学习目标是给现成的 Agent 循环配置 Middleware；LangGraph 在下层负责 State、Node、路由、
持久化和暂停恢复。本文件没有手动使用 StateGraph、add_node()、add_edge() 构建流程，因此按
直接学习的 API 归入 LangChain；显式设计 Graph 结构时才归入 LangGraph 教程。

FakeMessagesListChatModel： LangChain 内置的“固定剧本测试模型”。
不会理解或推理输入内容，只会依次返回 responses 中预置的消息
FakeListChatModel：返回字符串，再包装成 AIMessage
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentState,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ModelRequest,
    ModelResponse,
    ModelRetryMiddleware,
    PIIMiddleware,
    SummarizationMiddleware,
    ToolCallLimitMiddleware,
    ToolCallRequest,
    ToolRetryMiddleware,
    after_agent,
    after_model,
    before_agent,
    before_model,
    wrap_model_call,
    wrap_tool_call,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import (
    FakeListChatModel,
    FakeMessagesListChatModel,
)
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime
from langgraph.types import Command

from _offline_chat_model import ToolCallingFakeChatModel

EVENTS: list[dict[str, Any]] = []
TOOL_ATTEMPTS = 0
PUBLISHED_REPORTS: list[str] = []


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    role: str
    model_label: str
    selected_model: BaseChatModel


@tool
def flaky_course_lookup(topic: str) -> str:
    """查询课程摘要；第一次调用模拟暂时性错误。"""

    # 声明 global 后再赋值  → 修改模块级全局变量
    # 函数内给名字赋值       → 默认认为是局部变量
    global TOOL_ATTEMPTS
    TOOL_ATTEMPTS += 1
    if TOOL_ATTEMPTS == 1:
        raise ConnectionError("模拟课程服务第一次暂时不可用")
    return f"{topic}：Middleware 可以观察或包裹 Model/Tool 调用。"


@tool
def internal_admin_lookup(topic: str) -> str:
    """仅管理员可见的教学工具；reader 角色会在 Model Request 中移除它。"""

    return f"管理员资料：{topic}"


@tool
def publish_report(report_name: str) -> str:
    """发布一份报告；这是需要人工确认的敏感副作用。"""

    PUBLISHED_REPORTS.append(report_name)
    return f"已发布 {report_name}"


# LangChain 提供的装饰器，函数注册成“Agent 开始运行之前执行的 Middleware Hook”
# 一次 Agent 运行开始前执行一次
# 读取当前 state
# 读取本次 runtime
# 返回 None：不修改 State
# 返回字典：更新 State
@before_agent
def log_before_agent(
    state: AgentState, runtime: Runtime[RequestContext]
) -> None:  # 当前代码返回 None，所以只是记录日志，没有修改 State。
    EVENTS.append(
        {
            "hook": "before_agent",
            "tenant_id": runtime.context.tenant_id,
            "message_count": len(state["messages"]),
        }
    )


# LangChain 的装饰器，每次调用模型前都执行，可能执行多次
# 返回 None：不修改 State
# 返回字典：更新 State
@before_model
def trim_before_model(
    state: AgentState, runtime: Runtime[RequestContext]
) -> dict[str, Any] | None:
    """演示 Context Editing：State 仍由 Reducer 更新，不直接原地删除。"""

    del runtime
    messages = state["messages"]
    EVENTS.append({"hook": "before_model", "message_count": len(messages)})
    if len(messages) <= 5:
        return None
    return {
        # 表示清空旧消息，再添加最后两条，才能真正完成裁剪。作用是保留最后两条messages，丢弃之前的历史消息。
        "messages": [
            # 先清空 State 中已有的全部消息
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            # Reducer 会尝试“合并”最后两条消息
            *messages[-2:],
        ]
    }


# 包裹每一次模型调用，让你在模型调用前后插入逻辑，并控制模型如何被调用。
# 可以用它：
# - 修改 SystemMessage
# - 动态更换模型
# - 动态增删可用 Tool
# - 记录调用前后的日志
# - 捕获异常或实现重试
# - 直接返回结果，从而跳过真实模型调用
@wrap_model_call
def add_dynamic_system_message(
    request: ModelRequest[RequestContext],
    handler: Callable[[ModelRequest[RequestContext]], ModelResponse],
) -> ModelResponse:
    """每次调用模型前，根据当前用户的租户和角色，动态选择模型、过滤可用 Tool、添加 SystemMessage，然后真正调用模型。"""

    EVENTS.append(
        {
            "hook": "wrap_model_call:before",
            "tenant_id": request.runtime.context.tenant_id,
            "message_count": len(request.messages),
        }
    )
    selected_tools = [
        candidate
        for candidate in request.tools
        if request.runtime.context.role == "admin"
        or candidate.name != "internal_admin_lookup"
    ]
    EVENTS[-1].update(
        {
            "model_label": request.runtime.context.model_label,
            "available_tools": [candidate.name for candidate in request.tools],
            "selected_tools": [candidate.name for candidate in selected_tools],
        }
    )
    # request.override() 返回新的 ModelRequest，不会修改原来的 request。
    scoped_request = request.override(
        model=request.runtime.context.selected_model,
        tools=selected_tools,
        system_message=SystemMessage(
            content=(
                f"tenant={request.runtime.context.tenant_id}; "
                f"role={request.runtime.context.role}; 只使用获准工具。"
            )
        ),
    )
    # 调用 handler(scoped_request) 执行模型调用，返回 ModelResponse
    response = handler(scoped_request)
    EVENTS.append(
        {
            "hook": "wrap_model_call:after",
            "response_types": [type(item).__name__ for item in response.result],
        }
    )
    return response


@after_model
def log_after_model(state: AgentState, runtime: Runtime[RequestContext]) -> None:
    del runtime
    message = state["messages"][-1]
    EVENTS.append(
        {
            "hook": "after_model",
            "message_type": type(message).__name__,
            "has_tool_calls": bool(getattr(message, "tool_calls", [])),
        }
    )


# 包裹每一次 Tool 调用，让你在 Tool 执行前后插入逻辑，并控制 Tool 是否、如何执行
@wrap_tool_call
def log_tool_call(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
) -> ToolMessage | Command[Any]:
    """自定义 Wrapper 记录边界；真正重试由 ToolRetryMiddleware 负责。"""

    EVENTS.append(
        {
            "hook": "wrap_tool_call:before",
            "tool": request.tool_call["name"],
        }
    )
    result = handler(request)
    EVENTS.append(
        {
            "hook": "wrap_tool_call:after",
            "tool": request.tool_call["name"],
        }
    )
    return result


@after_agent
def log_after_agent(state: AgentState, runtime: Runtime[RequestContext]) -> None:
    del runtime
    EVENTS.append(
        {
            "hook": "after_agent",
            "message_count": len(state["messages"]),
        }
    )


def _message_summary(messages: list[BaseMessage]) -> list[dict[str, str]]:
    return [
        {"type": type(message).__name__, "content": str(message.content)}
        for message in messages
    ]


class TransientFailureFakeChatModel(FakeListChatModel):
    """第一次模型调用失败，供 ModelRetryMiddleware 离线验证。"""

    attempts: int = 0
    failures_remaining: int = 1

    def _call(self, *args: Any, **kwargs: Any) -> str:
        self.attempts += 1
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise ConnectionError("模拟模型服务第一次暂时不可用")
        return super()._call(*args, **kwargs)


# 7 条初始消息 → 裁剪为 2 条 → 第一次调用模型产生 Tool Call → Tool 第一次失败、第二次成功 → 第二次调用模型产生最终回答 → 最终 State 保留 5 条消息。
def lifecycle_demo() -> dict[str, Any]:
    global TOOL_ATTEMPTS
    EVENTS.clear()
    TOOL_ATTEMPTS = 0

    # 创建真正要使用的模型
    selected_model = ToolCallingFakeChatModel(
        # 假模型固定返回两次响应
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {  # 查询课程摘要；第一次调用模拟暂时性错误。
                        "name": "flaky_course_lookup",
                        "args": {"topic": "Agent Middleware"},
                        "id": "lookup-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="查询完成：Middleware 可以统一控制调用生命周期。"),
        ]
    )

    # 备用模型
    bootstrap_model = ToolCallingFakeChatModel(
        responses=[AIMessage(content="如果看到这句话，动态模型覆盖没有生效。")]
    )

    agent = create_agent(
        model=bootstrap_model,
        tools=[flaky_course_lookup, internal_admin_lookup],
        context_schema=RequestContext,
        middleware=[
            log_before_agent,
            trim_before_model,
            add_dynamic_system_message,
            log_after_model,
            log_tool_call,
            ToolRetryMiddleware(
                max_retries=1,
                tools=["flaky_course_lookup"],
                retry_on=ConnectionError,
                on_failure="error",
                initial_delay=0,
                backoff_factor=0,
                jitter=False,
            ),
            ModelCallLimitMiddleware(run_limit=3, exit_behavior="error"),
            ToolCallLimitMiddleware(run_limit=2, exit_behavior="error"),
            log_after_agent,
        ],
    )

    # State["messages"] 完整变化（这里只统计 messages；调用次数限制器不改变消息）：
    #
    # 1. agent.invoke(...) 创建初始 AgentState
    #    add_messages Reducer 把下面 7 个字典转换成 HumanMessage/AIMessage：7 条
    #
    # 2. log_before_agent(state, runtime)
    #    只把观察结果写入 EVENTS，隐式返回 None，不更新 State：仍为 7 条
    #
    # 3. trim_before_model(state, runtime) 第一次执行
    #    返回 {"messages": [RemoveMessage(REMOVE_ALL_MESSAGES), *messages[-2:]]}
    #    add_messages Reducer 先清空旧消息，再放回最后两条：7 条 → 2 条
    #
    # 4. add_dynamic_system_message(request, handler) 包裹第一次 Model 调用
    #    request.override(...) 只临时替换 ModelRequest 的模型、工具和 SystemMessage，不更新 State
    #    handler(scoped_request) 调用 selected_model，返回带 tool_calls 的 AIMessage
    #    Model 节点把该 AIMessage 作为 partial update 交给 add_messages 追加：2 条 → 3 条
    #
    # 5. log_after_model(state, runtime) 第一次执行
    #    只观察最新 AIMessage，返回 None，不更新 State：仍为 3 条
    #
    # 6. log_tool_call(request, handler) 包裹 ToolRetryMiddleware 和 flaky_course_lookup(...)
    #    Tool 第一次抛出 ConnectionError，第二次成功；Tool 节点生成 ToolMessage
    #    Tool 节点把 ToolMessage 作为 partial update 交给 add_messages 追加：3 条 → 4 条
    #
    # 7. trim_before_model(state, runtime) 第二次执行
    #    此时 len(messages) == 4，满足 <= 5，返回 None，不裁剪：仍为 4 条
    #
    # 8. add_dynamic_system_message(request, handler) 包裹第二次 Model 调用
    #    request.override(...) 仍只修改临时 ModelRequest；selected_model 返回最终 AIMessage
    #    Model 节点通过 add_messages 追加最终 AIMessage：4 条 → 5 条
    #
    # 9. log_after_model(state, runtime) 第二次执行
    #    观察到最终 AIMessage 没有 tool_calls，返回 None：仍为 5 条
    #
    # 10. log_after_agent(state, runtime)
    #     记录最终消息数量并返回 None，不更新 State：最终为 5 条，Agent 结束
    result = agent.invoke(
        {
            "messages": [  # 直接给 Agent 的初始 State 预置 messages
                {"role": "user", "content": "历史问题一"},
                {"role": "assistant", "content": "历史回答一"},
                {"role": "user", "content": "历史问题二"},
                {"role": "assistant", "content": "历史回答二"},
                {"role": "user", "content": "历史问题三"},
                {"role": "assistant", "content": "历史回答三"},
                {"role": "user", "content": "查询 Agent Middleware"},
            ]
        },
        # context 注入 selected_model，函数 add_dynamic_system_message 会使用它覆盖 bootstrap_model。
        context=RequestContext(
            tenant_id="tenant-a",
            role="reader",
            model_label="offline-reader-model",
            selected_model=selected_model,
        ),
    )

    assert TOOL_ATTEMPTS == 2
    assert any(event["hook"] == "after_agent" for event in EVENTS)
    model_events = [
        event for event in EVENTS if event["hook"] == "wrap_model_call:before"
    ]
    assert model_events
    assert all(
        "internal_admin_lookup" not in event["selected_tools"] for event in model_events
    )
    assert str(result["messages"][-1].content).startswith("查询完成")
    return {
        "tool_attempts": TOOL_ATTEMPTS,
        "events": list(EVENTS),
        "final_messages": _message_summary(result["messages"]),
        "dynamic_request": {
            "model": model_events[0]["model_label"],
            "available_tools": model_events[0]["available_tools"],
            "selected_tools": model_events[0]["selected_tools"],
        },
        "limits": {"model_calls_per_run": 3, "tool_calls_per_run": 2},
    }


def model_retry_demo() -> dict[str, Any]:
    model = TransientFailureFakeChatModel(
        responses=["ModelRetryMiddleware 重试后成功。"]
    )
    agent = create_agent(
        model=model,
        tools=[],
        middleware=[
            ModelRetryMiddleware(
                max_retries=1,
                retry_on=ConnectionError,
                on_failure="error",
                initial_delay=0,
                backoff_factor=0,
                jitter=False,
            )
        ],
    )

    # → Model Node
    #     → ModelRetryMiddleware.wrap_model_call()
    #       → 第一次 handler(request) → ConnectionError
    #       → 第二次 handler(request) → 成功
    #   → 生成一条 AIMessage
    # → add_messages 更新 State
    # 最终messages两条消息
    # HumanMessage("测试模型重试"),
    # AIMessage("ModelRetryMiddleware 重试后成功。") 模型预置的固定返回
    result = agent.invoke({"messages": [{"role": "user", "content": "测试模型重试"}]})

    assert model.attempts == 2
    return {
        "attempts": model.attempts,
        "max_retries_after_initial_call": 1,
        "answer": str(result["messages"][-1].content),
    }


# 5 条原始消息
#   → SummarizationMiddleware 触发
#   → 前 3 条交给 summary_model
#   → 后 2 条原样保留
#   → State 重建为：1 条摘要 + 2 条近期消息
#   → answer_model 生成最终回答
#   → 最终 State 共 4 条消息
def summarization_demo() -> dict[str, Any]:
    # 专门负责生成历史摘要： Fake Model，它不会真正理解输入，而是固定返回
    # summary_model：把旧消息变成摘要文本
    summary_model = FakeMessagesListChatModel(
        responses=[AIMessage(content="用户前面讨论了蓝色主题和两轮历史问题。")]
    )

    # answer_model：读取压缩后的上下文，生成最终回答
    answer_model = FakeMessagesListChatModel(
        responses=[AIMessage(content="已基于压缩后的上下文继续回答。")]
    )

    agent = create_agent(
        model=answer_model,  # agent 使用 answer_model
        tools=[],
        middleware=[
            # 配置摘要触发条件
            SummarizationMiddleware(
                # 使用 summary_model 生成摘要
                model=summary_model,
                # 消息数量达到 4 条就执行摘要
                trigger=("messages", 4),
                # 摘要后尽量原样保留最近 2 条消息
                keep=("messages", 2),
            )
        ],
    )

    # 预置5条消息，invoke直接触发 SummarizationMiddleware.before_model()
    #  → summary_model invoke 生成摘要 就是把前几条消息放入prompt调用 summary_model 生成总结
    # 最终 state["messages"] = [
    #     HumanMessage("Here is a summary ..."),
    #     AIMessage("继续讨论。"),
    #     HumanMessage("请继续回答。"),
    # ]
    result = agent.invoke(
        {
            "messages": [
                {"role": "user", "content": "第一轮：我喜欢蓝色。"},
                {"role": "assistant", "content": "已记录。"},
                {"role": "user", "content": "第二轮：讨论上下文。"},
                {"role": "assistant", "content": "继续讨论。"},
                {"role": "user", "content": "请继续回答。"},
            ]
        }
    )
    messages = _message_summary(result["messages"])
    assert messages[0]["content"].startswith("Here is a summary")
    return {
        "before_message_count": 5,
        "after_message_count": len(messages),
        "messages": messages,
        "note": "摘要替换模型上下文中的旧消息，不等于跨线程长期记忆。",
    }


# 需要特别注意：当前 before_model 只查找最新一条 HumanMessage，after_model 只查找最新一条 AIMessage
def pii_demo() -> dict[str, Any]:
    agent = create_agent(
        model=FakeMessagesListChatModel(
            # 让模型输出也包含邮箱，用来验证输出脱敏
            responses=[AIMessage(content="结果发送到 report@example.com")]
        ),
        tools=[],
        middleware=[
            PIIMiddleware(
                # "email"：使用框架内置的邮箱检测器
                "email",
                # 用 [REDACTED_EMAIL] 完整替换邮箱
                strategy="redact",
                # Model 执行前检查用户输入
                apply_to_input=True,
                # Model 执行后检查 AI 输出
                apply_to_output=True,
            )
        ],
    )

    # 1. agent.invoke(...) 创建初始 AgentState
    #    输入字典被转换成 HumanMessage("我的邮箱是 learner@example.com")：1 条
    # 2. PIIMiddleware.before_model(state, runtime)
    #    找到最新 HumanMessage，将邮箱替换为 [REDACTED_EMAIL]
    #    返回 message ID 不变的脱敏消息，add_messages 在原位置替换：1 条 → 仍为 1 条
    #    因此模型实际看到 HumanMessage("我的邮箱是 [REDACTED_EMAIL]")
    # 3. Model 节点调用 FakeMessagesListChatModel
    #    Fake Model 固定返回 AIMessage("结果发送到 report@example.com")
    #    Model 节点将其作为 partial update 交给 add_messages 追加：1 条 → 2 条
    # 4. PIIMiddleware.after_model(state, runtime)
    #    找到最新 AIMessage，将邮箱替换为 [REDACTED_EMAIL]
    #    返回 message ID 不变的脱敏消息，add_messages 在原位置替换：2 条 → 仍为 2 条
    # 5. Agent 没有 Tool Call，执行结束；最终 State["messages"] 为：
    #    HumanMessage("我的邮箱是 [REDACTED_EMAIL]")
    #    AIMessage("结果发送到 [REDACTED_EMAIL]")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "我的邮箱是 learner@example.com"}]}
    )

    # _message_summary() 只生成便于展示的 type/content 字典，不再修改 State。
    messages = _message_summary(result["messages"])
    assert all("@example.com" not in message["content"] for message in messages)
    assert all("[REDACTED_EMAIL]" in message["content"] for message in messages)
    return {
        "strategy": "redact",
        "input_and_output_messages": messages,
        "note": "脱敏只处理配置的数据面，不替代权限、日志清洗和存储加密。",
    }


# create_agent() 内部构建并编译的 Graph：
#
# START
#   ↓
# Model Node
#   │ 生成带 publish_report Tool Call 的 AIMessage
#   ↓
# HumanInTheLoopMiddleware.after_model Node
#   │ 在真实 Tool 执行前 interrupt，Checkpointer 保存暂停状态
#   ↓
# 等待人工决定
#   │
#   ├─ approve
#   │    ↓
#   │  Tools Node
#   │    │ 从 AIMessage.tool_calls 找到并执行 publish_report
#   │    │ 把执行结果追加为 ToolMessage
#   │    ↓
#   │  Model Node
#   │    │ 根据 ToolMessage 生成最终 AIMessage
#   │    ↓
#   │  HumanInTheLoopMiddleware.after_model Node
#   │    │ 最终 AIMessage 没有 Tool Call，不再暂停
#   │    ↓
#   │   END
#   │
#   └─ reject
#        ↓
#      跳过 Tools Node
#        │ HITL Node 追加表示拒绝结果的 ToolMessage
#        ↓
#      Model Node
#        │ 根据拒绝结果生成最终 AIMessage
#        ↓
#      HumanInTheLoopMiddleware.after_model Node
#        │ 最终 AIMessage 没有 Tool Call，不再暂停
#        ↓
#       END
#
# 第一次 agent.invoke() 从 START 运行到 interrupt 后返回审批请求。
# 第二次 agent.invoke(Command(resume=...)) 使用同一 thread_id，从暂停的 HITL Node 继续。
# publish_report 是注册在 Tools Node 内的具体 Tool，不是单独的 Graph Node。
def hitl_demo(decision: Literal["approve", "reject"]) -> dict[str, Any]:
    PUBLISHED_REPORTS.clear()
    model = ToolCallingFakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "publish_report",
                        "args": {"report_name": "middleware-report.md"},
                        "id": "publish-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="人工决策已经处理。"),
        ]
    )

    # HITL 实际发生在 after_model Hook：模型已经生成 Tool Call，但真实 Tool 尚未执行
    agent = create_agent(
        model=model,
        tools=[publish_report],
        middleware=[
            HumanInTheLoopMiddleware(  # HITL 策略
                interrupt_on={
                    "publish_report": {  # 必须人工审批
                        "allowed_decisions": [
                            "approve",
                            "reject",
                        ],  # 只允许 approve 或 reject
                        "description": "发布报告属于外部副作用，需要人工确认。",
                    }
                }
            )
        ],
        # Interrupt 必须依赖 Checkpointer 保存暂停点。
        checkpointer=InMemorySaver(),
    )

    config = {"configurable": {"thread_id": f"middleware-hitl-{decision}"}}

    interrupted = agent.invoke(
        {"messages": [{"role": "user", "content": "发布报告"}]},
        config=config,
    )
    interrupt_value = interrupted["__interrupt__"][0].value

    human_decision: dict[str, Any]
    if decision == "approve":
        human_decision = {"type": "approve"}
    else:
        human_decision = {"type": "reject", "message": "教学演示拒绝发布"}

    # 两次 agent.invoke() 必须使用同一个 Agent Checkpointer thread_id
    resumed = agent.invoke(
        # Graph 控制指令，负责把审批结果送回之前暂停的 interrupt()
        Command(resume={"decisions": [human_decision]}),
        config=config,
    )

    # 最终 state messages [
    #     HumanMessage("发布报告"),
    #     AIMessage(tool_calls=[publish_report]),
    #     ToolMessage(
    #         content="已发布 middleware-report.md",
    #         status="success",
    #     ),
    #     AIMessage("人工决策已经处理。"),
    # ]

    expected_count = 1 if decision == "approve" else 0
    assert len(PUBLISHED_REPORTS) == expected_count
    return {
        "decision": decision,
        "interrupt": interrupt_value,
        "published_reports": list(PUBLISHED_REPORTS),
        "tool_messages": [
            str(message.content)
            for message in resumed["messages"]
            if isinstance(message, ToolMessage)
        ],
    }


def run_demo(decision: Literal["approve", "reject"] = "approve") -> dict[str, Any]:
    return {
        "lifecycle": lifecycle_demo(),  # 生命周期、动态模型/工具、Tool 重试
        "model_retry": model_retry_demo(),  # Model 重试
        "summarization": summarization_demo(),  # 历史消息压缩
        "pii": pii_demo(),  # 输入输出脱敏
        "human_in_the_loop": hitl_demo(decision),  # 敏感 Tool 人工审批
    }


# 启动命令：
#   .venv/bin/python 2_langchain/L14_Agent_Middleware.py
#   .venv/bin/python 2_langchain/L14_Agent_Middleware.py --decision reject
# 参数枚举：--decision approve（默认）/ reject。
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LangChain Agent Middleware 离线教学")
    parser.add_argument(
        "--decision",
        choices=("approve", "reject"),
        default="approve",
        help="HITL 示例的人工决策",
    )
    args = parser.parse_args(argv)
    print(json.dumps(run_demo(args.decision), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
