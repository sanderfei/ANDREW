# LangChain 基础语法笔记

这份笔记整理 `andrew` 项目中 [2_langchain](2_langchain) 和 [3_rag_from_scratch](3_rag_from_scratch) 逐步出现的 LangChain 语法。

它与 [2_langchain/LangChain知识点总结.md](2_langchain/LangChain知识点总结.md) 的区别是：原总结按 L1～L12 回顾每课内容；本文按语法/API 分类，重点说明“怎么读、输入输出是什么、什么时候真正执行”。

本文依据当前项目环境整理：`langchain 1.3.11`、`langchain-core 1.4.8`。新代码优先参考 `3_rag_from_scratch` 中的 LangChain 1.x 写法。

## 1. 两个目录的学习主线

### 1.1 `2_langchain`：从模型调用走到 Agent

```text
L1  原生 Tool Calling 协议
L2  Runnable、LCEL、Prompt | Model | Parser
L3  Pydantic Schema、model.bind(tools=...)
L4  PydanticToolsParser 结构化抽取
L5  @tool、tool.invoke()、手写工具路由
L6  create_agent、Memory、状态流
L7  ToolStrategy、structured_response
L8  Sandbox、Middleware、Skills、SubAgent
L9  Document、Embedding、VectorStore、Retriever
L10 固定 RAG 与 Agentic RAG
L11 受限 SQL Tools
L12 RunnableGenerator 异步流式管道
```

### 1.2 `3_rag_from_scratch`：拆开 RAG 的每一层

```text
Part 1  Document → Indexing → Retrieval → Generation
Part 2  Splitter、embed_documents、embed_query、VectorStore
Part 3  retriever.invoke、batch、score、MMR
Part 4  Prompt → Model → Parser、拒答、citation
Part 5  RunnableLambda、Multi Query、retriever.map
Part 15 retriever.batch、RRF 多路排名融合
```

## 2. Runnable：统一的可运行接口

`Runnable` 可以先理解成：

```text
输入 → 一个处理步骤 → 输出
```

Prompt、Chat Model、Output Parser、Retriever，以及由多个组件组成的 Chain，都可以表现为 Runnable 或提供相同风格的运行接口。

| 方法 | 含义 | 典型返回值 |
| --- | --- | --- |
| `invoke(input)` | 同步处理一个输入 | 一个输出 |
| `batch(inputs)` | 同步处理多个输入 | 输出列表 |
| `stream(input)` | 同步流式处理 | 输出片段迭代器 |
| `ainvoke(input)` | 异步处理一个输入 | `await` 后得到一个输出 |
| `abatch(inputs)` | 异步批量处理 | `await` 后得到输出列表 |
| `astream(input)` | 异步流式处理 | 异步输出流 |

[L2_LangChainExpressLanguage_LCEL.py](2_langchain/L2_LangChainExpressLanguage_LCEL.py) 中的调用形式：

```python
one = chain.invoke({"topic": "bears"})

many = chain.batch([
    {"topic": "bears"},
    {"topic": "frogs"},
])

for chunk in chain.stream({"topic": "bears"}):
    print(chunk)

one_async = await chain.ainvoke({"topic": "bears"})
```

最重要的规则：

```python
chain = prompt | model | parser  # 只定义流程，没有执行
answer = chain.invoke(data)      # 此时才真正执行
```

## 3. LCEL 管道 `|`

LCEL 是 LangChain Expression Language。最基础的 Chain 是：

```python
chain = prompt | model | StrOutputParser()
answer = chain.invoke({"topic": "LangChain"})
```

`|` 表示把左边输出交给右边作为输入，大致等价于：

```python
prompt_value = prompt.invoke({"topic": "LangChain"})
model_message = model.invoke(prompt_value)
answer = StrOutputParser().invoke(model_message)
```

类型流转：

```text
dict
  ↓ ChatPromptTemplate
ChatPromptValue
  ↓ Chat Model
AIMessage
  ↓ StrOutputParser
str
```

外层管道按顺序执行：Prompt 完成后 Model 才能开始，Model 完成后 Parser 才能开始。

普通 Python 函数也能进入 LCEL。例如 [3_rag_from_scratch/_common.py](3_rag_from_scratch/_common.py) 中：

```python
retriever | format_documents
```

相当于：

```python
documents = retriever.invoke(question)
context = format_documents(documents)
```

```text
question: str → list[Document] → context: str
```

## 4. Prompt、Model、Message、Parser

### 4.1 Prompt

单模板：

