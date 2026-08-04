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

#### 7.1.1 当前知识库 Loader 中 Markdown 与 PDF 的 Document 粒度

[`4_rag_knowledge_base_service/loaders.py`](4_rag_knowledge_base_service/loaders.py)
负责递归查找知识库目录中的 `.md`、`.markdown` 和 `.pdf` 文件，并将文件内容
转换为 LangChain `Document`。Markdown 和 PDF 在“加载阶段”的粒度不同。

Markdown 的核心代码：

```python
text = path.read_text(encoding="utf-8", errors="replace").strip()
if not text:
    return []

return [
    Document(
        page_content=text,
        metadata={
            "source": source,
            "source_type": "markdown",
            "title": _markdown_title(text, path.stem),
            "source_sha256": source_sha256,
        },
    )
]
```

一个 Markdown 文件没有按页遍历：

```text
1 个非空 Markdown 文件
    ↓
1 个 Document，page_content 是整个文件正文
```

空 Markdown 文件清理首尾空白后会返回 `[]`。

PDF 的核心代码：

```python
documents: list[Document] = []

for page_number, page in enumerate(reader.pages, start=1):
    text = (page.extract_text() or "").strip()
    if not text:
        continue
    documents.append(
        Document(
            page_content=text,
            metadata={
                "source": source,
                "source_type": "pdf",
                "page": page_number,
            },
        )
    )
```

PDF 会遍历页面：

```text
1 个 PDF 文件
    ↓
第 1 个有文本页面 → 1 个 Document
第 2 个有文本页面 → 1 个 Document
空白或提取不到文字的页面 → 跳过
...
```

因此一个 10 页 PDF，如果 9 页能够提取到非空文字，加载结果就是
`list[Document]`，长度为 `9`，不是整个 PDF 只生成一个 `Document`。纯扫描
图片页面如果没有可提取文本，也可能被这里跳过，因为当前 Loader 没有做 OCR。

加载结果还不是最终写入向量库的 chunk。每个来源文件先被包装为：

```python
LoadedSource(
    source=source,
    source_sha256=digest,
    documents=documents,
)
```

随后 `indexer.py` 再执行：

```python
raw_chunks = splitter.split_documents(loaded.documents)
```

完整层次是：

```text
文件夹
  ↓ loaders.py
每个 Markdown：0 或 1 个原始 Document
每个 PDF：0 到多个按页的原始 Document
  ↓ RecursiveCharacterTextSplitter
多个 chunk Document
  ↓ Embedding / VectorStore
向量索引
```

切块时会复制原始 metadata，所以从 PDF 页面切出的 chunk 仍然保留 `page`；
Markdown chunk 没有 `page`，但仍保留 `source`、`title` 和 `source_type`。

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

### 7.5 Chroma 持久化向量索引

`Chroma` 是向量数据库，也实现了 LangChain 的 `VectorStore` 接口。当前项目通过：

```python
from langchain_chroma import Chroma

store = Chroma(
    collection_name="andrew_rag_knowledge_base",
    embedding_function=embeddings,
    persist_directory="runtime/chroma",
    collection_metadata={"hnsw:space": "cosine"},
)
```

可以先把“Chroma 索引”理解为：

> 把每个文档 chunk 转换成向量，并保存 chunk ID、原文、metadata 和向量；
> 同时建立能够按向量距离快速寻找相似 chunk 的近邻检索结构。

它不是聊天模型，也不是 Embedding 模型。三者职责不同：

```text
Embedding 模型：文本 → 向量
Chroma 索引：保存向量及其对应资料，并按相似度查找
聊天模型：读取召回的资料并组织最终答案
```

#### 写入索引

当前 `4_rag_knowledge_base_service/indexer.py` 的写入过程是：

```text
Markdown / PDF
    ↓ Loader
Document
    ↓ RecursiveCharacterTextSplitter
Document chunk
    ↓ embed_documents
384 维文档向量
    ↓ Chroma.add_documents
ID + 原文 + metadata + 向量
```

#### 一个 chunk 就是一个 `Document` 吗

在当前 LangChain 代码的表示方式中：

> 每个切分后的 chunk 都用一个 `Document` 对象承载，但不是每个 `Document`
> 都一定已经是 chunk。

Loader 首先产生表示整篇 Markdown 或单个 PDF 页面的原始 `Document`，Splitter 再把
一个原始 `Document` 切成零到多个新的 chunk `Document`：

```text
一个原始 Document
├── chunk Document 0
├── chunk Document 1
└── chunk Document 2
```

类型变化看起来仍然是：

```python
loaded.documents
# list[Document]，这里装的是原始文档或 PDF 页面

raw_chunks = splitter.split_documents(loaded.documents)
# list[Document]，这里每个 Document 已经表示一个 chunk
```

`Document` 是承载数据的对象类型；`chunk` 描述的是这份 `Document` 内容在处理流程中
扮演的角色。切块后的 `Document.page_content` 保存当前片段，`metadata` 继续保存
`source`、`page` 等来源信息，并增加 `start_index`、`chunk_id` 等索引信息。

当前项目向 Chroma 写入时，一个 chunk `Document` 对应一个稳定 chunk ID 和一条向量
记录。

例如一个 chunk 在逻辑上可以理解为：

```python
{
    "id": "a5344d...",
    "document": "# 本机模型与运行开关 ...",
    "metadata": {
        "source": "local_runtime.md",
        "source_type": "markdown",
        "start_index": 0,
        "chunk_id": "a5344d...",
    },
    "embedding": [0.012, -0.034, ...],  # 当前本地模型是 384 维
}
```

`add_documents()` 接收的是 `Document` 和 ID。Chroma 会通过构造时传入的
`embedding_function` 隐式调用 `embed_documents()`，所以调用方不需要先手工把
每个向量传给 `add_documents()`。

#### 查询索引

```python
matches = store.similarity_search_with_score(question, k=top_k)
```

内部流程是：

```text
question: str
    ↓ 同一个 embedding_function.embed_query()
查询向量
    ↓ Chroma 余弦近邻搜索
最接近的 k 个文档向量
    ↓ 根据向量找到对应记录
list[tuple[Document, distance]]
```

“索引”的价值在于不需要拿查询向量与所有文档向量逐条做完整扫描。Chroma 会维护
面向近邻搜索的数据结构；本项目通过 `{"hnsw:space": "cosine"}` 指定使用余弦距离。

#### 为什么把 `distance` 转成 `relevance score`

当前 `langchain-chroma` 的 `similarity_search_with_score()` 返回：

```python
list[tuple[Document, distance]]
```

这里第二项是距离：

```text
distance 越小  -> 两个向量越接近
distance 越大  -> 两个向量越远
```

但业务层使用的 `vector_score`、门槛判断和加权分数采用相反方向：

```text
score 越大 -> 越相关
score 越小 -> 越不相关
```

本项目把 Chroma collection 配置为 cosine distance。余弦距离和余弦相似度的关系是：

