import json
from _runtime import env



ZHIPU_API_KEY = env("ZHIPU_API_KEY")
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
STABLE_TEMPERATURE = 0.1


def load_dependencies():
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel, Field, ValidationError
    except Exception as exc:
        raise RuntimeError(
            "加载依赖失败。需要安装 langchain-core、langchain-openai、pydantic。"
            f" 原始错误：{type(exc).__name__}: {exc}"
        )

    return {
        "BaseModel": BaseModel,
        "ChatOpenAI": ChatOpenAI,
        "ChatPromptTemplate": ChatPromptTemplate,
        "Field": Field,
        "ValidationError": ValidationError,
    }

# 把一个 Pydantic 类转换成大模型 function calling / tool calling 需要的工具定义格式
def pydantic_to_tool(model):
    schema = model.model_json_schema() if hasattr(model, "model_json_schema") else model.schema()
    # pop 的意思是：取出这个 key，并从字典里删除它。如果没有这个 key，就返回 None。
    description = schema.pop("description", None) or (model.__doc__ or "").strip()
    parameters = {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
    }
    return {
        "type": "function",
        "function": {
            "name": model.__name__,
            "description": description,
            "parameters": parameters,
        },
    }


def build_zhipu_chat_model(ChatOpenAI, temperature=STABLE_TEMPERATURE, **kwargs):
    return ChatOpenAI(
        model=ZHIPU_CHAT_MODEL,
        temperature=temperature,
        openai_api_key=ZHIPU_API_KEY,
        openai_api_base=ZHIPU_BASE_URL,
        **kwargs,
    )


def define_models(BaseModel, Field):
    class User(BaseModel):
        name: str
        age: int
        email: str

    class ClassRoom(BaseModel):
        students: list[User]

    class WeatherSearch(BaseModel):
        """通过机场代码查询该机场所在地天气。"""
        # Pydantic 提供的函数 Field 配置额外元信息
        airport_code: str = Field(description="要查询天气的机场代码，例如 SFO")

    class ArtistSearch(BaseModel):
        """查询某位歌手的歌曲名称。"""
        artist_name: str = Field(description="要查询的歌手姓名")
        n: int = Field(description="返回结果数量")

    return User, ClassRoom, WeatherSearch, ArtistSearch


def run(title, func, deps):
    try:
        print(f"\n===== {title} =====")
        value = func(deps)
        print(value)
    except Exception as exc:
        print(f"跳过：{type(exc).__name__}: {exc}")


def compact_message(message):
    return {
        # getattr(对象, "属性名", 默认值)  Python 内置函数，用来从对象上读取某个属性
        "content": getattr(message, "content", None),
        "tool_calls": getattr(message, "tool_calls", None),
        "additional_kwargs": getattr(message, "additional_kwargs", None),
    }


def pydantic_validation_demo(deps):
    User, ClassRoom, _, _ = define_models(deps["BaseModel"], deps["Field"])
    valid_user = User(name="Jane", age=32, email="jane@gmail.com")
    room = ClassRoom(students=[valid_user])
    # room.model_dump() 是 Pydantic v2 的方法，用来把 Pydantic 对象转换成普通 Python 字典
    room_payload = room.model_dump() if hasattr(room, "model_dump") else room.dict()

    result = {
        "valid_user_age": valid_user.age,
        "class_room": room_payload,
    }

    try:
        User(name="Jane", age="bar", email="jane@gmail.com")
    except deps["ValidationError"] as exc:
        result["invalid_user_error"] = exc.errors()[0]["msg"]

    return result


def tool_schema_demo(deps):
    _, _, WeatherSearch, ArtistSearch = define_models(deps["BaseModel"], deps["Field"])

    tools = [
        pydantic_to_tool(WeatherSearch),
        pydantic_to_tool(ArtistSearch),
    ]
    return json.dumps(tools, ensure_ascii=False, indent=2)


def single_tool_call_demo(deps):
    _, _, WeatherSearch, _ = define_models(deps["BaseModel"], deps["Field"])
    weather_tool = pydantic_to_tool(WeatherSearch)

    model = build_zhipu_chat_model(deps["ChatOpenAI"]).bind(
        tools=[weather_tool],
        tool_choice="auto",
    )

    message = model.invoke("旧金山今天的天气怎么样？请根据机场代码调用工具。")
    return compact_message(message)


def prompt_chain_tool_call_demo(deps):
    _, _, WeatherSearch, _ = define_models(deps["BaseModel"], deps["Field"])
    weather_tool = pydantic_to_tool(WeatherSearch)

    prompt = deps["ChatPromptTemplate"].from_messages(
        [
            ("system", "你是一个乐于助人的助手。需要天气时请使用可用工具。"),
            ("user", "{input}"),
        ]
    )
    model = build_zhipu_chat_model(deps["ChatOpenAI"]).bind(
        tools=[weather_tool],
        tool_choice="auto",
    )

    chain = prompt | model
    message = chain.invoke({"input": "旧金山今天的天气怎么样？"})
    return compact_message(message)


def multi_tool_call_demo(deps):
    _, _, WeatherSearch, ArtistSearch = define_models(deps["BaseModel"], deps["Field"])
    tools = [
        pydantic_to_tool(WeatherSearch),
        pydantic_to_tool(ArtistSearch),
    ]

    model = build_zhipu_chat_model(deps["ChatOpenAI"]).bind(
        tools=tools,
        tool_choice="auto",
    )

    weather_message = model.invoke("旧金山今天的天气怎么样？")
    artist_message = model.invoke("列出 Taylor Swift 的三首歌。")
    return {
        "weather": compact_message(weather_message),
        "artist": compact_message(artist_message),
    }


def main():
    try:
        deps = load_dependencies()
    except RuntimeError as exc:
        print(exc)
        return

    run("1. pydantic 参数校验", pydantic_validation_demo, deps)
    run("2. pydantic 转 OpenAI/智谱 tool schema", tool_schema_demo, deps)
    run("3. 单工具调用", single_tool_call_demo, deps)
    run("4. prompt | model 工具调用链", prompt_chain_tool_call_demo, deps)
    run("5. 多工具选择", multi_tool_call_demo, deps)


if __name__ == "__main__":
    main()