```python
prompt = ChatPromptTemplate.from_template(
    "Context: {context}\nQuestion: {question}"
)

prompt_value = prompt.invoke({
    "context": "检索到的资料",
    "question": "什么是 RAG？",
})
```

多角色消息：

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个乐于助人的助手。"),
    ("user", "{input}"),
])
```

Prompt 只负责组织消息，不负责调用模型或生成答案。

### 4.2 Model 与 Message

```python
message = model.invoke("你好")
```

Chat Model 通常返回 `AIMessage`：

```python
message.content     # 普通回答文本
message.tool_calls  # 模型提出的工具调用请求
```

`tool_calls` 不表示 Python 工具已经执行。

### 4.3 Output Parser

`StrOutputParser()` 主要完成：

```text
AIMessage(content="...") → str
```

放在 Chain 中时，类型流转是：

```text
Prompt
  ↓
Chat Model
  ↓
AIMessage(
    content="最终回答",
    response_metadata={...},
    tool_calls=[...],
)
  ↓ StrOutputParser()
"最终回答"
  ↑ 对外类型契约为 str
```

因此下面两段代码作用相同：

```python
chain = prompt | model | StrOutputParser()
answer = chain.invoke(payload)
```

```python
prompt_value = prompt.invoke(payload)
model_message = model.invoke(prompt_value)       # AIMessage
answer = StrOutputParser().invoke(model_message) # str
```

当前本地 `langchain-core` 的内部过程可以简化为：

```text
AIMessage
  → 包装成 ChatGeneration
  → 读取第一个 Generation 的 .text
  → StrOutputParser.parse(text)
  → 原样返回 text
```

`StrOutputParser.parse()` 本身近似于：

```python
def parse(self, text: str) -> str:
    return text
```

如果左边已经返回 `str`，它也会直接得到相同字符串。因此目录 3 的在线 `ChatOpenAI` 返回 `AIMessage` 时，它负责提取文本；离线 `RunnableLambda(_offline_answer)` 已经返回 `str` 时，它相当于统一输出接口。最终调用方不必区分两种模型，得到的都是 `answer: str`。

精确到当前本地 `langchain-core 1.4.8` 的运行时实现，从 `AIMessage` 提取出的值可能是 `TextAccessor`，它是 `str` 的子类，所以 `isinstance(answer, str)` 仍为 `True`，可以按普通字符串使用；从普通 `str` 输入时则原样返回该字符串。

它不会完成以下工作：

- 不调用模型，也不生成答案。
- 不检查答案是否正确或忠于 context。
- 不验证 JSON、Pydantic schema 或 citation。
- 不保留 `response_metadata`、token usage 等完整 `AIMessage` 信息。
- 不执行 `tool_calls`；如果模型主要返回工具调用而文本为空，解析结果也可能是空字符串。

它不保证字符串一定是合法 JSON。JSON 链还需要：

```python
chain = prompt | model | StrOutputParser() | json.loads
```

如果后续需要工具调用或完整模型元数据，就不要立刻接 `StrOutputParser()`，而应先保留和检查原始 `AIMessage`。

## 5. 控制 Runnable 输入的四种核心语法

### 5.1 `RunnableLambda`：普通函数变成 Runnable

[part5_multi_query.py](3_rag_from_scratch/part5_multi_query.py) 中：

```python
query_generator = RunnableLambda(
    lambda value: build_query_variants(
        str(value),
        use_live=options.use_live,
    )
)

queries = query_generator.invoke(question)
```

执行关系：

```text
query_generator.invoke(question)
                       │
                       ▼
             value = question
                       │
                       ▼
build_query_variants(str(question), use_live=...)
                       │
                       ▼
                 queries: list[str]
```

等价的普通函数写法：

```python
def generate_queries(value):
    return build_query_variants(
        str(value),
        use_live=options.use_live,
    )

query_generator = RunnableLambda(generate_queries)
queries = query_generator.invoke(question)
```

如果不需要组合 Chain，直接调用普通函数也能得到相同业务结果。包装后的区别是可以继续使用 `invoke()`、`batch()`、`map()` 和 `|`。

这里 `value` 来自将来的 `invoke()`；`options.use_live` 是 lambda 捕获的外部变量。

### 5.2 `lambda _: queries`：接收但忽略输入

```python
RunnableLambda(lambda _: queries).invoke(question)
```

`_` 仍然是入参，只是 Python 约定用它表示“不会使用这个参数”。执行过程：

```text
接收 question → 忽略 question → 返回外部的 queries
```

它不是直接透传 `question`。

### 5.3 `RunnablePassthrough()`：原样传递

```python
result = RunnablePassthrough().invoke(question)
```

输出仍是原来的 `question`。固定 RAG 中常写成：

```python
{
    "context": retriever | format_documents,
    "question": RunnablePassthrough(),
}
```

```text
question
  ├─ retriever → list[Document] → format_documents → context
  └─ RunnablePassthrough                         → question