```text
cosine_distance   = 1 - cosine_similarity
cosine_similarity = 1 - cosine_distance
```

因此搜索方法执行：

```python
matches = self._store().similarity_search_with_score(query, k=top_k)

return [
    (document, max(0.0, min(1.0, 1.0 - float(distance))))
    for document, distance in matches
]
```

例如：

| Chroma `distance` | `1 - distance` | 转换后的含义 |
| ---: | ---: | --- |
| `0.0` | `1.0` | 向量最接近 |
| `0.2` | `0.8` | 比较相关 |
| `0.8` | `0.2` | 相关性较低 |
| `1.3` | `-0.3` | 方向相反，最终钳制为 `0.0` |

最外层：

```python
max(0.0, min(1.0, score))
```

把结果限制在 `0.0..1.0`：

```text
score > 1.0 -> 1.0
0 <= score <= 1.0 -> 保持原值
score < 0.0 -> 0.0
```

所以这里的数据流是：

```text
Chroma distance（越小越相似）
    ↓ 1 - distance
cosine similarity（越大越相似）
    ↓ max/min
0..1 vector_score
```

这个 `vector_score` 表示向量接近程度，不是答案正确概率。服务层还会把它与
`lexical_overlap` 加权生成最终 `relevance_score`，再用于候选接受和拒答判断。

#### `collection`、Chroma 索引和 manifest 的区别

| 名称 | 当前项目中的含义 |
| --- | --- |
| collection | Chroma 内的逻辑数据集合，名称为 `andrew_rag_knowledge_base` |
| Chroma 索引 | 用于保存和搜索 chunk 原文、metadata、ID 与向量的数据及近邻结构 |
| `runtime/chroma` | Chroma 数据的本地持久化目录，进程退出后仍然存在 |
| `index_manifest.json` | 项目自己维护的增量同步账本，记录来源 hash 和 chunk IDs，不保存向量 |
| `index_fingerprint` | chunk 参数、embedding 身份和 collection 名称的配置指纹 |

这里的 `index_fingerprint` 不是“当前全部索引数据的内容指纹”。它更准确的含义是：

> 这批 Chroma 向量是按照哪一套索引构建配置生成的。

它由 `@property` 即时计算，没有在 `__init__()` 中单独赋值：

```python
@property
def index_fingerprint(self) -> str:
    payload = {
        "chunk_size": self.settings.chunk_size,
        "chunk_overlap": self.settings.chunk_overlap,
        "embedding": embedding_identity(self.settings),
        "collection": self.settings.collection_name,
    }
    return _sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False)
    )[:20]
```

manifest 使用两层信息分别描述“构建方式”和“数据内容”：

```text
index_manifest.json
├── index_fingerprint     索引构建配置是否兼容
└── sources
    ├── A.md
    │   ├── sha256        A.md 内容是否变化
    │   └── chunk_ids     A.md 当前对应哪些 Chroma 记录
    └── B.md
        ├── sha256
        └── chunk_ids
```

可以把两者理解成“控制账本”和“实际数据仓库”：

```text
index_manifest.json（项目控制账本）
    source_sha256 + chunk_ids
                    │
                    │ chunk_id 一一对应
                    ▼
Chroma（实际向量数据仓库）
    id + 原文 + metadata + embedding
```

| 内容 | `index_manifest.json` | Chroma |
| --- | --- | --- |
| 来源文件 SHA-256 | 保存，用于判断文件变化 | metadata 中也可能保留，但不负责增量比较 |
| chunk IDs | 按来源文件分组保存 | 作为每条向量记录的 ID |
| chunk 原文 | 不保存 | 保存 |
| chunk metadata | 不完整保存 | 保存完整 metadata |
| 384 维向量 | 不保存 | 保存 |
| 近邻搜索结构 | 不保存 | 保存 |

Chroma 本身不知道项目的 `index_manifest.json`。manifest 也不会自动读取或修改 Chroma；
两者由 `IncrementalIndexer.reindex()` 协调：

```text
读取旧 manifest
    ↓ 比较当前来源 SHA-256
找出新增、修改、删除的来源
    ↓
根据旧 manifest 的 chunk_ids 删除 Chroma 旧记录
    ↓
用相同的稳定 chunk_ids 向 Chroma 写入新 Documents
    ↓
最后写入新的 manifest
```

查询时职责不同：

```text
manifest → 检查是否已有来源、构建配置是否兼容
Chroma   → 真正执行向量搜索并返回 Document 和距离
```

因此这两个目录或文件应该作为一组持久化状态维护。手工只删除或修改其中一边，可能造成
manifest 记录的 chunk 与 Chroma 实际记录不一致。

#### `sources` 与 `manifest_matches_config()`

manifest 中的 `sources` 不是 Settings 配置参数，而是“已经纳入索引的来源文件状态表”：

```python
"sources": {
    "rag_basics.md": {
        "sha256": "64e334...",
        "chunk_count": 1,
        "chunk_ids": ["00e78a..."],
    }
}
```

其类型是：

```python
dict[str, dict[str, Any]]
```

key 是来源相对路径，value 保存该来源的内容 hash、chunk 数量和 Chroma IDs。

配置兼容方法：

```python
def manifest_matches_config(
    self,
    manifest: dict[str, Any] | None = None,
) -> bool:
    active_manifest = (
        manifest
        if manifest is not None
        else self.read_manifest()
    )
    sources = active_manifest.get("sources", {})
    return (
        not sources
        or active_manifest.get("index_fingerprint")
        == self.index_fingerprint
    )
```

第一行有两条来源分支：

```text
显式传入 manifest 字典 → 直接检查传入字典
manifest 参数为 None   → read_manifest() 读取本地文件
```

最后一行使用 `or` 短路，准确逻辑是：

| `sources` | manifest 指纹 | 返回值 |
| --- | --- | --- |
| 缺失或 `{}` | 任意值，包括缺失或错误 | `True` |
| 非空 | 等于当前 `self.index_fingerprint` | `True` |
| 非空 | 缺失或不等于当前指纹 | `False` |

这个表描述的是方法拿到 `active_manifest` 之后的表达式结果。如果
`manifest=None`、需要读取本地文件，`read_manifest()` 会先验证 `sources` 必须存在且
为字典；本地 JSON 缺少 `sources` 时会直接抛出 `IndexingError`。只有调用方显式传入
一个未经 `read_manifest()` 校验的字典时，缺失 `sources` 才会被 `.get(..., {})`
当成空字典。

因此并不是“没有 sources 时再比较指纹”，而是恰好相反：

```text
没有已索引来源 → 没有旧向量会发生配置冲突 → 直接兼容
已有索引来源   → 必须确认旧向量与当前构建配置兼容
```

这里返回 `True` 只表示“配置没有冲突”，不表示“索引已准备好”。健康检查还会额外判断：

```python
index_ready = bool(sources) and index_config_matches
```

所以空 `sources` 时：

```text
manifest_matches_config() == True
index_ready               == False
```

