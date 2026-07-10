

import json
from pathlib import Path
import sys
from typing import Literal

from numpy import positive


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_SITE_PACKAGES = (
    PROJECT_ROOT
    / ".venv"
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)
if VENV_SITE_PACKAGES.exists():
    sys.path.insert(0, str(VENV_SITE_PACKAGES))


ZHIPU_API_KEY = "sk-lLKjavEquIsN4nk6eguOXFlhBXbXntGLHo5tOhbQWkBztYbj"
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
STABLE_TEMPERATURE = 0.1

SYSTEM_PROMPT = """
你是一个 LangChain structured output 教学助手。

你的任务不是自由发挥，而是把用户输入稳定抽取成指定 Pydantic 结构。
如果原文没有给出某个字段，不要编造；可以使用 None、other 或简短说明。
"""

def load_dependencies():
    try:
        from langchain.agents import create_agent
        from langchain.agents.structured_output import ToolStrategy
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError(
            "加载失败。需要安装 langchain、langchain-openai、pydantic。"
            f"原始错误: {type(exc).__name__}: {exc}"
        ) from exc

    return {
        "BaseModel": BaseModel,
        "ChatOpenAI": ChatOpenAI,
        "Field": Field,
        "ToolStrategy": ToolStrategy,
        "create_agent": create_agent,
    }

def build_model(ChatOpenAI, temperature=STABLE_TEMPERATURE, **kwargs):
    return ChatOpenAI(
        model=ZHIPU_CHAT_MODEL,
        temperature=temperature,
        openai_api_key=ZHIPU_API_KEY,
        openai_api_base=ZHIPU_BASE_URL,
        timeout=60,
        **kwargs,
    )


def model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return {key: model_dump(item) for key, item in value.items()}
    if isinstance(value, list):
        return [model_dump(item) for item in value]
    return value


def define_schemas(deps):
    BaseModel = deps["BaseModel"]
    Field = deps["Field"]

    class ContactInfo(BaseModel):
        """从文本中抽取联系人信息。"""

        name: str = Field(description="联系人姓名")
        email: str | None = Field(default=None, description="邮箱；没有就返回 None")
        phone: str | None = Field(default=None, description="电话；没有就返回 None")
        company: str | None = Field(default=None, description="公司；没有就返回 None")

    class ProductReview(BaseModel):
        """分析一段商品评价。"""

        rating: int | None = Field(
            default=None,
            ge=1,
            le=5,
            description="1 到 5 分评分；没有明确评分就返回 None",
        )
        sentiment: Literal["positive", "negative", "mixed"] = Field(
            description="整体情绪"
        )
        key_points: list[str] = Field(description="评价要点，使用短中文短语")
        needs_follow_up: bool = Field(description="是否需要客服或产品团队继续跟进")

    class SupportTicket(BaseModel):
        """把用户反馈整理成客服工单。"""

        category: Literal["account", "billing", "technical", "logistics", "other"] = (
            Field(description="工单分类")
        )
        priority: Literal["low", "medium", "high"] = Field(description="优先级")
        summary: str = Field(description="一句话概括问题")
        next_action: str = Field(description="建议下一步动作")

    return {
        "ContactInfo": ContactInfo,
        "ProductReview": ProductReview,
        "SupportTicket": SupportTicket,
    }

def build_structured_agent(
    deps,
    schema,
    tool_message_content=None,
    handle_errors=True,
):
    response_format = deps["ToolStrategy"](schema=schema, tool_message_content=tool_message_content, handle_errors=handle_errors)
    return deps["create_agent"](
        model=build_model(deps["ChatOpenAI"]),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=response_format,
    )

def contact_info_demo(deps):
    schemas = define_schemas(deps)
    agent = build_structured_agent(
        deps,
        schemas["ContactInfo"],
        tool_message_content="联系人信息已抽取完成。",
    )
    source_text = (
        "请从这段话抽取联系人：鼎捷项目负责人是王小明，"
        "邮箱 wangxiaoming@example.com，电话 138-0000-1234。"
    )
    return agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": source_text,
                }
            ]
        }
    )

def product_review_demo(deps):
    schemas = define_schemas(deps)
    agent = build_structured_agent(
        deps,
        schemas["ProductReview"],
        tool_message_content="商品评价已整理成结构化数据。",
    )
    source_text = (
        "请分析这个评论：这款无线鼠标整体很好用，5分满分我给4分，"
        "握感舒服，续航不错，但是滚轮声音有点大。"
    )
    return agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": source_text,
                }
            ]
        }
    )


def support_ticket_demo(deps):
    schemas = define_schemas(deps)
    agent = build_structured_agent(
        deps,
        schemas["SupportTicket"],
        tool_message_content="客服工单已生成。",
        handle_errors="请严格按工单 schema 返回，不要漏字段。",
    )
    source_text = (
        "用户反馈：昨天付款后订单页面一直显示未支付，"
        "但是银行卡已经扣款，客户今天下午要给财务报销，比较着急。"
    )
    return agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": source_text,
                }
            ]
        }
    )

def run(title, func, deps):
    try:
        print(f"\n===== {title} =====")
        value = func(deps)
        print(json.dumps(model_dump(value), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"跳过：{type(exc).__name__}: {exc}")


def main():
    try:
        deps = load_dependencies()
    except RuntimeError as exc:
        print(exc)
        return

    run("1. response_format 抽取联系人结构", contact_info_demo, deps)
    run("2. ToolStrategy 分析商品评价", product_review_demo, deps)
    run("3. 自定义错误提示生成客服工单", support_ticket_demo, deps)


if __name__ == "__main__":
    main()