```

### 5.4 `RunnableMap({...})`：多个命名分支

[L2_LangChainExpressLanguage_LCEL.py](2_langchain/L2_LangChainExpressLanguage_LCEL.py) 中：

```python
inputs = RunnableMap({
    "context": lambda x: retriever.get_relevant_documents(
        x["question"]
    ),
    "question": lambda x: x["question"],
})
```

`RunnableMap` 当前是 `RunnableParallel` 的别名：同一份输入进入多个命名分支，最后组装成字典。

当前 LCEL 也可以直接写字典：

```python
{
    "context": retriever | format_documents,
    "question": RunnablePassthrough(),
}
```

当字典参与 LCEL 组合时，LangChain 会把它转换为并行命名分支。

### 5.5 `runnable.map()`：列表逐项执行

Part 5：

```python
per_query_documents = (
    RunnableLambda(lambda _: queries)
    | retriever.map()
).invoke(question)
```

把 `RunnableLambda` 的参数换行书写也完全等价：

```python
queries_documents = (
    RunnableLambda(
        lambda _: queries
    ) | retriever.map()
).invoke(question)
```

这仍然是同一条 Chain：`RunnableLambda(...)` 先输出 `queries`，再由 `retriever.map()` 对列表中的每个 query 执行检索，最后 `.invoke(question)` 启动整条 Chain。`queries_documents` 作为变量名可以运行，但返回值表示“每个 query 各自对应的一组 Documents”，所以 `per_query_documents` 更能体现其 `list[list[Document]]` 的嵌套结构。改名时，后续所有引用也必须同步修改。

逐步展开：

```python
query_list = RunnableLambda(
    lambda _: queries
).invoke(question)

per_query_documents = retriever.map().invoke(query_list)
```

类型流转：

```text
question: str
  ↓ RunnableLambda(lambda _: queries)
queries: list[str]
  ↓ retriever.map()
per_query_documents: list[list[Document]]
```

每个 query 单独执行一次 `retriever.invoke(query)`。外层 `|` 顺序执行；`.map()` 内部使用批处理，默认同步实现通常可以用线程池并发。返回列表仍与输入顺序对应。

### 5.6 三种 map 速查

| 写法 | 作用 | 输出 |
| --- | --- | --- |
| `RunnableMap({...})` | 同一个输入进入多个命名分支 | `dict` |
| LCEL 中的 `{...}` | 自动转换为命名并行分支 | `dict` |
| `runnable.map()` | 列表每一项执行同一个 Runnable | `list[output]` |

## 6. `invoke`、`batch`、`map` 的类型区别

```python
documents = retriever.invoke(question)
```

```text
str → list[Document]
```

```python
document_lists = retriever.batch(questions)
```

```text
list[str] → list[list[Document]]
```

```python
document_lists = retriever.map().invoke(questions)
```

`batch(questions)` 立即执行；`map()` 先返回新 Runnable，之后 `invoke(questions)` 才执行。默认批处理可以并发，但输出顺序与输入顺序对应。

## 7. RAG 的基础对象与 API

### 7.1 `Document`

```python
document = Document(
    page_content="任务分解会把复杂任务拆成更小的步骤。",
    metadata={
        "source": "agent-planning.md",
        "topic": "planning",
    },
)
```

| 字段 | 含义 |
| --- | --- |
| `page_content` | 用于切块、Embedding、检索和注入 Prompt 的正文 |
| `metadata` | 来源、页码、章节、起始位置等附加信息 |

Loader 通常完成：

```text
网页或文件 → list[Document]
```

它不负责向量化或生成回答。

### 7.2 `RecursiveCharacterTextSplitter`

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    add_start_index=True,
)
chunks = splitter.split_documents(documents)
```

```text
list[Document 原文] → list[Document chunk]
```

`add_start_index=True` 会在 metadata 中记录 chunk 的字符起始位置。

直接构造 `RecursiveCharacterTextSplitter` 时，默认长度函数是 Python 的 `len()`：

```python
RecursiveCharacterTextSplitter(
    chunk_size=140,
    chunk_overlap=30,
)
```

因此这里的 `140` 和 `30` 按字符数量衡量，不是按英文单词数量，也不是按模型 token 数量衡量。

[part2_chunking_parameter_comparison.py](3_rag_from_scratch/part2_chunking_parameter_comparison.py) 还使用：

