import asyncio
import json
import sys
from pathlib import Path

# 取当前文件 转path对象，转绝对路径，取上上级目录（0是上级目录代表/langchain 1代表上上级/andrew），就是项目根目录。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 拼接 venv 的 site-packages 路径（此语法只适用path对应拼接）
VENV_SITE_PACKAGES = (
    PROJECT_ROOT
    / ".venv"
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)
#  sys.path 是 Python 查找模块的路径列表
#  并把venv路径它插到 sys.path 前面。这样就能优先使用 venv 里的包了。
if VENV_SITE_PACKAGES.exists():
    sys.path.insert(0, str(VENV_SITE_PACKAGES))


ZHIPU_API_KEY = "sk-lLKjavEquIsN4nk6eguOXFlhBXbXntGLHo5tOhbQWkBztYbj"
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
ZHIPU_EMBEDDING_MODEL = "embedding-3"

# 智谱官方接口里 temperature 的建议区间是 (0, 1)，所以这里用 0.1 近似  OpenAI示例里的 temperature=0。
STABLE_TEMPERATURE = 0.1


def load_langchain_dependencies():
    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.runnables import RunnableMap
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from langchain_community.vectorstores import DocArrayInMemorySearch
    except ImportError as exc:
        raise RuntimeError(
            "缺少 LCEL 示例依赖。需要安装 langchain-core、langchain-openai、"
            "langchain-community、docarray 等包后再运行。"
        ) from exc

    return {
        "ChatPromptTemplate": ChatPromptTemplate,
        "ChatOpenAI": ChatOpenAI,
        "DocArrayInMemorySearch": DocArrayInMemorySearch,
        "OpenAIEmbeddings": OpenAIEmbeddings,
        "RunnableMap": RunnableMap,
        "StrOutputParser": StrOutputParser,
    }


def build_zhipu_chat_model(ChatOpenAI, temperature=STABLE_TEMPERATURE, **kwargs):
    return ChatOpenAI(
        model=ZHIPU_CHAT_MODEL,
        temperature=temperature,
        openai_api_key=ZHIPU_API_KEY,
        openai_api_base=ZHIPU_BASE_URL,
        **kwargs,
    )


def build_zhipu_embeddings(OpenAIEmbeddings):
    # 向量模型
    # OpenAI 原代码：
    # embedding=OpenAIEmbeddings()
    #
    # 智谱 OpenAI-compatible 写法：
    # 仍然使用 LangChain 的 OpenAIEmbeddings 适配器，但把 key/base_url/model 换成智谱。
    # 如果你使用智谱官方 LangChain 扩展，也可以换成 ZhipuAIEmbeddings。
    return OpenAIEmbeddings(
        model=ZHIPU_EMBEDDING_MODEL,
        openai_api_key=ZHIPU_API_KEY,
        openai_api_base=ZHIPU_BASE_URL,
    )


def demo_simple_chain(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]
    StrOutputParser = deps["StrOutputParser"]

    # 功能：最基础的 LCEL 链，prompt -> chat model -> string parser。
    #
    # OpenAI 原代码：
    # prompt = ChatPromptTemplate.from_template("tell me a short joke about {topic}")
    # model = ChatOpenAI()
    # output_parser = StrOutputParser()
    # chain = prompt | model | output_parser
    # chain.invoke({"topic": "bears"})
    prompt = ChatPromptTemplate.from_template("tell me a short joke about {topic}")
    model = build_zhipu_chat_model(ChatOpenAI)
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser

    return chain.invoke({"topic": "bears"})


def build_retriever(deps):
    DocArrayInMemorySearch = deps["DocArrayInMemorySearch"]
    OpenAIEmbeddings = deps["OpenAIEmbeddings"]

    # 功能：把文本转为向量，建立内存向量库，再按问题做语义检索。
    #
    # OpenAI 原代码：
    # vectorstore = DocArrayInMemorySearch.from_texts(
    #     ["harrison worked at kensho", "bears like to eat honey"],
    #     embedding=OpenAIEmbeddings()
    # )
    vectorstore = DocArrayInMemorySearch.from_texts(
        ["harrison worked at kensho", "bears like to eat honey"],
        embedding=build_zhipu_embeddings(OpenAIEmbeddings),
    )
    return vectorstore.as_retriever()