`ensure_compatible_manifest()` 只是把上面的布尔结果转换成“正常继续或抛异常”：

```python
def ensure_compatible_manifest(self) -> None:
    if not self.manifest_matches_config():
        raise IndexConflictError(
            "当前持久化索引由另一组 chunk/embedding 配置生成；"
            "请先执行 reindex --reset。"
        )
```

正常情况没有显式 `return`，因此返回：

```python
None
```

三种主要结果是：

| manifest 状态 | 结果 |
| --- | --- |
| `sources` 为空 | 没有旧向量冲突，正常返回 `None` |
| `sources` 非空且指纹相同 | 同一套构建配置，正常返回 `None` |
| `sources` 非空且指纹不同 | 抛出 `IndexConflictError` |

这里的“当前配置”不是写死在 Python 文件里的固定值，而是本次进程从 Settings 得到的值。
以下变化都可能让当前指纹与上一次写入 manifest 的指纹不同：

- `.env` 或系统环境变量中的 chunk 参数发生变化。
- CLI 改用另一种 Embedding 模式。
- 本地 Embedding 模型身份或加载变体发生变化。
- Chroma collection 名称发生变化。
- 从其他环境复制了由不同配置生成的 manifest。
- 手工修改了 manifest 中的 fingerprint。

它只检查索引构建配置兼容性，不检查：

- Markdown/PDF 内容有没有变化；这由每个来源的 SHA-256 比较负责。
- manifest 中的 chunk IDs 是否真的全部存在于 Chroma。
- Chroma 是否被手工删除或损坏。
- 空 `sources` 是否已经可以查询；健康检查另用 `index_ready` 判断。

另外，`manifest=None` 时会先调用 `read_manifest()`。如果本地 JSON 无法读取、
`format_version` 不兼容或 `sources` 格式错误，可能先抛出 `IndexingError`，而不是
走到 fingerprint 不一致的 `IndexConflictError`。

不同变化对应的记录位置：

| 变化 | `index_fingerprint` | `sources` |
| --- | --- | --- |
| 修改、新增或删除来源文件 | 通常不变 | 来源 SHA-256 和 chunk IDs 变化 |
| 修改 `chunk_size` / `chunk_overlap` | 变化 | 要求完整重建 |
| 更换 Embedding 实现或模型身份 | 变化 | 要求完整重建 |
| 更换 Chroma collection | 变化 | 要求完整重建 |
| 修改 `top_k`、拒答门槛或聊天模型 | 不变 | 不影响已存向量，无需重建 |

因此当前增量同步不需要“每次数据改变就生成一个全局数据指纹”：它会逐个比较
`sources[name]["sha256"]`，从而准确知道哪些文件要新增、更新、跳过或删除。

如果未来需要表示整个知识库的单一版本号，例如用于 ETag、跨节点缓存或审计，可以额外
增加 `data_fingerprint`，对排序后的 `{source: sha256}` 再做一次哈希；若还要同时覆盖
构建配置，则可以生成包含 `index_fingerprint + data_fingerprint` 的
`snapshot_fingerprint`。当前代码没有这两个字段。

不能使用一种 Embedding 建库，再随意换另一种 Embedding 查询。不同模型生成的向量
坐标含义可能不同，维度也可能不同。因此当前项目在 chunk 参数、Embedding 或
collection 发生变化时，会要求执行 `reindex --reset` 重建索引。

#### `IncrementalIndexer`：增量索引的执行与协调对象

`IncrementalIndexer` 是当前项目自己定义的普通业务类，不是 dataclass，也不是
LangChain 或 Chroma 自带的类：

```python
class IncrementalIndexer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._embeddings = build_embeddings(settings)
```

这里的 `settings: Settings` 表示调用方应该传入已经创建好的 `Settings` 配置实例。
`IncrementalIndexer.__init__()` 不负责读取 `.env`；真正的配置解析发生在服务创建之前：

```python
settings = Settings.from_env()
service = KnowledgeBaseService(settings)
# KnowledgeBaseService 内部继续执行 IncrementalIndexer(settings)
```

同一个配置对象会被保存并向下传递：

```text
settings
  ├── service.settings
  └── service.indexer.settings
```

`IncrementalIndexer` 会使用其中不同字段完成不同工作：

| Settings 字段 | 使用位置 |
| --- | --- |
| `embedding_mode` 及模型字段 | `build_embeddings(settings)` 选择 Embedding 实现 |
| `chunk_size`、`chunk_overlap` | `_chunk_source()` 创建文本切分器 |
| `runtime_dir` / `chroma_dir` | 读取 manifest、连接本地 Chroma |
| `collection_name` | 选择 Chroma collection，并参与索引指纹 |

它与前面两个数据对象的关系是：

| 对象 | 职责 |
| --- | --- |
| `ChunkedSource` | 保存一个来源文件完成切块后的 Documents 和 chunk IDs |
| `IndexStats` | 保存一次 `reindex()` 完成后的统计结果 |
| `IncrementalIndexer` | 真正执行切块、差异比较、Chroma 增删、manifest 更新和搜索 |

主数据流是：

```text
Settings
   ↓
IncrementalIndexer
   ├── reindex()
   │     LoadedSource
   │         ↓ 切块和生成稳定 ID
   │     ChunkedSource
   │         ↓
   │     Chroma + index_manifest.json
   │         ↓
   │     IndexStats
   │
   └── search()
         question
             ↓ Chroma 相似度搜索
         list[tuple[Document, relevance_score]]
```

##### `_store()` 创建或连接 Chroma VectorStore

当前方法：

```python
def _store(self):
    from langchain_chroma import Chroma

    self.settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=self.settings.collection_name,
        embedding_function=self._embeddings,
        persist_directory=str(self.settings.chroma_dir),
        collection_metadata={"hnsw:space": "cosine"},
    )
```

执行顺序是：

1. 在函数内部导入 LangChain 的 Chroma VectorStore 包装类。
2. 确保本地 Chroma 持久化目录存在；已有目录不会被清空。
3. 使用该目录创建 `PersistentClient`。
4. 按 `collection_name` 获取已有 collection；不存在时自动创建。
5. 把当前 Embeddings 对象保存在 Chroma 包装器中。
6. 返回一个 `langchain_chroma.vectorstores.Chroma` 对象。

参数含义：

| 参数 | 当前项目中的作用 |
| --- | --- |
| `collection_name` | 选择逻辑 collection，默认是 `andrew_rag_knowledge_base` |
| `embedding_function` | 绑定当前 Embeddings 实例，供写入和查询时转换向量 |
| `persist_directory` | 使用本地持久化客户端，数据保存到 `runtime/chroma` |
| `collection_metadata` | 设置向量近邻索引使用 cosine 距离 |

构造 Chroma 对象时不会立刻把所有来源文件重新向量化。真正写入时：

```python
store.add_documents(documents=documents, ids=ids)
```

LangChain Chroma 包装器才会调用：

```python
self._embeddings.embed_documents(texts)
```

真正查询时：