```python
RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=140,
    chunk_overlap=30,
)
```

`from_tiktoken_encoder()` 是一个类方法形式的工厂：它仍然创建 `RecursiveCharacterTextSplitter`，但把长度函数换成指定 tiktoken 编码器的 token 计数。因此这里的 `140` 和 `30` 按 `cl100k_base` token 数衡量。

两种写法没有改变递归分隔逻辑，仍会依次尝试段落、换行、空格和字符等边界；改变的是“怎样计算当前片段有多长”：

| 写法 | `chunk_size` / `chunk_overlap` 的单位 | 分隔策略 |
| --- | --- | --- |
| 直接构造 | 默认是 Python `len()` 计算的字符数 | 递归字符分隔 |
| `from_tiktoken_encoder(...)` | 指定 tiktoken 编码器计算的 token 数 | 递归字符分隔 |

它和“字符与英文单词”的区别不完全相同。token 是 tokenizer 划分出的模型计费/上下文单位：一个英文单词可能对应一个或多个 token，一个汉字或标点也可能占一个或多个 token。

还要注意两点：

- `add_start_index=True` 保存的 `start_index` 仍然是原文中的字符偏移量。
- `cl100k_base` 只是这里用于控制切块长度的 tokenizer，与本地 MiniLM 或在线聊天模型自己的 tokenizer 不一定相同，所以它提供的是一致的近似预算，不是所有模型都完全一致的真实 token 数。

### 7.3 `Embeddings` 的隐藏接口合同

[3_rag_from_scratch/_common.py](3_rag_from_scratch/_common.py) 中：

```python
class StableHashEmbeddings(Embeddings):
    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        ...

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        ...
```

| 方法 | 调用阶段 | 输入 | 输出 |
| --- | --- | --- | --- |
| `embed_documents(texts)` | 文档入库 | `list[str]` | `list[list[float]]` |
| `embed_query(text)` | 用户查询 | `str` | `list[float]` |

`build_embeddings()` 返回的是 Embeddings 对象，不是某一个向量。

[part2_offline_vs_glm_embeddings.py](3_rag_from_scratch/part2_offline_vs_glm_embeddings.py) 中不同 Embedding 实现都遵守这两个方法，因此上层 VectorStore 调用方式相同。

### 7.4 `InMemoryVectorStore`

```python
vector_store = InMemoryVectorStore.from_documents(
    documents=chunks,
    embedding=embeddings,
)
```

`embedding=embeddings` 传入的是文本转向量对象，不是布尔值或单个向量。

```text
索引：Document → embed_documents → 文档向量 → VectorStore
查询：question → embed_query → 查询向量 → 相似度排序
```

`InMemoryVectorStore` 只在当前进程内保存数据。

### 7.5 搜索与 Retriever

只返回文档：

```python
documents = vector_store.similarity_search(question, k=2)
# list[Document]
```

同时返回分数：

```python
matches = vector_store.similarity_search_with_score(
    question,
    k=3,
)
# list[tuple[Document, float]]
```

当前 InMemoryVectorStore 的 score 是相似度，不是“答案正确概率”。

包装成 Retriever：

```python
retriever = vector_store.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 2},
)

documents = retriever.invoke(question)
```

`as_retriever()` 不会创建第二份向量库，只是套上标准 Retriever/Runnable 接口。

`2_langchain/L2` 保留了旧教程的 `get_relevant_documents(question)`；当前项目新代码优先使用 `retriever.invoke(question)`。

MMR：

```python
retriever = vector_store.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 3,
        "fetch_k": 6,
        "lambda_mult": 0.5,
    },
)
```

- `fetch_k`：第一阶段候选数。
- `k`：最终返回数。
- `lambda_mult`：越接近 1 越偏相关性，越接近 0 越偏多样性。

多样性不等于正确性，MMR 仍可能选入无关资料。

## 8. 固定两步 RAG 的完整 LCEL

[3_rag_from_scratch/_common.py](3_rag_from_scratch/_common.py)：

```python
def build_rag_chain(retriever, *, use_live: bool):
    return (
        {
            "context": retriever | format_documents,
            "question": RunnablePassthrough(),
        }
        | build_rag_prompt()
        | build_chat_model(use_live=use_live)
        | StrOutputParser()
    )
```

执行：

```python
answer = build_rag_chain(
    retriever,
    use_live=False,
).invoke(question)
```

完整数据流：

```text
question
  ├─ retriever → list[Document] → format_documents → context
  └─ RunnablePassthrough                         → question
                        ↓
             {"context": str, "question": str}
                        ↓ Prompt
                 ChatPromptValue
                        ↓ Model
                    AIMessage
                        ↓ Parser
                   answer: str
```

