"""供 LangChain 进阶课件复用的离线 Tool Calling 模型。"""

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.tools import BaseTool


class ToolCallingFakeChatModel(FakeMessagesListChatModel):
    """让预设的 ``AIMessage`` 可以经过 ``create_agent`` 的工具绑定阶段。"""

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> "ToolCallingFakeChatModel":
        del tools, tool_choice, kwargs
        return self
