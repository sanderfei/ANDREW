"""为助手构造 LangChain 聊天模型；默认框架模式不会加载或调用远端模型。"""

from typing import TYPE_CHECKING

from config import AssistantSettings

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI


def build_chat_model(settings: AssistantSettings) -> "ChatOpenAI | None":
    """只构造客户端，模型推理由工作流中的显式 invoke 调用触发。"""
    if settings.mode == "framework":
        return None
    if settings.mode != "glm":
        raise ValueError("assistant.mode 只能为 framework 或 glm。")
    if not settings.api_key:
        raise ValueError(
            "assistant.mode=glm 需要 ZHIPU_API_KEY；请在进程环境、"
            "runtime/local.env 或仓库根目录 .env 中配置。"
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.model,
        api_key=settings.api_key,
        base_url=settings.base_url,
        temperature=settings.temperature,
        timeout=settings.timeout,
        max_retries=settings.max_retries,
    )
