import json
from typing import Literal

ZHIPU_API_KEY = "sk-lLKjavEquIsN4nk6eguOXFlhBXbXntGLHo5tOhbQWkBztYbj"
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
STABLE_TEMPERATURE = 0.1


def load_dependencies():
    try:
        from langchain_core.output_parsers.openai_tools import PydanticToolsParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel, Field
    except Exception as exc:
        raise RuntimeError(
            "加载失败。需要安装 langchain-core、langchain-openai、pydantic。"
            f"原始错误: {type(exc).__name__}: {exc}"
        )
    return {
        "BaseModel": BaseModel,
        "ChatOpenAI": ChatOpenAI,
        "ChatPromptTemplate": ChatPromptTemplate,
        "Field": Field,
        "PydanticToolsParser": PydanticToolsParser,
    }


def pydantic_to_tool(model):
    schema = model.model_json_schema() if hasattr(model, "model_json_schema") else model.schema()
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

def build_model(ChatOpenAI, temperature=STABLE_TEMPERATURE, **kwargs):
    return ChatOpenAI(
        model=ZHIPU_CHAT_MODEL,
        temperature=temperature,
        openai_api_key=ZHIPU_API_KEY,
        openai_api_base=ZHIPU_BASE_URL,
        **kwargs,
    )

# value是pydantic模型实例需要递归构造，这样json.dump时才能正确处理
def model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return{key: model_dump(item) for key, item in value.items()}
    if isinstance(value, list):
        return [model_dump(item) for item in value]
    return value

def compact_message(message):
    return {
        "content": getattr(message, "content", None),
        "tool_calls": getattr(message, "tool_calls", None),
        "additional_kwargs": getattr(message, "additional_kwargs", None),
    }

def define_models(BaseModel, Field):
    class Tagging(BaseModel):
        """给文本打标签，抽取整体判断信息。"""

        sentiment: Literal["positive", "neutral", "negative"] = Field(description="文本的情感倾向")
        language: str = Field(description="文本的语言，使用 ISO 639-1 双字母代码")

    class Person(BaseModel):
        """文本中提到的一个人。"""

        name: str = Field(description="人的姓名")
        age: int | None = Field(default=None, description="人的年龄；如果未明确提供，不要猜测")

    class Information(BaseModel):
        """从文本中抽取到的人员信息。"""

        people: list[Person] = Field(default_factory=list, description="文本中提到的人")   

    class Overview(BaseModel):
        """文章概览信息。"""

        summary: str = Field(description="文章摘要")
        language: str = Field(description="文章语言，使用 ISO 639-1 双字母代码")
        keywords: list[str] = Field(description="文章关键词列表")

    class Paper(BaseModel):
        """文章中提到的一篇论文。"""

        title: str = Field(description="论文标题")
        author: str | None = Field(default=None, description="论文作者；如果未明确提供，不要猜测")

    class PaperInfo(BaseModel):
        """文章中提到的论文列表。"""

        # Field(default_factory=list) 的意思是如果没有提供值，就使用一个新的空列表作为默认值，避免了多个实例共享同一个列表导致的问题。
        papers: list[Paper] = Field(default_factory=list, description="文章中提到的论文")
        # people: list[Person] = [] 这样多个实例共享一个列表会相互影响

    return Tagging, Person, Information, Overview, Paper, PaperInfo

def run(title, func, deps):
    try:
        print(f"\n===== {title} =====")
        value = func(deps)
        print(json.dumps(model_dump(value), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"跳过：{type(exc).__name__}: {exc}")

def tagging_demo(deps):
    Tagging, *_ = define_models(deps["BaseModel"], deps["field"])
    prompt = deps["ChatPromptTemplate"].from_messages(
        [
            ("system", "请从用户输入中抽取标签。"),
            ("user", "{input}"),
        ]
    )
    model = build_model(deps["ChatOpenAI"]).bind(
        tools=[pydantic_to_tool(Tagging)],
        tools_choice="auto",
    )
    message = (prompt | model).invoke({"input": "I love LangChain, it is very useful!"})
    return compact_message(message)

def tagging_parser_demo(deps):
    Tagging, *_ = define_models(deps["BaseModel"], deps["Field"])
    prompt = deps["ChatPromptTemplate"].from_messages(
        [
            ("system", "请从用户输入中抽取标签。"),
            ("user", "{input}"),
        ]
    )
    model = build_model(deps["ChatOpenAI"]).bind(
        tools=[pydantic_to_tool(Tagging)],
        tool_choice="auto",
    )
    parser = deps["PydanticToolsParser"](tools=[Tagging], first_tool_only=True)
    chain = prompt | model | parser
    return {
        "english_positive": chain.invoke({"input": "I love LangChain, it is very useful!"}),
        "italian_negative": chain.invoke({"input": "Non mi piace questo prodotto."}),
    }

def extraction_raw_message_demo(deps):
    _, _, Information, *_ = define_models(deps["BaseModel"], deps["Field"])
    model = build_model(deps["ChatOpenAI"]).bind(
        tools=[pydantic_to_tool(Information)],
        tool_choice="auto",
    )

    message = model.invoke("Joe is 30, his mom is Martha.")
    return compact_message(message)

def extraction_parser_demo(deps):
    _, _, Information, *_ = define_models(deps["BaseModel"], deps["Field"])
    prompt = deps["ChatPromptTemplate"].from_messages(
        [
            (
                "system",
                "抽取相关信息。如果信息没有明确提供，不要猜测。允许只抽取部分信息。",
            ),
            ("user", "{input}"),
        ]
    )
    model = build_model(deps["ChatOpenAI"]).bind(
        tools=[pydantic_to_tool(Information)],
        tool_choice="auto",
    )
    parser = deps["PydanticToolsParser"](tools=[Information], first_tool_only=True)
    chain = prompt | model | parser

    return chain.invoke({"input": "Joe is 30. His mom is Martha."})

def load_article():
    url = "https://lilianweng.github.io/posts/2023-06-23-agent/"
    from langchain_community.document_loaders import WebBaseLoader

    loader = WebBaseLoader(url)
    docs = loader.load()
    return docs[0].page_content

def full_article_paper_extraction_demo(deps):
    *_, PaperInfo = define_models(deps["BaseModel"], deps["Field"])
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    page_content = load_article()
    splitter = RecursiveCharacterTextSplitter(chunk_size=5000, chunk_overlap=0)
    splits = splitter.split_text(page_content)
    prompt = deps["ChatPromptTemplate"].from_messages(
        [
            (
                "system",
                "你会收到一段文章片段。请抽取片段中提到的所有论文。"
                "不要抽取文章自身的标题。不要编造或猜测额外信息。"
                "如果没有提到论文，返回空列表。",
            ),
            ("user", "{input}"),
        ]
    )
    model = build_model(deps["ChatOpenAI"]).bind(
        tools=[pydantic_to_tool(PaperInfo)],
        tool_choice="auto",
    )
    parser = deps["PydanticToolsParser"](tools=[PaperInfo], first_tool_only=True)
    chain = prompt | model | parser

    results = chain.batch([{"input": split} for split in splits])
    return flatten([result.papers for result in results])

def flatten(list_of_lists):
    return [item for sublist in list_of_lists for item in sublist]