展开成普通代码：

```python
documents = retriever.invoke(question)
context = format_documents(documents)
prompt_value = prompt.invoke({
    "context": context,
    "question": question,
})
message = model.invoke(prompt_value)
answer = parser.invoke(message)
```

因此模型看不到向量或完整向量库，只看到放进 Prompt 的 context 和 question。

[part4_1_generation.py](3_rag_from_scratch/part4_1_generation.py) 同时演示：

- 手动先调用 `retriever.invoke()`，Chain 只包含 Prompt → Model → Parser。
- 通过 `build_rag_chain()` 把 Retriever 也封装进完整 Chain。

[part4_2_answer_with_citations.py](3_rag_from_scratch/part4_2_answer_with_citations.py) 中的 score gate、拒答和 citation 是项目自己的 Python 业务逻辑，不是 Retriever 自动提供的：

```text
candidates
  ├─ retrieval：保留全部候选用于审计
  └─ accepted：通过阈值的候选
       ├─ 生成模型 context
       └─ citations
```

## 9. Multi Query 与 RRF

### 9.1 Multi Query

[part5_multi_query.py](3_rag_from_scratch/part5_multi_query.py) 的完整类型流：

```text
question: str
  ↓ RunnableLambda + build_query_variants
queries: list[str]
  ↓ retriever.map()
per_query_documents: list[list[Document]]
  ↓ unique_union
merged_documents: list[Document]
  ↓ format_documents
context: str
  ↓ Prompt → Model → Parser
answer: str
```

`unique_union()` 是项目普通 Python 函数，按 `page_content + metadata` 去重，并保留首次出现顺序。

### 9.2 RRF

[part15_reciprocal_rank_fusion_reranking.py](3_rag_from_scratch/part15_reciprocal_rank_fusion_reranking.py)：

```python
queries = build_query_variants(question, use_live=use_live)[:4]
ranked_lists = retriever.batch(queries)
fused = reciprocal_rank_fusion(ranked_lists, k=60)
```

```text
queries: list[str]
  ↓ retriever.batch
ranked_lists: list[list[Document]]
  ↓ reciprocal_rank_fusion
fused: list[tuple[Document, float]]
```

RRF 是项目中的 Python 排名融合函数，不调用 Chat Model，也不是 cross-encoder 语义重排模型。

## 10. Tool Calling：声明、请求、执行

必须分清：

```text
声明 Tool Schema
  ↓
模型生成 tool_calls 请求
  ↓
Python 或 Agent Runtime 执行 Tool
```

### 10.1 `model.bind(tools=...)`

```python
model_with_tools = model.bind(
    tools=[weather_tool],
    tool_choice="auto",
)

message = model_with_tools.invoke(user_input)
```

`bind()` 只返回一个绑定额外模型参数的新 Runnable；`invoke()` 时模型才执行。

`tool_choice="auto"` 表示模型可以决定是否调用工具。它不会自动执行 Python 函数，也不会自动把 Tool 结果回传给模型。

### 10.2 Pydantic Schema

```python
class WeatherSearch(BaseModel):
    """通过机场代码查询天气。"""

    airport_code: str = Field(
        description="机场代码，例如 SFO"
    )
```

`WeatherSearch.model_json_schema()` 可以生成模型可读的参数合同。Schema 描述参数，不负责真实业务执行或权限校验。

### 10.3 `@tool` 与 `tool.invoke()`

[L5_Tools_Routing_APIs.py](2_langchain/L5_Tools_Routing_APIs.py)：

```python
@tool(args_schema=OpenMeteoInput)
def current_weather_online(
    latitude: float,
    longitude: float,
) -> str:
    """根据经纬度查询实时天气。"""
    ...
```

执行 Tool：

```python
result = current_weather_online.invoke({
    "latitude": 37.7749,
    "longitude": -122.4194,
})
```

LangChain 会利用函数名、docstring、类型注解或 `args_schema` 生成 Tool 描述。手写路由的真正执行点是：

```python
result = tool_map[tool_call["name"]].invoke(
    tool_call["args"]
)
```

### 10.4 `content_and_artifact`

[L10_RAG_Agent.py](2_langchain/L10_RAG_Agent.py)：

```python
@tool(response_format="content_and_artifact")
def retrieve_context(query: str):
    """Retrieve information to help answer a query."""

    documents = vector_store.similarity_search(query, k=2)
    content = format_documents(documents)
    return content, documents
```

函数必须返回 `(content, artifact)`：