def demo_retriever(deps):
    retriever = build_retriever(deps)

    # 功能：只看检索器本身返回哪些文档，不调用聊天模型。
    #
    # OpenAI 原代码：
    # retriever.get_relevant_documents("where did harrison work?")
    # retriever.get_relevant_documents("what do bears like to eat")
    harrison_docs = retriever.get_relevant_documents("where did harrison work?")
    bear_docs = retriever.get_relevant_documents("what do bears like to eat")

    return {
        "where did harrison work?": harrison_docs,
        "what do bears like to eat": bear_docs,
    }


def demo_rag_chain(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]
    RunnableMap = deps["RunnableMap"]
    StrOutputParser = deps["StrOutputParser"]

    retriever = build_retriever(deps)
    model = build_zhipu_chat_model(ChatOpenAI)
    output_parser = StrOutputParser()

    # 功能：RAG。RunnableMap 先并行构造 context/question，再把它们交给 prompt 和模型。
    #
    # OpenAI 原代码：
    # chain = RunnableMap({
    #     "context": lambda x: retriever.get_relevant_documents(x["question"]),
    #     "question": lambda x: x["question"]
    # }) | prompt | model | output_parser
    template = """Answer the question based only on the following context:
{context}

Question: {question}
"""
    prompt = ChatPromptTemplate.from_template(template)

    inputs = RunnableMap(
        {
            "context": lambda x: retriever.get_relevant_documents(x["question"]),
            "question": lambda x: x["question"],
        }
    )
    chain = inputs | prompt | model | output_parser

    return {
        "inputs": inputs.invoke({"question": "where did harrison work?"}),
        "answer": chain.invoke({"question": "where did harrison work?"}),
    }


def weather_tool():
    # OpenAI 原代码是 functions=[{"name": ..., "parameters": ...}]。
    # 智谱当前推荐使用 tools=[{"type": "function", "function": {...}}]。
    return {
        "type": "function",
        "function": {
            "name": "weather_search",
            "description": "Search for weather given an airport code",
            "parameters": {
                "type": "object",
                "properties": {
                    "airport_code": {
                        "type": "string",
                        "description": "The airport code to get the weather for",
                    },
                },
                "required": ["airport_code"],
            },
        },
    }


def sports_tool():
    return {
        "type": "function",
        "function": {
            "name": "sports_search",
            "description": "Search for news of recent sport events",
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {
                        "type": "string",
                        "description": "The sports team to search for",
                    },
                },
                "required": ["team_name"],
            },
        },
    }


def demo_single_tool_call(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]

    # 功能：单工具 function/tool calling。模型只负责返回 tool_calls，不会真的执行函数。
    #
    # OpenAI 原代码：
    # functions = [{"name": "weather_search", ...}]
    # model = ChatOpenAI(temperature=0).bind(functions=functions)
    # runnable = prompt | model
    # runnable.invoke({"input": "what is the weather in sf"})
    prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
    model = build_zhipu_chat_model(ChatOpenAI).bind(
        tools=[weather_tool()],
        tool_choice="auto",
    )
    runnable = prompt | model

    return runnable.invoke({"input": "what is the weather in sf"})


def demo_multi_tool_choice(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]

    # 功能：多工具选择。模型根据用户输入决定调用天气工具还是体育工具。
    #
    # OpenAI 原代码：
    # functions = [weather_search, sports_search]
    # model = model.bind(functions=functions)
    # runnable.invoke({"input": "how did the patriots do yesterday?"})
    prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
    model = build_zhipu_chat_model(ChatOpenAI).bind(
        tools=[weather_tool(), sports_tool()],
        tool_choice="auto",
    )
    runnable = prompt | model

    return runnable.invoke({"input": "how did the patriots do yesterday?"})


