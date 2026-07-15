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
            f"加载失败: {type(exc).__name__}: {exc}。"
        )
    
    return {
        "BaseModel": BaseModel,
        "ChatOpenAI": ChatOpenAI,
        "ChatPromptTemplate": ChatPromptTemplate,
        "Field": Field,
        "ValidationError": ValidationError,
    }

# 把一个 Pydantic 类转换成大模型需要的工具定义格式
def pydantic_to_tool(model):
    schema = model.model_json_schema() if hasattr(model, "model_json_schema") else model.schema()
    desc = schema.pop("description", None) or (model.__doc__ or "").strip()
    parameters = {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
    }
    return {
        "type": "function",
        "function": {
            "name": model.__name__,
            "description": desc,
            "parameters": parameters,
        },
    }

def build_model(ChatOpenAI, temperature=STABLE_TEMPERATURE, **kwargs):
    return ChatOpenAI(
        model=ZHIPU_CHAT_MODEL,
        temperature=temperature,
        openai_api_key=ZHIPU_API_KEY,
        openai_api_base=ZHIPU_BASE_URL,
        **kwargs,
    )

def define_models(BaseModel, Field):
    class User(BaseModel):
        name: str = Field(description="用户的名字")
        age: int = Field(description="用户的年龄")
        email: str = Field(description="用户的邮箱地址")
    
    class ClassRoom(BaseModel):
        students: list[User]

    class WeatherSearch(BaseModel):
        """通过机场代码查询该机场所在地天气。"""
        airport_code: str = Field(description="机场的三字码，例如 PEK、SHA、LAX")

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
        "content": getattr(message, "content", None),
        "tool_calls": getattr(message, "tool_calls", None),
        "additional_kwargs": getattr(message, "additional_kwargs", None),
    }

def pydantic_validation_demo(deps):
    User, ClassRoom,_,_ = define_models(deps["BaseModel"], deps["Field"])
    user = User(name="Alice", age=30, email="alice@example.com")
    room = ClassRoom(students=[user])
    room_payload = room.model_dump() if hasattr(room, "model_dump") else room.dict()

    result  =  {
        "valid_user_age": user.age,
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

    return json.dumps(tools, indent=2, ensure_ascii=False)

def single_tool_call_demo(deps):
    _, _, WeatherSearch, _ = define_models(deps["BaseModel"], deps["Field"])
    weather_tool = pydantic_to_tool(WeatherSearch)
    model = build_model(deps["ChatOpenAI"]).bind(
        tools=[weather_tool],
        tool_choice="auto",
    )

    message = model.invoke("旧金山今天的天气怎么样？请根据机场代码调用工具。")
    return compact_message(message)

def prompt_tool_call_demo(deps):
    _, _, WeatherSearch, _ = define_models(deps["BaseModel"], deps["Field"])
    weather_tool = pydantic_to_tool(WeatherSearch)
    prompt = deps["ChatPromptTemplate"].from_messages(
        [
            ("system", "你是一个天气查询助手。"),
            ("user", "{input}"),
        ]
    )
    model = build_model(deps["ChatOpenAI"]).bind(
        tools=[weather_tool],
        tool_choice="auto",
    )

    chain = prompt | model
    message = chain.invoke({"input": "请告诉我旧金山今天的天气"})
    return compact_message(message)

def multi_tool_call_demo(deps):
    _, _, WeatherSearch, ArtistSearch = define_models(deps["BaseModel"], deps["Field"])
    weather_tool = pydantic_to_tool(WeatherSearch)
    artist_tool = pydantic_to_tool(ArtistSearch)

    model = build_model(deps["ChatOpenAI"]).bind(
        tools=[weather_tool, artist_tool],
        tool_choice="auto",
    )

    weather_message = model.invoke("旧金山今天的天气怎么样？")
    artist_message = model.invoke("列出 Taylor Swift 的三首歌。")
    message = model.invoke("请告诉我旧金山今天的天气，并推荐几首周杰伦的歌。")

    return {
        "weather": compact_message(weather_message),
        "artist": compact_message(artist_message),
        "combined": compact_message(message),
    }



def main():
    try:
        deps = load_dependencies()
    except RuntimeError as exc:
        print(exc)
        return

    # run("1. pydantic 参数校验", pydantic_validation_demo, deps)
    # run("2. 生成工具定义", tool_schema_demo, deps)
    # run("3. 单工具调用示例", single_tool_call_demo, deps)
    # run("4. PromptChain 中的工具调用示例", prompt_tool_call_demo, deps)
    run("5. 多工具调用示例", multi_tool_call_demo, deps)


if __name__ == "__main__":
    main()