```python
store.similarity_search_with_score(query, k=top_k)
```

包装器才会调用：

```python
self._embeddings.embed_query(query)
```

当前安装版本在构造过程中使用 `get_or_create_collection()`，所以 `_store()` 同时适用于
第一次创建和后续重新连接。重复调用 `_store()` 会返回不同的 Python 包装对象，但它们
连接的是同一持久化目录和同名 collection，不会因此创建多份向量数据。

当前本地实测返回对象和连接状态为：

```text
返回类型：langchain_chroma.vectorstores.Chroma
collection：andrew_rag_knowledge_base
Embedding：LocalMiniLMEmbeddings
当前记录数：5
距离规则：cosine
```

##### `reindex()` 中“当前快照、旧账本、Chroma 和返回统计”的关系

当前方法开头：

```python
loaded_sources = load_sources(self.settings.source_dir)
chunked_sources = {
    source.source: self._chunk_source(source) for source in loaded_sources
}
old_manifest = self.read_manifest()
old_sources: dict[str, dict[str, Any]] = old_manifest["sources"]
```

这些变量可以分成两组：

| 变量 | 数据来源 | 表示什么 |
| --- | --- | --- |
| `loaded_sources` | 当前 `source_dir` 磁盘文件 | 本次扫描并读取到的 `list[LoadedSource]` |
| `chunked_sources` | 本次 `_chunk_source()` 结果 | 当前期望索引状态，类型为 `dict[str, ChunkedSource]` |
| `old_manifest` | 上次成功写下的 `index_manifest.json` | 旧索引控制账本 |
| `old_sources` | `old_manifest["sources"]` | 上次记录的来源 hash、chunk 数量和 chunk IDs |

因此“当前”和“旧”的主线理解是正确的，但要注意两点：

1. `chunked_sources` 此时只是内存中的 chunk Documents 和稳定 IDs，还没有生成
   Embedding，也没有写入 Chroma；
2. `old_sources` 来自 manifest 账本，并不是重新查询 Chroma 得到的实际旧记录。

字典推导式：

```python
chunked_sources = {
    source.source: self._chunk_source(source)
    for source in loaded_sources
}
```

可以展开为：

```python
chunked_sources = {}
for source in loaded_sources:
    chunked_sources[source.source] = self._chunk_source(source)
```

它形成的结构类似：

```text
{
    "A.md": ChunkedSource(A 的 hash、Documents、chunk IDs),
    "B.pdf": ChunkedSource(B 的 hash、Documents、chunk IDs),
}
```

完成当前文件的加载和切块以后，方法才计算差异：

```text
current_names  = 当前 chunked_sources 的来源名称
previous_names = 旧 manifest 的来源名称

changed_names
    = 当前新增的来源
    + source_sha256 与旧 manifest 不同的来源

removed_names
    = 旧 manifest 中有、当前目录中已经没有的来源

unchanged
    = 当前存在且 source_sha256 与旧记录相同的来源
```

随后才处理 Chroma：

```text
changed + removed 的旧 chunk IDs
    ↓
_delete_ids()
    ↓
从 Chroma 删除旧记录

changed 对应的当前 ChunkedSource
    ↓
_add_source_chunks()
    ↓ Chroma 调用 Embedding
生成向量并写入新的 Document、metadata、ID 和 embedding
```

没有变化的来源不会重新 Embedding，也不会重新写入 Chroma。

Chroma 更新完成后，代码根据全部当前 `chunked_sources` 创建完整的新 manifest，而不是
只把变化部分写进去：

```python
new_manifest["sources"] = {
    name: self._manifest_source_entry(source)
    for name, source in sorted(chunked_sources.items())
}
self._write_manifest(new_manifest)
```

只有执行到最后，方法才返回一次性的统计报告：

```python
return IndexStats(...)
```

`IndexStats` 表示“本次 `reindex()` 做了什么以及新 manifest 期望的总 chunk 数”，不
保存 Document 或向量，也不是以后继续用于新旧比较的账本；以后比较仍然读取
`index_manifest.json`。

还有两个统计口径细节：

- `total_indexed_chunks` 是汇总新 manifest 中的 `chunk_count`，不是重新调用 Chroma
  查询实际记录数；
- `_delete_ids()` 返回提交删除的 ID 数量，因此 `deleted_chunks` 表示本次按账本处理
  的旧 ID 数量，不是额外进行一次 Chroma 全量审计后的结果。

完整成功路径是：

```text
当前文件
  ↓ load_sources()
LoadedSource
  ↓ _chunk_source()
当前 chunked_sources
  ↕ 与旧 manifest.sources 对比
changed / removed / unchanged
  ↓
删除 Chroma 旧 chunk
  ↓
写入 Chroma 新 chunk 和向量
  ↓
原子写入完整新 manifest
  ↓
返回 IndexStats
```

如果中途抛出异常，方法不会返回 `IndexStats`。

##### 为什么叫 Incremental

`Incremental` 表示“增量的”。普通情况下，它不会每次都重新向量化全部文件，而是
使用当前来源文件与旧 manifest 做比较：

```text
新文件                 → 生成 chunk 并写入 Chroma
内容 hash 改变的文件   → 删除旧 chunk，再写入新 chunk
没有变化的文件         → 跳过，不重新计算向量
已经删除的来源文件     → 根据旧 chunk IDs 从 Chroma 删除
```

例如旧 manifest 和当前来源分别是：

```text
旧 manifest              当前来源
A.md：hash-old           A.md：hash-new
B.md：hash-b             B.md：hash-b
C.md：hash-c             D.md：hash-d
```

比较后得到：

```text
changed_names = ["A.md", "D.md"]  # A 修改，D 新增
removed_names = ["C.md"]          # C 已删除
B.md                              # 未变化，跳过
```

然后执行：

```text
删除 A.md 和 C.md 的旧 chunk IDs
写入 A.md 和 D.md 的新 chunk Documents
重写最新 manifest
返回本次 IndexStats
```

##### 主要方法分工

| 方法 | 作用 |
| --- | --- |
| `index_fingerprint` | 根据切块参数、Embedding 身份和 collection 生成配置指纹 |
| `_store()` | 创建或打开持久化 Chroma collection |
| `read_manifest()` | 读取并验证 `index_manifest.json` |
| `manifest_matches_config()` | 判断持久化索引配置是否与当前配置一致 |
| `_chunk_source()` | 把一个 `LoadedSource` 转成 `ChunkedSource` |
| `_delete_ids()` | 分批删除 Chroma 中的旧 chunk IDs |
| `_add_source_chunks()` | 分批把 chunk Documents 和 IDs 写入 Chroma |
| `reindex()` | 协调整个增量同步流程并返回 `IndexStats` |
| `search()` | 使用 Chroma 查询候选 Documents 并转换距离分数 |

当 `reset=True` 时，它会删除旧 manifest 记录的全部 chunk，并把当前所有来源重新切块、
向量化和写入。这是完整重建，不再是只处理变化文件。