| 值 | 用途 |
| --- | --- |
| `content` | `ToolMessage.content`，给模型读取 |
| `artifact` | `ToolMessage.artifact`，给程序保留原始对象 |

直接用普通参数字典调用：

```python
content = retrieve_context.invoke({"query": query})
```

通常直接得到 `content`。Agent 使用真正的 ToolCall 调用时，LangChain 才构造带 `content` 和 `artifact` 的 `ToolMessage`。

`artifact` 不会自动展示给前端，应用需要自己从状态中提取。

## 11. 结构化输出

### 11.1 `PydanticToolsParser`

[L4_Tagging_Extraction.py](2_langchain/L4_Tagging_Extraction.py)：

```python
parser = PydanticToolsParser(
    tools=[Information],
    first_tool_only=True,
)

chain = prompt | model_with_tools | parser
result = chain.invoke({"input": source_text})
```

```text
自然语言 → 模型按 Schema 生成 tool_calls
         → PydanticToolsParser → Pydantic 对象
```

`first_tool_only=True` 只取第一个工具调用。结构化数据可能位于 `tool_calls` 中，所以原始 `AIMessage.content` 可能为空。

### 11.2 `ToolStrategy`

[L7_Agents_Structured_Output.py](2_langchain/L7_Agents_Structured_Output.py)：

```python
response_format = ToolStrategy(schema=ContactInfo)

agent = create_agent(
    model=model,
    tools=[],
    response_format=response_format,
)

result = agent.invoke({"messages": [...]})
```

```python
result["structured_response"]  # 校验后的业务对象
result["messages"]             # 完整执行轨迹
```

即使 `tools=[]`，结构化输出实现也可能在轨迹中出现 Schema 相关 Tool Call；它不是在执行天气或数据库业务工具。

## 12. `create_agent()`、Memory 与状态流

### 12.1 创建和调用 Agent

[L6_Agents_Memory_Streaming.py](2_langchain/L6_Agents_Memory_Streaming.py)：

```python
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
)

result = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": "查询旧金山天气",
        }
    ]
})
```

Agent 自动管理：

```text
HumanMessage
  ↓
AIMessage(tool_calls=[...])
  ↓ LangChain 执行 Tool
ToolMessage(content=工具结果)
  ↓
AIMessage(content=最终回答)
```

`agent.invoke()` 返回状态字典，不是单独的 `AIMessage`：

```python
messages = result["messages"]
final_message = messages[-1]
answer = final_message.content
```

查看全部 `messages` 才能确认 Agent 是否真的调用了 Tool。

当前 LangChain 也能根据普通 Python 函数的签名和 docstring 自动创建简单 Tool；需要 `args_schema` 或 `content_and_artifact` 时使用 `@tool(...)` 更明确。

### 12.2 Memory

```python
agent = create_agent(
    model=model,
    tools=tools,
    checkpointer=InMemorySaver(),
)

config = {
    "configurable": {
        "thread_id": "demo-thread",
    }
}

first = agent.invoke(first_input, config=config)
second = agent.invoke(second_input, config=config)
```

同一个 Agent/checkpointer 实例加同一个 `thread_id` 表示同一会话。更换 `thread_id` 是另一段会话；进程退出后 `InMemorySaver` 数据消失。

### 12.3 `stream_mode="values"`

```python
for state in agent.stream(
    {"messages": [...]},
    stream_mode="values",
):
    latest = state["messages"][-1]
```

这里每次得到的是当前完整状态快照，不是单个 token。最终 AI 回复通常可以这样筛选：

```python
if latest.type == "ai" and not latest.tool_calls:
    final_text = latest.content
```

## 13. 后续课程中的高级语法

### 13.1 `with_fallbacks()`

```python
final_chain = primary_chain.with_fallbacks([
    fallback_chain
])
```

主链抛异常时才尝试备用链。主链正常返回低质量文本时不会自动 fallback。

### 13.2 Middleware

[L8_Deep_Agent_From_Scratch.py](2_langchain/L8_Deep_Agent_From_Scratch.py)：

```python
agent = create_agent(
    model=model,
    tools=[],
    middleware=[
        FilesystemMiddleware(backend=backend),
        SummarizationMiddleware(model=model, backend=backend),
        SkillsMiddleware(backend=backend, sources=["/skills/"]),
    ],
)
```

Middleware 给 Agent 增加文件系统、摘要、Skills、任务规划和子 Agent 等能力。真实访问边界仍应由 sandbox/backend 或 Tool 代码限制。

### 13.3 SQL Agent

[L11_SQL_Agent.py](2_langchain/L11_SQL_Agent.py) 仍然是：

