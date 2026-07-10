import json
from datetime import UTC, datetime


ZHIPU_API_KEY = "sk-lLKjavEquIsN4nk6eguOXFlhBXbXntGLHo5tOhbQWkBztYbj"
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
STABLE_TEMPERATURE = 0.1


def load_dependencies():
    try:
        import requests
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel, Field
    except Exception as exc:
        raise RuntimeError(
            "加载失败。需要安装 langchain-core、langchain-openai、pydantic、requests。"
            f"原始错误: {type(exc).__name__}: {exc}"
        )

    return {
        "BaseModel": BaseModel,
        "ChatOpenAI": ChatOpenAI,
        "ChatPromptTemplate": ChatPromptTemplate,
        "Field": Field,
        "requests": requests,
        "tool": tool,
    }


def build_model(ChatOpenAI, temperature=STABLE_TEMPERATURE, **kwargs):
    return ChatOpenAI(
        model=ZHIPU_CHAT_MODEL,
        temperature=temperature,
        openai_api_key=ZHIPU_API_KEY,
        openai_api_base=ZHIPU_BASE_URL,
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


def compact_message(message):
    return {
        "content": getattr(message, "content", None),
        "tool_calls": getattr(message, "tool_calls", None),
        "additional_kwargs": getattr(message, "additional_kwargs", None),
    }


# 如果 tool_obj 没有 args_schema，就尝试从 tool_obj.args 里拿参数信息。
# 如果连 args 属性也没有，就返回空字典 {}，避免程序直接报错。
def tool_to_openai_tool(tool_obj):
    """把 LangChain tool 转成 OpenAI/Zhipu 的 tools 参数结构。"""
    args_schema = getattr(tool_obj, "args_schema", None)
    if args_schema is not None:
        schema = (
            args_schema.model_json_schema()
            if hasattr(args_schema, "model_json_schema")
            else args_schema.schema()
        )
        parameters = {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": schema.get("required", []),
        }
    else:
        args = getattr(tool_obj, "args", {})
        parameters = {
            "type": "object",
            "properties": args,
            "required": list(args.keys()),
        }

    return {
        "type": "function",
        "function": {
            "name": tool_obj.name,
            "description": tool_obj.description,
            "parameters": parameters,
        },
    }


def define_tools(deps):
    BaseModel = deps["BaseModel"]
    Field = deps["Field"]
    requests = deps["requests"]
    tool = deps["tool"]

    class SearchInput(BaseModel):
        query: str = Field(description="要搜索的教程关键词或问题")

    class OpenMeteoInput(BaseModel):
        latitude: float = Field(description="纬度，例如旧金山是 37.7749")
        longitude: float = Field(description="经度，例如旧金山是 -122.4194")

    @tool(args_schema=SearchInput)
    def search_course_notes(query: str) -> str:
        """搜索本地课程笔记，适合回答 LangChain、tool、routing、智普接入相关问题。"""
        docs = [
            {
                "title": "LangChain tools",
                "body": (
                    "Tool 是一层 Python 函数包装。模型不会真的执行函数，"
                    "它只会返回想调用哪个 tool 以及参数；本地代码负责执行。"
                ),
            },
            {
                "title": "Routing",
                "body": (
                    "Routing 是让模型根据用户问题选择下一步动作。"
                    "例如天气问题走天气 tool，课程概念问题走搜索 tool，普通闲聊直接回答。"
                ),
            },
            {
                "title": "Zhipu OpenAI-compatible API",
                "body": (
                    "智普的 OpenAI-compatible 接口可以通过 ChatOpenAI 设置 "
                    "openai_api_base、openai_api_key、model 来调用；tool calling 使用 tools 参数。"
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
            f"气温: {current.get('temperature_2m')} {units.get('temperature_2m', 'C')}; "
            f"风速: {current.get('wind_speed_10m')} {units.get('wind_speed_10m', 'km/h')}"
        )

    return [search_course_notes, current_weather_online]


def execute_tool_call(tool_map, tool_call):
    name = tool_call["name"]
    args = tool_call.get("args") or {}
    if isinstance(args, str):
        args = json.loads(args)
    if name not in tool_map:
        raise ValueError(f"模型请求了未知 tool: {name}")
    return {
        "tool": name,
        "args": args,
        "result": tool_map[name].invoke(args),
    }


def route_once(deps, user_input):
    tools = define_tools(deps)
    tool_map = {item.name: item for item in tools}
    tool_defs = [tool_to_openai_tool(item) for item in tools]

    prompt = deps["ChatPromptTemplate"].from_messages(
        [
            (
                "system",
                "你是一个路由器。天气、气温、风速、经纬度问题必须调用 current_weather_online。"
                "LangChain、tool、routing、智普接口相关问题必须调用 search_course_notes。"
                "其他普通问题可以直接回答。",
            ),
            ("user", "{input}"),
        ]
    )
    model = build_model(deps["ChatOpenAI"]).bind(
        tools=tool_defs,
        tool_choice="auto",
    )
    message = (prompt | model).invoke({"input": user_input})

    tool_results = [
        execute_tool_call(tool_map, tool_call)
        for tool_call in (getattr(message, "tool_calls", None) or [])
    ]
    return {
        "user_input": user_input,
        "model_message": compact_message(message),
        "tool_results": tool_results,
    }


def tool_metadata_demo(deps):
    tools = define_tools(deps)
    return [
        {
            "name": item.name,
            "description": item.description,
            "args": item.args,
        }
        for item in tools
    ]


def tool_schema_demo(deps):
    return [tool_to_openai_tool(item) for item in define_tools(deps)]


def direct_tool_run_demo(deps):
    search_course_notes, current_weather_online = define_tools(deps)
    return {
        "search_result": search_course_notes.invoke({"query": "routing"}),
        "weather_result": current_weather_online.invoke(
            {"latitude": 37.7749, "longitude": -122.4194}
        ),
    }


def route_weather_demo(deps):
    return route_once(
        deps,
        "旧金山现在气温是多少？请用 latitude=37.7749, longitude=-122.4194 查询。",
    )


def route_course_notes_demo(deps):
    return route_once(deps, "LangChain 的 tool 和 routing 分别是什么意思？")


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

    # run("1. @tool 生成的 LangChain tool 元数据", tool_metadata_demo, deps)
    run("2. 转成 OpenAI/Zhipu tools 参数", tool_schema_demo, deps)
    # run("3. 不经过模型，直接执行本地 tool", direct_tool_run_demo, deps)
    # run("4. 经过模型路由到天气 tool", route_weather_demo, deps)
    run("5. 经过模型路由到课程搜索 tool", route_course_notes_demo, deps)


if __name__ == "__main__":
    main()