`IncrementalIndexer` 对象由 `KnowledgeBaseService` 创建和持有：

```python
self.indexer = IncrementalIndexer(settings)
```

API 和 CLI 不直接操作 Chroma，而是通过服务层调用：

```python
self.indexer.reindex(reset=reset)
self.indexer.search(question, top_k=top_k)
```

### 7.6 搜索与 Retriever

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

#### 当前知识库服务的两个相关度门槛

当前服务需要区分三个分数：

| 名称 | 来源 | 含义 |
| --- | --- | --- |
| `vector_score` | Chroma 向量搜索 | 查询向量与文档向量的接近程度 |
| `lexical_overlap` | 项目自己的词项集合计算 | 问题有效词项被文档覆盖的比例 |
| `relevance_score` | 项目加权计算 | 25% `vector_score` + 75% `lexical_overlap` |

代码：

```python
lexical_overlap = len(
    query_tokens.intersection(document_tokens)
) / max(1, len(query_tokens))

relevance_score = (
    0.25 * vector_score
    + 0.75 * lexical_overlap
)
```

`lexical_overlap` 的分母只是问题词项数量，因此它读作：

> 问题中的有效词项，有多大比例也出现在当前候选文档中。

它不是 Jaccard 相似度，因为没有除以双方词项的并集数量。

例如：

```python
question = "知识库使用什么向量数据库？"
document = "当前知识库使用 Chroma 向量数据库。"
```

经过 `grounding_tokens()` 并排除高频停用词后：

```python
query_tokens
# 7 个词项

query_tokens.intersection(document_tokens)
# {"使用", "向量", "库使", "据库", "量数"}，共 5 个

lexical_overlap
# 5 / 7 ≈ 0.7143
```

两个配置分别限制：

```python
relevance_score >= min_relevance_score
lexical_overlap >= min_lexical_overlap
```

默认值是：

```text
min_relevance_score = 0.10
min_lexical_overlap = 0.12
```

之所以保留第二个独立门槛，是为了给词面证据设置硬下限。例如：

```text
vector_score    = 0.80
lexical_overlap = 0.05
relevance_score = 0.25 × 0.80 + 0.75 × 0.05
                = 0.2375
```

此时：

```text
0.2375 >= 0.10  → 综合分数通过
0.05   >= 0.12  → 词面证据不通过
```

所以候选文档仍然被拒绝。这能拦住“向量语义看起来相近，但文档没有覆盖问题中关键
词项”的伪相关结果。

因此配置名可以准确理解为：

```text
min_relevance_score  = 最低综合分数门槛
min_lexical_overlap  = 最低问题词项覆盖率门槛
```

#### 完整的 relevance gate

`relevance gate` 可以读作“相关性准入门”。Chroma Top-K 只负责从向量库中找出
相对更接近的候选，即使问题完全不属于知识库，也仍可能返回排在前面的文档。
relevance gate 在 Top-K 之后决定哪些候选有资格进入回答流程。

目录 5 的 `LocalKnowledgeRetriever.retrieve()` 复用目录 4 的规则，每条候选必须同时
满足四个条件：

```python
is_accepted = (
    relevance_score >= min_relevance_score
    and lexical_overlap >= min_lexical_overlap
    and relevance_score >= best_relevance * 0.85
    and (not query_technical_tokens or technical_match)
)
```

当前默认阈值：

```text
min_relevance_score = 0.10
min_lexical_overlap = 0.12
```

四道条件分别表示：

1. 综合相关度至少达到绝对下限 `0.10`。
2. 问题词项覆盖率至少达到绝对下限 `0.12`。
3. 当前候选至少达到本次最佳候选分数的 `85%`，过滤明显落后的候选。
4. 问题包含 ASCII 技术标识时，候选正文也必须命中至少一个技术标识；纯中文问题的
   `query_technical_tokens` 为空集合，这一项自动通过。

数据分层：

```text
Chroma Top-K
  ↓ 全部候选计算三种分数
matches：保留全部候选和 accepted=True/False，供审计
  ↓ relevance gate
accepted：只保留四项条件全部通过的 Evidence
```

例如本地 Hash 模式下，已知问题的最佳候选为：

```text
vector_score    = 0.253427
lexical_overlap = 0.555556
relevance_score = 0.25 × 0.253427 + 0.75 × 0.555556
                ≈ 0.480023
best × 0.85     ≈ 0.408020
technical_match = True
```

四项全部通过，所以进入 `accepted`。同一次检索中另一候选即使
`relevance_score=0.363357` 高于绝对下限，也因为：

```text
0.363357 < 0.408020
```

没有达到最佳候选的 `85%`，因此不会进入 `accepted`。

未知问题 `QUASAR_TIDE_9999 是什么？` 的本地实测最佳候选为：

```text
vector_score    = 0.074536
lexical_overlap = 0
relevance_score = 0.018634
technical_match = False
```

它无法通过绝对综合分数、词面覆盖和技术词匹配条件，因此：

```python
accepted == []
```

需要区分 relevance gate 和 Part 2 后面的 evidence grader：

```text
relevance gate
  = 本地确定性 Python 规则，先过滤每个 Chroma 候选

evidence grader
  = accepted 证据形成 used_evidence 后，判断整组证据是否足够回答原问题
```

流程是：

```text
Chroma Top-K
→ relevance gate
→ accepted
→ used_evidence
→ 可选模型 grader
→ generate / rewrite / refuse
```

通过 relevance gate 只表示“这条 chunk 有资格继续参与回答”，不表示最终答案一定
正确，也不表示模型已经实际使用了它。

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

目录 4 的 `KnowledgeBaseService.ask()` 把这套关系进一步拆成了几个明确的中间值：

```text
retrieved
  = Chroma 返回的 Top-K (Document, vector_score)
  ↓ 为每条结果计算 lexical_overlap、relevance_score、technical_match
candidates
  = 计算完成但尚未过滤的全部 Top-K 候选
  ├─ matches
  │    = 全部候选的检索审计记录，通过与否保存在 accepted 字段
  └─ accepted_pairs
       = 只保留通过全部 gate 的候选，并按 relevance_score 降序排列
       ├─ citations = accepted_pairs[:3] 转换得到
       ├─ offline answer = 前两条 citation.quote
       └─ live context = 按顺序加入 accepted_pairs，受最大字符数限制
```

因此每条 `Citation` 一定来自 `accepted_pairs`，但两者数量不保证相同：
`citations` 最多取前三条。`Citation.quote` 是从对应 `Document.page_content`
中截取的相关窗口，不是完整正文；`matches.content_preview` 则是候选正文的
开头预览，两者用途不同。

这里与目录 3 的严格 citation 契约存在差异。目录 3 使用同一份
`accepted Documents` 同时构建 context 和 citations：

```text
context document IDs == citation document IDs == accepted document IDs
```

目录 4 当前则分别处理：

```text
citation document IDs = accepted_pairs 的前三条
live context IDs       = accepted_pairs 中受 max_context_chars 限制的前缀
offline answer IDs     = citation 的前两条
```