def demo_json_output_with_fallback(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]
    StrOutputParser = deps["StrOutputParser"]

    challenge = (
        "write three poems in a json blob, where each poem is a json blob "
        "of a title, author, and first line"
    )

    # 功能：结构化 JSON 输出，并用 LangChain 的 with_fallbacks 做降级。
    #
    # OpenAI 原代码：
    # simple_model = OpenAI(model="gpt-3.5-turbo-instruct", temperature=0)
    # simple_chain = simple_model | json.loads
    # model = ChatOpenAI(temperature=0)
    # chain = model | StrOutputParser() | json.loads
    # final_chain = simple_chain.with_fallbacks([chain])
    #
    # 智谱没有必要沿用 instruct completion 示例；这里直接用 chat.completions + JSON 模式。
    json_prompt = ChatPromptTemplate.from_template(
        "Return only valid JSON. Do not wrap it in markdown.\n\n{challenge}"
    )
    json_model = build_zhipu_chat_model(ChatOpenAI).bind(
        response_format={"type": "json_object"}
    )
    primary_chain = json_prompt | json_model | StrOutputParser() | json.loads

    fallback_prompt = ChatPromptTemplate.from_template(
        "Write a valid JSON object only. No markdown.\n\n{challenge}"
    )
    fallback_chain = fallback_prompt | build_zhipu_chat_model(ChatOpenAI) | StrOutputParser() | json.loads
    final_chain = primary_chain.with_fallbacks([fallback_chain])

    return final_chain.invoke({"challenge": challenge})


async def demo_invoke_batch_stream_async(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]
    StrOutputParser = deps["StrOutputParser"]

    # 功能：LCEL 的 invoke、batch、stream、ainvoke 四种调用形态。
    #
    # OpenAI 原代码：
    # chain.invoke({"topic": "bears"})
    # chain.batch([{"topic": "bears"}, {"topic": "frogs"}])
    # for t in chain.stream({"topic": "bears"}): print(t)
    # response = await chain.ainvoke({"topic": "bears"})
    prompt = ChatPromptTemplate.from_template("Tell me a short joke about {topic}")
    model = build_zhipu_chat_model(ChatOpenAI)
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser

    stream_chunks = []
    for chunk in chain.stream({"topic": "bears"}):
        stream_chunks.append(chunk)

    return {
        "invoke": chain.invoke({"topic": "bears"}),
        "batch": chain.batch([{"topic": "bears"}, {"topic": "frogs"}]),
        "stream": "".join(stream_chunks),
        "ainvoke": await chain.ainvoke({"topic": "bears"}),
    }


def print_result(title, value):
    print(f"\n=== {title} ===")
    print(value)


def print_failure(title, exc):
    print(f"\n=== {title} ===")
    print(f"跳过：{type(exc).__name__}: {exc}")


def run_demo(title, demo_func, deps):
    try:
        print_result(title, demo_func(deps))
    except Exception as exc:
        print_failure(title, exc)


async def run_async_demo(title, demo_func, deps):
    try:
        print_result(title, await demo_func(deps))
    except Exception as exc:
        print_failure(title, exc)


async def main():
    deps = load_langchain_dependencies()

    run_demo("1. simple chain", demo_simple_chain, deps)
    run_demo("2. retriever", demo_retriever, deps)
    run_demo("3. RAG chain", demo_rag_chain, deps)
    run_demo("4. single tool call", demo_single_tool_call, deps)
    run_demo("5. multi tool choice", demo_multi_tool_choice, deps)
    run_demo("6. JSON output with fallback", demo_json_output_with_fallback, deps)
    await run_async_demo("7. invoke/batch/stream/ainvoke", demo_invoke_batch_stream_async, deps)


if __name__ == "__main__":
    asyncio.run(main())
