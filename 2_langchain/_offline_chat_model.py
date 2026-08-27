"""供 LangChain 进阶课件复用的离线 Tool Calling 模型。"""

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.tools import BaseTool


class ToolCallingFakeChatModel(FakeMessagesListChatModel):
    """让预设的 ``AIMessage`` 可以经过 ``create_agent`` 的工具绑定阶段。"""

    # ToolCallingFakeChatModel 额外提供了 bind_tools()，让它能够交给 create_agent() 使用，但它不会像真实模型那样分析 Tool 描述并决定调用哪个 Tool；调用决定已经提前写进 responses 了。
    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> "ToolCallingFakeChatModel":
        del tools, tool_choice, kwargs
        return self