所以它只能保证这些数据都来源于 `accepted_pairs`，不能保证三组 ID 严格相等。
当 accepted 候选超过三条或 context 被字符上限截断时，模型可能看到没有 citation
的文档；反过来，某条 citation 对应的正文也可能没有完整进入 live context。
若要求严格一致，应先确定实际使用的 `used_pairs`，再从同一份 `used_pairs`
同时构建 context、answer 和 citations。

实际生产系统不一定要求“所有 context 文档都必须各返回一条 citation”。更常见的
契约是：

```text
citation document IDs ⊆ 实际进入模型的 context document IDs
答案中的被引用片段 → 明确关联到其中一个或多个 citation document IDs
```

context 可以包含模型最终没有采用的候选，因此 citation 可以是 context 的子集；
但 citation 不能指向没有进入实际上下文的来源，答案若使用某份上下文证据也不应
缺少相应引用。目录 3 使用集合完全相等，是在没有“答案片段 → chunk ID”结构化
输出和引用校验时最简单、安全的教学实现。目录 4 当前仍由
`StrOutputParser()` 只返回普通字符串，无法确认模型实际使用了哪些 chunk，因此
现阶段继续采用同一份 `used_pairs` 构建 context 和 citations 更可靠；以后若改成
结构化引用输出并校验 chunk ID，citations 才适合成为 context 的受验证子集。

#### 为什么推荐模型返回 `cited_chunk_ids`

给模型的每段最终上下文应带有稳定 ID：

```text
[chunk_id=chunk-a source=rag.md]
第一段证据……

[chunk_id=chunk-b source=runtime.md]
第二段证据……
```

模型只返回答案文本时：

```python
answer: str
```

程序只能知道哪些 chunk 进入过 Prompt，不能知道模型实际采用了哪些 chunk。推荐让
模型返回受约束的结构：

```python
class GroundedAnswer(BaseModel):
    answer: str
    cited_chunk_ids: list[str]
```

例如：

```python
GroundedAnswer(
    answer="Chroma 数据保存在 runtime/chroma。",
    cited_chunk_ids=["chunk-b"],
)
```

程序必须把模型返回的 ID 当作待校验数据，而不是直接信任：

```python
context_by_id = {
    evidence.chunk_id: evidence
    for evidence in used_evidence
}

unknown_ids = set(result.cited_chunk_ids).difference(context_by_id)
if unknown_ids:
    raise ValueError("模型返回了不在本次 context 中的 chunk_id")

citations = [
    build_citation(context_by_id[chunk_id])
    for chunk_id in result.cited_chunk_ids
]
```

这样设计有三个原因：

1. 模型只负责声明“答案使用了哪些证据 ID”，不能自由编造 `source`、`quote` 和分数。
2. 程序能验证 `cited_chunk_ids` 是实际 context IDs 的子集，阻止引用越界。
3. Citation 仍由本地可信的 `Document.metadata` 和实际进入 Prompt 的文本构建。

`answer + cited_chunk_ids` 提供的是答案级来源映射。如果还需要精确到每句话，应让
模型返回 `claims`，每个 claim 分别包含正文和 `cited_chunk_ids`，或返回答案文本
区间与 chunk ID 的映射，再逐项校验引用内容是否真的支持该 claim。

#### `evaluate.py`：黄金集评测与增量索引回归

目录 4 的 `evaluate.py` 是直接调用真实 `KnowledgeBaseService`、Chroma 和文件系统
的集成回归脚本，不是只测试单个函数的单元测试：

```text
读取 golden_cases.json
  ↓
创建 TemporaryDirectory
  ↓
复制 data/source 到临时 source
  ↓
根据 --mode 选择 offline/live，创建独立临时 runtime
  ↓
完整 reindex
  ↓
逐条 service.ask() 检查 20 条黄金样本
  ↓
修改临时 service_operations.md → reindex → 验证新内容可检索
  ↓
删除该临时文件 → reindex → 验证 manifest 已清理
  ↓
离开 with，自动删除整个临时目录
  ↓
写 evaluation.json；成功退出 0，失败退出 1
```

默认参数是 `--embedding local --mode live`：本机 MiniLM 负责建库和查询向量，
通过 answerability gate 的问题会调用在线聊天模型生成答案；无答案问题仍在生成前
拒答。CI 显式使用 `--embedding hash --mode offline`，保持确定性且不需要 API Key。

每条黄金样本可以检查：

- `answerable` 是否符合预期；
- citations 是否包含全部 `expected_sources`；
- 拒答时 citations 是否为空；
- citations 是否命中 `forbidden_sources`；
- 离线摘录答案是否包含全部 `expected_terms`。

其中 `expected_sources.issubset(citations)` 只要求正确来源出现在 citations 中，允许
额外来源。若要严格拦截错误引用，需要在黄金样本中填写 `forbidden_sources`，或者
改为校验 citation 集合完全相等；当前 20 条样本尚未使用 `forbidden_sources`。
live 模式会真实触发模型生成。由于正确回答可能把 `manifest` 改写成“清单”或把
`request_id` 改写成“请求 ID”，不能继续把“答案逐字包含术语”当作硬条件。当前规则
是：指定术语必须存在于实际 citation 证据中，answer 必须非空；answer 没有逐字复述
术语时只记录 warning。offline 模式仍对确定性摘录执行逐字硬断言。这仍不等于完成
生成答案的语义正确性或忠实性评测。脚本也不验证答案句子到 citation 的映射、HTTP
路由或并发锁；API 端到端行为由 `scripts/smoke.py` 负责另一层验证。

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

### 11.3 `model.with_structured_output()`

目录 5 的证据评分器：

```python
class GradeDocuments(BaseModel):
    binary_score: Literal["yes", "no"] = Field(
        description="检索证据相关且足以回答时为 yes，否则为 no。"
    )


grader = model.with_structured_output(
    GradeDocuments,
    method="function_calling",
)
```

执行 `with_structured_output()` 时只创建一个新的 Runnable，不会立即请求模型。
当前本地 `ChatOpenAI` 实现会把 Pydantic Schema 转换成 OpenAI Tool Schema：

```json
{
  "type": "function",
  "function": {
    "name": "GradeDocuments",
    "parameters": {
      "properties": {
        "binary_score": {
          "type": "string",
          "enum": ["yes", "no"]
        }
      },
      "required": ["binary_score"],
      "type": "object"
    }
  }
}
```

内部逻辑可以近似理解为：

```python
model_with_schema = model.bind_tools(
    [GradeDocuments],
    tool_choice="GradeDocuments",
    parallel_tool_calls=False,
)

parser = PydanticToolsParser(
    tools=[GradeDocuments],
    first_tool_only=True,
)

grader = model_with_schema | parser
```

这里的 `function_calling` 是模型输出协议，不表示执行了一个名为
`GradeDocuments` 的真实 Python 业务函数。它只要求模型把结果放进 Schema Tool Call
的参数中。

真正调用发生在：

