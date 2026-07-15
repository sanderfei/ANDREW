import asyncio
import json
from _runtime import env



ZHIPU_API_KEY = env("ZHIPU_API_KEY")
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
ZHIPU_EMBEDDING_MODEL = "embedding-3"
STABLE_TEMPERATURE = 0.1

def run(title, func, deps):
    try:
        print(f"Running {title}...")
        value = func(deps)
        print(f"result: {value}")
    except Exception as exc:
        print(f"跳过：{type(exc).__name__}: {exc}")
    
async def run_async(title, func, deps):
    try:
        print(f"Running {title}...")
        value = await func(deps)
        print(f"result: {value}")
    except Exception as exc:
        print(f"跳过：{type(exc).__name__}: {exc}")

def load_dependencies():
    try:
        # Simulate loading dependencies
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.runnables import RunnableMap
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from langchain_community.vectorstores import DocArrayInMemorySearch
    except Exception as exc:
       raise RuntimeError(f"加载依赖失败：{type(exc).__name__}: {exc}")
    
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

def simple_chain_demo(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    StrOutputParser = deps["StrOutputParser"]

    prompt = ChatPromptTemplate.from_template("tell me a joke about {topic}")
    model = build_zhipu_chat_model(deps["ChatOpenAI"])
    output_parser = StrOutputParser()# 输出解析器
    # langchain 重载运算符标识链式结构
    # 注意链顺序：左边的输出，必须刚好是右边能接收的输入。这个就是 LCEL 链的核心规则
    chain = prompt | model | output_parser
    return chain.invoke({"topic": "programming"})

def build_zhipu_embeddings(OpenAIEmbeddings):
    # 向量模型
    return


def build_retriever(deps):
    OpenAIEmbeddings = deps["OpenAIEmbeddings"]
    DocArrayInMemorySearch = deps["DocArrayInMemorySearch"]

    # 是从文本创建一个内存向量库
    vectorstore = DocArrayInMemorySearch.from_texts(
        ["harrison worked at kensho", "bears like to eat honey"],
        # 指定向量模型
        embedding = OpenAIEmbeddings(
            model=ZHIPU_EMBEDDING_MODEL,
            openai_api_key=ZHIPU_API_KEY,
            openai_api_base=ZHIPU_BASE_URL,
        ),
    )
    # retriever 是 LangChain 里统一的“检索器接口”，它把底层向量库的细节封装起来，提供一个统一的接口来获取相关文档
    return vectorstore.as_retriever()

def retriever_demo(deps):
    # 构建检索器
    retriever = build_retriever(deps)
    # 检索问题
    harrison_docs = retriever.get_relevant_documents("where did harrison work?")
    bear_docs = retriever.get_relevant_documents("what do bears like to eat")

    return {
        "where did harrison work?": harrison_docs,
        "what do bears like to eat": bear_docs,
    }

def rag_chain_demo(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]
    RunnableMap = deps["RunnableMap"]
    StrOutputParser = deps["StrOutputParser"]

    retriever = build_retriever(deps)
    model = build_zhipu_chat_model(ChatOpenAI)
    output_parser = StrOutputParser()

    template = """Answer the question based only on the following context: {context}
    Question: {question}"""
    prompt = ChatPromptTemplate.from_template(template)

    # 它的作用是：把一个输入同时加工成多个字段。在这个例子里，它把输入的 question 字段，既用来检索相关文档（context），又直接传递给 prompt 模板。这样就实现了一个 RAG（Retrieval-Augmented Generation）链：先检索相关文档，再把文档和问题一起输入到生成模型里，最后解析输出答案。
    inputs = RunnableMap(
    {
            # 从输入的 question 字段，获取相关文档，作为 context 字段的值
            "context": lambda x: retriever.get_relevant_documents(x["question"]),
            # 把输入的 question 字段，直接传递给 prompt 模板，作为 question 字段的值
            "question": lambda x: x["question"],
        }
    )

    chain = inputs | prompt | model | output_parser
    return {
        #问题 -> 构造 prompt 需要的输入 只是检索相关文档，并把原问题保留下来 =>给模型准备了什么上下文
        "inputs": inputs.invoke({"question": "where did harrison work?"}),
        #调的是完整链：=>模型基于这些上下文最终回答了什么
        "answer": chain.invoke({"question": "where did harrison work?"}),
    }

def weather_tool():
    return  {
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
                    }
                },
                "required": ["airport_code"],
            },
        }
    }