```text
受限 @tool 函数 + create_agent
```

“只能执行只读 SQL”由数据库权限和 Tool 内部校验保证，不是 `create_agent()` 自动保证。

### 13.4 `RunnableGenerator`

[L12_Voice_Agent.py](2_langchain/L12_Voice_Agent.py)：

```python
pipeline = (
    RunnableGenerator(stt_stream)
    | RunnableGenerator(agent_stage)
    | RunnableGenerator(tts_stream)
)

async for event in pipeline.atransform(audio_stream):
    ...
```

`RunnableGenerator` 把异步生成器包装成流式 LCEL 阶段：

```text
AsyncIterator[bytes]
  ↓ STT
AsyncIterator[VoiceAgentEvent]
  ↓ Agent
AsyncIterator[VoiceAgentEvent]
  ↓ TTS
AsyncIterator[VoiceAgentEvent]
```

## 14. 固定 RAG 与 Agentic RAG

固定 RAG 对应：

- [2_langchain/L10_RAG_Agent.py](2_langchain/L10_RAG_Agent.py) 的 `two_step_rag_chain_demo()`。
- [3_rag_from_scratch/_common.py](3_rag_from_scratch/_common.py) 的 `build_rag_chain()`。

Agentic RAG 对应 [2_langchain/L10_RAG_Agent.py](2_langchain/L10_RAG_Agent.py) 的 `build_rag_agent()`。

| 对比 | 固定 RAG | Agentic RAG |
| --- | --- | --- |
| 是否必定检索 | 是 | 不一定 |
| 谁决定检索时机 | 程序流程 | 模型 |
| 核心语法 | LCEL + Retriever | `create_agent` + Retrieval Tool |
| 特点 | 可预测 | 灵活，但控制和审计更复杂 |

两者不是新旧版本关系，而是控制流不同。

## 15. 输入输出合同速查

| 对象或调用 | 输入 | 输出 |
| --- | --- | --- |
| `prompt.invoke({...})` | Prompt 变量字典 | `ChatPromptValue` |
| `model.invoke(...)` | 字符串、消息或 PromptValue | `AIMessage` |
| `StrOutputParser().invoke(message)` | `AIMessage` | `str` |
| `RunnableLambda(fn).invoke(x)` | `fn` 的输入 | `fn` 的返回值 |
| `RunnablePassthrough().invoke(x)` | 任意 `x` | 原始 `x` |
| `RunnableMap({...}).invoke(x)` | 同一个 `x` | 分支结果 `dict` |
| `runnable.map().invoke(xs)` | `list[input]` | `list[output]` |
| `splitter.split_documents(docs)` | `list[Document]` | `list[Document]` chunks |
| `embed_documents(texts)` | `list[str]` | `list[list[float]]` |
| `embed_query(query)` | `str` | `list[float]` |
| `similarity_search(query, k)` | `str` | `list[Document]` |
| `similarity_search_with_score(...)` | `str` | `list[tuple[Document, float]]` |
| `retriever.invoke(query)` | `str` | `list[Document]` |
| `retriever.batch(queries)` | `list[str]` | `list[list[Document]]` |
| `tool.invoke(args)` | 参数字典 | Tool 业务结果 |
| `agent.invoke({"messages": ...})` | Agent 状态字典 | 含 `messages` 的状态字典 |
| Structured Agent | `messages` 状态 | `messages + structured_response` |

## 16. 最容易混淆的语法

| 容易混淆 | 正确理解 |
| --- | --- |
| 构造 Chain 与执行 Chain | `prompt | model` 只构造；`invoke()` 才执行 |
| `RunnableMap` 与 `.map()` | 前者创建命名分支；后者逐项处理列表 |
| `lambda _: queries` 与透传 | 前者忽略输入并返回 queries；透传用 `RunnablePassthrough` |
| `model.bind(tools=...)` 与执行 Tool | bind 只告诉模型 Tool Schema；本地运行时才执行 |
| Retriever 与答案 | Retriever 返回 Document；Model 才生成答案 |
| top-k 与“有答案” | top-k 总会尝试返回候选；是否可答需要业务 gate |
| `ToolMessage.content` 与 `artifact` | content 给模型；artifact 给程序 |
| Agent values stream 与 token stream | values 返回完整状态快照，不是单 token |
| 固定 RAG 与 Agentic RAG | 前者必定检索；后者由模型决定是否检索 |

## 17. 建议复习顺序