```python
grade = grader.invoke(messages)
```

数据流：

```text
list[SystemMessage | HumanMessage]
  ↓ model_with_schema
AIMessage(
    content="",
    tool_calls=[
        {
            "name": "GradeDocuments",
            "args": {"binary_score": "yes"},
        }
    ],
)
  ↓ PydanticToolsParser
GradeDocuments(binary_score="yes")
```

因此：

```python
type(grade) is GradeDocuments
grade.binary_score  # "yes" 或 "no"
```

当前代码没有传 `include_raw=True`，所以调用方直接得到解析后的 Pydantic 对象，
看不到包装前的 `AIMessage`。如果模型给出不符合 `Literal["yes", "no"]` 的值，
Pydantic 解析会失败，而不是把任意文本当成有效分支结果。

`include_raw=True` 要在创建结构化输出 Runnable 时传入，而不是传给 `invoke()`：

```python
grader = model.with_structured_output(
    GradeDocuments,
    method="function_calling",
    include_raw=True,
)

result = grader.invoke(messages)
```

此时 `result` 不再直接是 `GradeDocuments`，而是一个字典：

```python
result = {
    "raw": AIMessage(...),
    "parsed": GradeDocuments(binary_score="yes"),
    "parsing_error": None,
}

raw_message = result["raw"]
grade = result["parsed"]
error = result["parsing_error"]
```

- `raw`：模型未经 Pydantic 解析的原始 `AIMessage`，可以查看 `tool_calls`。
- `parsed`：解析成功时为 `GradeDocuments`；解析失败时为 `None`。
- `parsing_error`：解析成功时为 `None`；解析失败时保存异常对象。

因此原来直接访问字段的代码：

```python
grade.binary_score
```

开启 `include_raw=True` 后需要改为：

```python
result["parsed"].binary_score
```

更稳妥的业务写法是先判断解析是否成功：

```python
result = grader.invoke(messages)
if result["parsing_error"] is not None:
    raise result["parsing_error"]

grade = result["parsed"]
assert grade is not None
binary_score = grade.binary_score
```

需要与真正 Tool 执行区分：

```text
with_structured_output(GradeDocuments)
  → 借用 Tool Call 格式承载结构化数据
  → PydanticToolsParser 解析
  → 不经过 ToolNode，不执行 Python Tool

ToolNode([retrieval_tool])
  → 读取 AIMessage.tool_calls
  → 真正执行 retrieve_context
  → 返回 ToolMessage
```

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

#### `ChatModel.invoke()` 为什么接收消息列表

目录 5 的路由模型调用：

```python
messages = list(state["messages"])
response = model_with_tools.invoke(
    [SystemMessage(content=ROUTER_SYSTEM_PROMPT), *messages]
)
```

本地 `BaseChatModel.invoke()` 的 `input` 可以接收三类数据：

```text
str
PromptValue
Sequence[BaseMessage]
```

这里使用 `list[BaseMessage]`，是因为 ChatModel 需要同时知道每条消息的角色和顺序。
第一次调用时可以近似理解为：

```python
messages = [
    HumanMessage(content="本地知识库默认使用什么 Embedding 模型？")
]

model_input = [
    SystemMessage(content=ROUTER_SYSTEM_PROMPT),
    HumanMessage(content="本地知识库默认使用什么 Embedding 模型？"),
]
```

- `SystemMessage`：只为本次路由模型调用提供规则。
- `messages`：LangGraph State 中已经积累的 Human、AI 和 Tool 消息历史。
- `*messages`：Python 列表解包，把历史消息逐项放到 SystemMessage 后面。

如果写成下面这样：

```python
[SystemMessage(content=ROUTER_SYSTEM_PROMPT), messages]
```

第二项会是完整的子列表，而不是一条 `BaseMessage`，不符合这里需要的平铺消息序列。

`model_with_tools` 虽然通过 `bind_tools()` 绑定了工具，但输入协议仍然是 ChatModel 的
消息输入协议；它返回一个 `AIMessage`，其中可能包含 `tool_calls`。

对于“本地知识库默认使用什么 Embedding 模型？”这个知识问题，模型决定调用检索
Tool 时，`response` 可以近似为下面的对象。`id`、token 用量和 provider metadata
每次请求都可能不同：

```python
response = AIMessage(
    content="",
    id="run-demo-001",
    tool_calls=[
        {
            "name": "retrieve_context",
            "args": {
                "query": "本地知识库默认使用什么 Embedding 模型？",
            },
            "id": "call-demo-001",
            "type": "tool_call",
        }
    ],
    usage_metadata={
        "input_tokens": 320,
        "output_tokens": 18,
        "total_tokens": 338,
    },
)
```

读取结果：

```python
type(response)                         # AIMessage
response.content                      # ""
bool(response.tool_calls)              # True
response.tool_calls[0]["name"]         # "retrieve_context"
response.tool_calls[0]["args"]         # {"query": "本地知识库默认使用什么 Embedding 模型？"}
response.tool_calls[0]["id"]           # "call-demo-001"
```

`content=""` 并不表示模型没有返回结果。这里模型返回的是结构化 Tool Call，而不是
自然语言；后续 `ToolNode` 才会真正执行 `retrieve_context`。

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
| 22 | [5_langgraph_agentic_rag/README.md](5_langgraph_agentic_rag/README.md) | `StateGraph`、条件路由、重试、Persistence、HITL |

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

## 19. LangGraph 显式控制流

[5_langgraph_agentic_rag/](5_langgraph_agentic_rag/) 不再只调用
`create_agent()`，而是把 Agent 的状态和跳转显式写成 Graph。

### 19.1 State、Node 与部分更新

```python
class LearningState(TypedDict, total=False):
    question: str
    route: str
    answer: str


def classify_question(state: LearningState) -> LearningState:
    return {"route": "knowledge"}
```

`state` 是当前完整状态。Node 返回的字典是“本节点要更新的字段”，不要求手动复制完整 state。

### 19.2 普通边与条件边

```python
workflow.add_edge(START, "classify_question")

workflow.add_conditional_edges(
    "classify_question",
    choose_route,
    {
        "knowledge": "retrieve",
        "smalltalk": END,
    },
)
```

- `add_edge(A, B)`：A 执行完固定进入 B。
- `add_conditional_edges(...)`：先调用路由函数，再把返回值映射到不同节点。
- `START` 和 `END` 是图的入口、出口，不是普通业务 Node。

### 19.3 `MessagesState` 与消息累加

```python
class AgenticRAGState(MessagesState, total=False):
    original_question: str
    rewrite_count: int
    used_evidence: list[dict]
```

`MessagesState` 已经定义了带消息 reducer 的 `messages` 字段。Node 返回：

```python
{"messages": [AIMessage(...)]}
```

表示把新消息追加到轨迹，而不是直接覆盖此前的 HumanMessage、AIMessage 和 ToolMessage。

### 19.4 `ToolNode` 执行 Tool Call