def single_tool_chain_demo(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]
    prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
    model = build_zhipu_chat_model(ChatOpenAI).bind(
        tools=[weather_tool()],
        tool_choice="auto",
    )
    runnable = prompt | model
    return runnable.invoke({"input": "what's the weather like in sf?"})

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

def multi_tool_chain_demo(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]

    prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
    model = build_zhipu_chat_model(ChatOpenAI).bind(
        tools=[weather_tool(), sports_tool()],
        tool_choice="auto",
    )
    runnable = prompt | model
    return runnable.invoke({"input": "how did the patriots do yesterday?"})

def fallback_chain_demo(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]
    StrOutputParser = deps["StrOutputParser"]

    challenge = (
        "write three poems in a json blob, where each poem is a json blob "
        "of a title, author, and first line"
    )

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

async def batch_stream_async_demo(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]
    StrOutputParser = deps["StrOutputParser"]
    prompt = ChatPromptTemplate.from_template("Tell me a short joke about {topic}")
    model = build_zhipu_chat_model(ChatOpenAI)
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser

    stream_chunks = []
    for chunk in chain.stream({"topic": "bears"}):
        stream_chunks.append(chunk)

    return {
        "invoke": chain.invoke({"topic": "bears"}),#单次同步调用
        "batch": chain.batch([{"topic": "bears"}, {"topic": "frogs"}]),#批量同步调用
        "stream": "".join(stream_chunks),#流式同步调用
        "ainvoke": await chain.ainvoke({"topic": "bears"}),#单次异步调用
    }

async def batch_stream_async_demo2(deps):
    ChatPromptTemplate = deps["ChatPromptTemplate"]
    ChatOpenAI = deps["ChatOpenAI"]
    StrOutputParser = deps["StrOutputParser"]

    prompt = ChatPromptTemplate.from_template("Tell me a short joke about {topic}")
    model = build_zhipu_chat_model(ChatOpenAI)
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser

    async def collect_stream(payload):
        chunks = []
        async for chunk in chain.astream(payload):
            chunks.append(chunk)
        return "".join(chunks)

    invoke_task = chain.ainvoke({"topic": "bears"})
    batch_task = chain.abatch([{"topic": "bears"}, {"topic": "frogs"}])
    stream_task = collect_stream({"topic": "bears"})
    another_task = chain.ainvoke({"topic": "programming"})

    # 异步原语
    invoke_result, batch_result, stream_result, another_result = await asyncio.gather(
        invoke_task,
        batch_task,
        stream_task,
        another_task,
    )

    return {
        "ainvoke": invoke_result,
        "abatch": batch_result,
        "astream": stream_result,
        "another_ainvoke": another_result,
    }

async def main():
    deps = load_dependencies()

    # run("simple chain", simple_chain_demo, deps)
    # run("retriever", retriever_demo, deps)
    # run("RAG chain", rag_chain_demo, deps)
    # run("single_tool_chain", single_tool_chain_demo, deps)
    # run("multi_tool_chain", multi_tool_chain_demo, deps)
    # run("fallback_chain", fallback_chain_demo, deps)
    # await run_async("batch_stream_async_demo", batch_stream_async_demo, deps)
    await run_async("batch_stream_async_demo2", batch_stream_async_demo2, deps)


if __name__ == "__main__":
    asyncio.run(main())
