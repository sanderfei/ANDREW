import json
import sys
from datetime import UTC, datetime
from pathlib import Path


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
你是一个 LangChain agent 教学助手。

你可以使用工具查询实时天气，也可以搜索本地课程笔记。
回答时先基于工具结果，不要编造实时数据。
如果用户没有给出天气查询需要的经纬度，请先要求用户补充 latitude 和 longitude。
"""


def load_dependencies():
    try:
        import requests
        from langchain.agents import create_agent
        from langchain.tools import tool
        from langchain_openai import ChatOpenAI
        from langgraph.checkpoint.memory import InMemorySaver
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError(
            "加载失败。需要安装 langchain、langchain-openai、langgraph、"
            "pydantic、requests。"
            f"原始错误: {type(exc).__name__}: {exc}"
        ) from exc

    return {
        "BaseModel": BaseModel,
        "ChatOpenAI": ChatOpenAI,
        "Field": Field,
        "InMemorySaver": InMemorySaver,
        "create_agent": create_agent,
        "requests": requests,
        "tool": tool,
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


def define_tools(deps):
    BaseModel = deps["BaseModel"]
    Field = deps["Field"]
    requests = deps["requests"]
    tool = deps["tool"]

    class SearchInput(BaseModel):
        query: str = Field(description="要搜索的课程关键词或问题")

    class OpenMeteoInput(BaseModel):
        latitude: float = Field(description="纬度，例如旧金山是 37.7749")
        longitude: float = Field(description="经度，例如旧金山是 -122.4194")

    @tool(args_schema=SearchInput)
    def search_course_notes(query: str) -> str:
        """搜索本地课程笔记，适合回答 LangChain agent、tool、memory 相关问题。"""
        docs = [
            {
                "title": "Tool calling",
                "body": (
                    "L5 演示的是模型返回 tool_calls，本地代码再手动执行工具。"
                ),
            },
            {
                "title": "Agent",
                "body": (
                    "Agent 是模型和工具的循环。模型可以先调用工具，拿到工具结果后，"
                    "再继续决定是否调用下一个工具，直到生成最终回答。"
                ),
            },
            {
                "title": "Memory",
                "body": (
                    "create_agent 配合 checkpointer 和 thread_id，可以在同一个会话里"
                    "保留历史消息，让下一轮问题复用上一轮上下文。"
                ),
            },
        ]
        query_lower = query.lower()
        matched = [
            doc
            for doc in docs
            if query_lower in doc["title"].lower() or query_lower in doc["body"].lower()
        ]
        if not matched:
            matched = docs
        return "\n".join(f"{doc['title']}: {doc['body']}" for doc in matched[:2])

    @tool(args_schema=OpenMeteoInput)
    def current_weather_online(latitude: float, longitude: float) -> str:
        """根据经纬度查询实时天气。"""
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,wind_speed_10m",
                "timezone": "auto",
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        current = data.get("current", {})
        units = data.get("current_units", {})
        observed_at = current.get("time") or datetime.now(UTC).isoformat()
        return (
            f"观测时间: {observed_at}; "
            f"气温: {current.get('temperature_2m')} "
            f"{units.get('temperature_2m', 'C')}; "
            f"风速: {current.get('wind_speed_10m')} "
            f"{units.get('wind_speed_10m', 'km/h')}"
        )

    return [search_course_notes, current_weather_online]


def build_agent(deps, use_memory=False):
    checkpointer = deps["InMemorySaver"]() if use_memory else None
    return deps["create_agent"](
        model=build_model(deps["ChatOpenAI"]),
        tools=define_tools(deps),
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


def basic_agent_demo(deps):
    agent = build_agent(deps)
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "旧金山现在气温是多少？"
                        "请用 latitude=37.7749, longitude=-122.4194 查询。"
                    ),
                }
            ]
        }
    )
    return result


def memory_agent_demo(deps):
    agent = build_agent(deps, use_memory=True)
    config = {"configurable": {"thread_id": "l6-agent-memory-demo"}}

    first = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "请记住：我后面说的默认城市是旧金山，"
                        "latitude=37.7749, longitude=-122.4194。"
                    ),
                }
            ]
        },
        config=config,
    )
    second = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "现在这个默认城市的气温和风速是多少？",
                }
            ]
        },
        config=config,
    )

    return {
        "first_turn_result": first,
        "second_turn_result": second,
    }


def stream_agent_steps_demo(deps):
    agent = build_agent(deps)
    chunks = []
    for chunk in agent.stream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "LangChain 的 agent 和 tool calling 有什么区别？",
                }
            ]
        },
        stream_mode="values",
    ):
        chunks.append(chunk)
    return chunks


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

    # run("1. create_agent 自动执行天气 tool 并生成最终回答", basic_agent_demo, deps)
    # run("2. checkpointer + thread_id 保留多轮上下文", memory_agent_demo, deps)
    run("3. stream 查看 agent 中间步骤", stream_agent_steps_demo, deps)


if __name__ == "__main__":
    main()