```python
workflow.add_node(
    "retrieve",
    ToolNode([retrieval_tool]),
)
```

真实顺序是：

```text
AIMessage.tool_calls
  ↓ ToolNode
调用本地 Python Tool
  ↓
ToolMessage(content=给模型看的文本, artifact=程序保留的结构化证据)
```

`bind_tools()` 只让模型知道 Tool Schema；`ToolNode` 才执行 Python Tool。

### 19.5 有上限的改写循环

```text
retrieve
  ↓
assess_evidence
  ├─ relevant → generate_answer
  ├─ weak 且 rewrite_count < max_rewrites → rewrite_question
  └─ weak 且达到上限 → refuse
```

图中有一条回边不代表无限循环。业务 state 必须保存计数，并提供明确结束分支。

`RetryPolicy(max_attempts=2)` 与 `max_rewrites` 不是一回事：

- `RetryPolicy` 处理同一个 Node 的暂时性执行错误。
- `max_rewrites` 控制业务层“改写问题后重新检索”的循环次数。

### 19.6 Checkpointer、`thread_id` 与人工确认

```python
graph = workflow.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "thread-1"}}

paused = graph.invoke(input_state, config=config)
final = graph.invoke(
    Command(resume={"decision": "approve"}),
    config=config,
)
```

Node 内的 `interrupt(payload)` 会暂停执行。恢复时必须使用同一个
`thread_id`，checkpointer 才能找到原来的 checkpoint。

`InMemorySaver` 只在当前进程有效；进程重启后数据消失。它适合教学和测试，不等于生产持久化。

### 19.7 `used_evidence` 与引用 ID 校验

目录 5 的生成顺序是：

```text
accepted Documents
  ↓ 先受 max_context_chars 限制
used_evidence
  ↓ Prompt 标注真实 chunk_id
answer + cited_chunk_ids
  ↓ 程序校验 cited IDs 是 context IDs 的子集
citations
```

模型只负责声明它使用了哪些 ID。`source`、`quote` 和分数仍由程序根据真实
Document 构建；模型返回不存在的 ID 时不能生成 citation。

### 19.8 Reducer 决定“覆盖”还是“合并”

State 字段没有 Reducer 时，新值直接覆盖旧值。用 `Annotated` 给字段声明
Reducer 后，LangGraph 会把旧值和本次 Node 返回的新值交给 Reducer：

```python
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class State(TypedDict, total=False):
    steps: Annotated[list[str], operator.add]
    messages: Annotated[list[BaseMessage], add_messages]
```

- `operator.add`：`旧 list + 新 list`，适合追加步骤或日志。
- `add_messages`：新 ID 追加；相同 message ID 更新原消息。
- Reducer 只定义单个字段的合并规则，不负责决定下一个 Node。

### 19.9 v2 Streaming 与自定义进度

```python
for part in graph.stream(
    input_state,
    stream_mode=["updates", "custom"],
    version="v2",
):
    print(part["type"], part["ns"], part["data"])
```

v2 每个流事件都有统一外壳：

| 字段 | 含义 |
| --- | --- |
| `type` | `updates`、`values`、`custom` 等模式 |
| `ns` | 当前图或子图的命名空间 |
| `data` | 该模式的实际数据 |

Node 可以发送不写入 State 的进度事件：

```python
from langgraph.config import get_stream_writer


def retrieve(state):
    writer = get_stream_writer()
    writer({"stage": "retrieve", "message": "正在检索"})
    return {"documents": [...]}
```

`custom` 事件用于 UI 进度；它不会自动成为可恢复的业务 State。需要恢复的
数据仍应由 Node 返回并交给 checkpointer。

### 19.10 RetryPolicy 与 `error_handler`

```python
from langgraph.errors import NodeError
from langgraph.types import Command, RetryPolicy


def recover(state, error: NodeError) -> Command:
    return Command(
        update={"status": f"compensated: {type(error.error).__name__}"},
        goto="finalize",
    )


workflow.add_node(
    "call_api",
    call_api,
    retry_policy=RetryPolicy(
        max_attempts=3,
        retry_on=ConnectionError,
    ),
    error_handler=recover,
)
```

- `max_attempts=3` 包含第一次执行，不是“第一次再加三次”。
- 只把短暂网络错误、限流等可恢复错误列为可重试。
- 参数错误、权限错误等业务失败应走条件边或立即拒绝。
- Node 抛异常时，本次返回更新不会写入 State。
- 重试耗尽后才进入 `error_handler`；`NodeError` 保存失败节点和原异常。

### 19.11 SQLite Checkpointer、历史、Replay 与 Fork

SQLite checkpointer 是单独依赖：

```bash
pip install langgraph-checkpoint-sqlite
```

```python
from langgraph.checkpoint.sqlite import SqliteSaver

config = {"configurable": {"thread_id": "thread-1"}}

with SqliteSaver.from_conn_string("checkpoints.sqlite") as saver:
    graph = workflow.compile(checkpointer=saver)
    graph.invoke(input_state, config=config)
    current = graph.get_state(config)
    history = list(graph.get_state_history(config))
```

时间旅行的两个动作：

```python
# Replay：用旧 checkpoint 的 config 原样重新执行其后续节点
replayed = graph.invoke(None, config=old_snapshot.config)

# Fork：先修改旧 checkpoint，再从相同位置走一条新路径
fork_config = graph.update_state(
    old_snapshot.config,
    {"amount": 10},
)
forked = graph.invoke(None, config=fork_config)
```

应选择 `snapshot.next` 仍有待执行 Node 的 checkpoint。最终 checkpoint 的
`next == ()`，从它 `invoke(None, ...)` 不会重新执行任何 Node。

### 19.12 受控多 Tool Graph 与服务合同

“模型知道多个 Tool”不代表模型应拥有所有权限。可以先用显式条件边划分能力：

```text
knowledge → retrieval Tool
business  → readonly metric Tool
export    → interrupt → approve 后才调用 Tool
smalltalk → 不调用 Tool
```

服务化时需要把 Graph 的运行语义映射到 HTTP：

- 普通 `invoke` 返回 `completed` 或 `interrupted`。
- 恢复接口必须携带原 `thread_id`。
- 同一 `thread_id` 可以保留 `turn_count`、`last_question` 等会话字段；新一轮仍要显式清空上一轮 answer/citations 等结果字段。
- SSE 可以传 `updates/custom/result`，但流本身不是 checkpoint。
- 进程内 `InMemorySaver` 重启即丢失；多进程服务不能假设内存线程共享。

### 19.13 Graph 评测先检查稳定合同

确定性测试优先检查：

1. 路由轨迹是否经过预期 Node。
2. 已知问题是否有有效引用，未知问题是否拒答且引用为空。
3. Tool 参数和返回数据源是否符合白名单。
4. 敏感动作是否先暂停。
5. approve/reject 后是否执行或跳过对应 Tool。

这些是程序可以严格判定的合同。回答文风、帮助程度等主观质量再单独使用模型
评审或人工评审，不能替代权限和引用检查。