| 顺序 | 文件 | 重点 |
| --- | --- | --- |
| 1 | [2_langchain/L2_LangChainExpressLanguage_LCEL.py](2_langchain/L2_LangChainExpressLanguage_LCEL.py) | LCEL、Runnable、调用方式 |
| 2 | [2_langchain/L3_Function_Calling_In_Langchain.py](2_langchain/L3_Function_Calling_In_Langchain.py) | Schema、`bind(tools=...)` |
| 3 | [2_langchain/L4_Tagging_Extraction.py](2_langchain/L4_Tagging_Extraction.py) | `PydanticToolsParser` |
| 4 | [2_langchain/L5_Tools_Routing_APIs.py](2_langchain/L5_Tools_Routing_APIs.py) | `@tool`、手写路由 |
| 5 | [2_langchain/L6_Agents_Memory_Streaming.py](2_langchain/L6_Agents_Memory_Streaming.py) | Agent、Memory、状态流 |
| 6 | [2_langchain/L7_Agents_Structured_Output.py](2_langchain/L7_Agents_Structured_Output.py) | `ToolStrategy` |
| 7 | [2_langchain/L8_Deep_Agent_From_Scratch.py](2_langchain/L8_Deep_Agent_From_Scratch.py) | Middleware、Sandbox |
| 8 | [2_langchain/L9_Semantic_Search_Knowledge_Base.py](2_langchain/L9_Semantic_Search_Knowledge_Base.py) | Document、Embedding、Retriever |
| 9 | [2_langchain/L10_RAG_Agent.py](2_langchain/L10_RAG_Agent.py) | 固定 RAG、Agentic RAG |
| 10 | [2_langchain/L11_SQL_Agent.py](2_langchain/L11_SQL_Agent.py) | Tool 权限边界 |
| 11 | [2_langchain/L12_Voice_Agent.py](2_langchain/L12_Voice_Agent.py) | 异步流式管道 |
| 12 | [3_rag_from_scratch/part1_overview.py](3_rag_from_scratch/part1_overview.py) | 最小 RAG 全流程 |
| 13 | [3_rag_from_scratch/part2_indexing.py](3_rag_from_scratch/part2_indexing.py) | 切块、Embedding、入库 |
| 14 | [3_rag_from_scratch/part2_chunking_parameter_comparison.py](3_rag_from_scratch/part2_chunking_parameter_comparison.py) | token-aware 切块参数 |
| 15 | [3_rag_from_scratch/part2_offline_vs_glm_embeddings.py](3_rag_from_scratch/part2_offline_vs_glm_embeddings.py) | Embedding 实现对比 |
| 16 | [3_rag_from_scratch/part3_1_retrieval.py](3_rag_from_scratch/part3_1_retrieval.py) | `invoke/batch` |
| 17 | [3_rag_from_scratch/part3_2_retrieval_k_score_mmr_no_answer.py](3_rag_from_scratch/part3_2_retrieval_k_score_mmr_no_answer.py) | score、MMR、no-answer |
| 18 | [3_rag_from_scratch/part4_1_generation.py](3_rag_from_scratch/part4_1_generation.py) | 生成链与完整 RAG 链 |
| 19 | [3_rag_from_scratch/part4_2_answer_with_citations.py](3_rag_from_scratch/part4_2_answer_with_citations.py) | gate 与 citation |
| 20 | [3_rag_from_scratch/part5_multi_query.py](3_rag_from_scratch/part5_multi_query.py) | `RunnableLambda`、`.map()` |
| 21 | [3_rag_from_scratch/part15_reciprocal_rank_fusion_reranking.py](3_rag_from_scratch/part15_reciprocal_rank_fusion_reranking.py) | `batch()`、RRF |

## 18. 一页速记

```text
Runnable
  = invoke / batch / stream / async variants

prompt | model | parser
  = 左边输出传给右边
  = 构造时不执行，invoke 时执行

RunnableLambda(fn)
  = 普通 Python 函数 → Runnable

RunnablePassthrough()
  = 输入原样输出

RunnableMap({...}) / LCEL 字典
  = 同一个输入 → 多个命名分支 → dict

runnable.map()
  = list 中每一项执行同一个 Runnable

Document
  = page_content + metadata

Embeddings
  = embed_documents 用于入库
  = embed_query 用于查询

Retriever
  = question → list[Document]

固定 RAG
  = question → Retriever → Prompt → Model → answer

Tool Calling
  = 模型生成 tool_calls
  ≠ 模型自己执行 Python 函数

create_agent
  = 自动管理 Model → Tool → Model 循环

Agent result["messages"]
  = 完整执行轨迹

Multi Query
  = 一个问题 → 多个查询 → 多路检索 → 合并去重

RRF
  = 多个检索排名 → 基于名次融合
```
