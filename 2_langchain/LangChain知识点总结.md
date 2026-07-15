# LangChain L1-L12 知识点总结

> 本文依据当前 langchain 目录中的示例代码整理。短文件多数是手写学习 Demo；L8-L12 的长文件是按官方教程扩展的主学习文件。
>
> 每课只保留一小段关键代码，省略依赖加载、模型配置和完整错误处理；代码用于理解调用关系，不是完整可直接运行的 Demo。

## 一、12 课学习主线

~~~text
L1  手工理解模型如何请求和执行工具
→ L2  用 LCEL 组合 Prompt、Model、Parser、Retriever
→ L3  用 Pydantic 定义工具参数和 Schema
→ L4  把模型工具调用解析成结构化数据
→ L5  手写工具路由和一次工具执行
→ L6  使用 create_agent 自动完成 Agent 循环、记忆和状态流
→ L7  让 Agent 返回稳定的结构化业务结果
→ L8  给 Agent 增加受控文件环境、技能和子 Agent
→ L9  文档切块、Embedding、向量库、语义检索
→ L10 固定 RAG 与 Agentic RAG
→ L11 用受限工具实现安全 SQL Agent
→ L12 用异步事件流组织 STT → Agent → TTS
~~~

## 二、先记住的通用对象

| 对象 | 含义 | 常见位置 |
| --- | --- | --- |
| Prompt | 给模型的提示模板 | L2 以后 |
| ChatModel | 调用聊天模型的 Runnable | L2 以后 |
| Message | 对话中的 Human、AI、Tool 消息 | L1、L5 以后 |
| Tool | 可被模型选择调用的 Python 能力 | L1、L3、L5 以后 |
| Runnable | 可被 invoke、batch、stream 等方式运行的组件 | L2 以后 |
| Document | 文档正文 page_content 加来源 metadata | L9、L10 |
| Retriever | 根据查询取回相关 Document 的接口 | L2、L9、L10 |
| Agent | 自动管理 模型 → 工具 → 模型 循环的运行时 | L6 以后 |

一个真实业务工具循环通常是：

~~~text
HumanMessage
→ AIMessage 中的 tool_calls
→ Python 或 LangChain 执行工具
→ ToolMessage 携带工具结果
→ AIMessage 根据结果生成最终回答
~~~

模型只会决定调用什么工具及其参数；真正执行工具的是 Python 或 LangChain 运行时。

## 三、L1：原生 Function Calling 基线

**对应文件：** [L1_functions_student.py](L1_functions_student.py)

L1 还没有使用 LangChain。它用 requests 直接请求 OpenAI-compatible 接口，目的是把工具调用的最底层协议看清楚。

### 核心知识点

- tools JSON Schema：声明工具名、描述、参数及必填字段。
- tool_choice="auto"：允许模型自行决定是否调用工具。
- tool_calls：模型返回的调用请求，包含名称、参数和调用 ID。
- role="tool" 与 tool_call_id：把执行结果对应回本次工具调用。

### 代码流程

~~~text
用户问题
→ requests.post(messages + tools)
→ 第一次模型响应
→ 若有 tool_calls，Python 调用 get_current_weather()
→ 将结果作为 role="tool" 消息追加
→ 第二次 requests.post()
→ 模型读取工具结果，生成最终回答
~~~

### 核心代码：回传工具执行结果

~~~python
if message.get("tool_calls"):
    messages.append(message)
    for tool_call in message["tool_calls"]:
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": call_function(tool_call),
        })
~~~

### 易错点

- function.arguments 可能是 JSON 字符串，需要先 json.loads。
- 一次响应可能有多个 tool_calls，要逐个执行。
- tool_call_id 必须与模型给出的 ID 对应。
- 真实项目要处理参数非法、工具异常和超时；密钥也不应硬编码在源码中。

## 四、L2：LCEL、Retriever、RAG 与 Runnable 调用方式

**对应文件：** [L2_LangChainExpressLanguage_LCEL.py](L2_LangChainExpressLanguage_LCEL.py)

L2 的主角是 LCEL，也就是 LangChain Expression Language。它用 | 把多个 Runnable 连接成一条链。

### 核心知识点

- ChatPromptTemplate：把输入变量填入提示词。
- ChatOpenAI：聊天模型 Runnable。
- StrOutputParser：把 AIMessage 的文本内容取出为字符串。
- RunnableMap：从同一份输入并行构造多个字段。
- invoke、batch、stream、ainvoke：单次同步、批量、同步流式、单次异步调用。
- with_fallbacks：主链抛异常时走备用链。

### 最基础 LCEL 链

~~~python
chain = prompt | model | output_parser
answer = chain.invoke({"topic": "bears"})
~~~

这里的 | 不是普通 Python 按位或，而是把前一段输出作为后一段输入。

### Retriever 与固定 RAG

~~~text
问题
→ Embeddings
→ 内存向量库检索
→ RunnableMap 构造 context 和 question
→ Prompt
→ Model
→ StrOutputParser
→ 字符串答案
~~~

L2 也演示 model.bind(tools=...)。它只让模型生成 tool_calls，不会自动执行工具或回传 ToolMessage；完整 Agent 循环要到 L6。

### 易错点

- StrOutputParser 只负责提取文本，不保证文本一定是合法 JSON。
- with_fallbacks 只在前一条链抛异常时触发，不能替代业务校验。
- Retriever 返回的是 Document 列表；生产 RAG 通常要显式格式化 page_content 与 metadata 后再放入 Prompt。

## 五、L3：Pydantic 工具参数与 Tool Schema

**对应文件：** [L3_Function_Calling_In_Langchain.py](L3_Function_Calling_In_Langchain.py)

L3 学习先用 Pydantic 类定义数据结构，再转成模型能理解的工具 Schema。

### 核心知识点

- BaseModel：定义有类型的数据模型。
- Field(description=...)：给字段增加模型可读的说明和约束。
- model_json_schema()：从 Pydantic 模型生成 JSON Schema。
- ValidationError：本地创建 Pydantic 对象时的校验错误。
- model.bind(tools=..., tool_choice="auto")：把工具定义注册给模型。

### 两种 Pydantic 作用

1. 本地数据校验：例如创建 User 或 ClassRoom 时检查字段类型。
2. 工具参数描述：例如 WeatherSearch、ArtistSearch 被转换为工具的 parameters Schema。

### 核心代码：Pydantic Schema 注册为工具

~~~python
weather_tool = pydantic_to_tool(WeatherSearch)
model = build_zhipu_chat_model(deps["ChatOpenAI"]).bind(
    tools=[weather_tool],
    tool_choice="auto",
)
message = model.invoke("旧金山今天的天气怎么样？")
~~~

~~~text
Pydantic 类
→ model_json_schema()
→ OpenAI-compatible tools Schema
→ model.bind(tools=...)
→ 模型返回 tool_calls
~~~

### 易错点

- tool_choice="auto" 表示模型可以调用工具，不代表一定调用。
- 模型返回 tool_calls 后，仍应在真正执行前做参数校验。
- 本课展示的是模型选择工具，不包含真实工具执行及 ToolMessage 回环。

## 六、L4：Tagging 与信息抽取

**对应文件：** [L4_Tagging_Extraction.py](L4_Tagging_Extraction.py)

L4 把工具调用当作结构化输出载体，再用 Parser 变成 Pydantic 对象。

### Tagging 与 Extraction 的区别

| 类型 | 目标 | 示例 |
| --- | --- | --- |
| Tagging | 给整段文本打总体标签 | 情感、语言、评分 |
| Extraction | 提取文本中明确出现的字段或实体 | 姓名、年龄、论文信息 |

### 核心知识点

- Literal[...]：限制字段只能取固定枚举值。
- str | None、int | None：字段允许没有值，避免模型猜测。
- PydanticToolsParser：解析模型产生的工具调用参数。
- first_tool_only=True：只取第一个工具调用。
- RecursiveCharacterTextSplitter 与 chain.batch：长文分块后批量抽取。

### 标准结构化抽取链

~~~text
Prompt
→ Model 发出 Schema 工具调用
→ PydanticToolsParser
→ 已校验的 Pydantic 对象
~~~

### 核心代码：把工具调用解析为对象

~~~python
parser = deps["PydanticToolsParser"](
    tools=[Information],
    first_tool_only=True,
)
chain = prompt | model | parser
info = chain.invoke({"input": "Joe is 30. His mom is Martha."})
~~~

这里的工具不是外部函数，不会查询天气或修改数据；它只承载模型必须遵守的输出 Schema。

### 易错点

- 结构化数据常在 tool_calls 中，AIMessage.content 可能为空。
- first_tool_only=True 会丢弃后续工具调用。
- 分块抽取后 flatten 只负责展平，不会自动去重。

## 七、L5：Tools、Routing 与外部 API

**对应文件：** [L5_Tools_Routing_APIs.py](L5_Tools_Routing_APIs.py)

L5 用 @tool 把 Python 函数包装成 LangChain Tool，并手写“模型选择 → 本地执行”的路由流程。

### 核心知识点

- @tool(args_schema=...)：将函数及其参数 Schema 暴露给模型。
- tool.invoke(args)：在本地真正执行一个 Tool。
- tool_to_openai_tool()：把 LangChain Tool 转成 OpenAI/Zhipu 兼容的 tools JSON Schema。
- route_once()：根据模型返回的 tool_calls 手动执行对应函数。

### 代码流程

~~~text
用户问题
→ prompt | model
→ AIMessage.tool_calls
→ execute_tool_call()
→ 本地 Python 执行 search_course_notes 或 current_weather_online
→ 返回 tool_results
~~~

### 核心代码：根据模型请求执行本地 Tool

~~~python
name = tool_call["name"]
args = tool_call.get("args") or {}
if isinstance(args, str):
    args = json.loads(args)
result = tool_map[name].invoke(args)
~~~

### 与 L6 的关键差异

L5 在执行一次工具后就结束，未将结果包装为 ToolMessage 再交还模型，因此它是“手写路由和工具执行”，不是完整 Agent 循环。

### 易错点

- 模型不会自行执行 Python 函数。
- 需要处理未知工具、字符串形式的 JSON 参数和外部 API 网络失败。
- 工具权限和输入校验必须由本地代码实现，不能只靠 Prompt。

## 八、L6：create_agent、Memory 与状态流

**对应文件：** [L6_Agents_Memory_Streaming.py](L6_Agents_Memory_Streaming.py)

L6 开始由 create_agent 接管 Agent 循环，开发者不再需要手动拼 ToolMessage。

### 核心知识点

- create_agent(model=..., tools=..., system_prompt=...)。
- agent.invoke(...)：运行到最终结果。
- agent.stream(..., stream_mode="values")：逐步读取 Agent 状态。
- InMemorySaver() 与 configurable.thread_id：保存同一会话的历史消息。

### 自动循环

~~~text
HumanMessage
→ AIMessage（tool_calls）
→ LangChain 执行 Tool
→ ToolMessage（工具结果）
→ AIMessage（最终自然语言回答）
~~~

### 核心代码：创建带记忆的 Agent

~~~python
agent = build_agent(deps, use_memory=True)
config = {"configurable": {"thread_id": "demo-thread"}}
result = agent.invoke(
    {"messages": [{"role": "user", "content": "查询默认城市天气"}]},
    config=config,
)
~~~

### 记忆

同一个 InMemorySaver 加同一个 thread_id，会让下一轮请求带上之前保存的消息。例如第一轮记住默认城市，第二轮可以继续查询该城市天气。

### 易错点

- stream_mode="values" 是完整状态快照，不是逐 token 文本；常用 chunk["messages"][-1] 查看最新消息。
- InMemorySaver 只在当前 Python 进程内有效；换 thread_id 或重启进程就失去记忆。
- result["messages"] 是执行轨迹，最后一条 AIMessage.content 才通常是最终自然语言答案。

## 九、L7：Agent 结构化输出

**对应文件：** [L7_Agents_Structured_Output.py](L7_Agents_Structured_Output.py)

L7 的重点不是调用业务工具，而是让模型按固定业务数据合同返回结果。

### 核心知识点

- Pydantic Schema：例如 ContactInfo、ProductReview、SupportTicket。
- ToolStrategy(schema=...)：把 Schema 作为 Agent 的 response_format。
- structured_response：LangChain 校验后的结构化结果，适合下游业务代码使用。
- messages：执行过程记录，适合调试。

### 代码流程

~~~text
用户文本
→ create_agent(response_format=ToolStrategy(schema))
→ 模型按 Schema 生成字段
→ LangChain 校验并解析
→ result["structured_response"]
~~~

### 核心代码：把 Schema 设为 Agent 输出合同

~~~python
response_format = deps["ToolStrategy"](schema=ContactInfo)
agent = deps["create_agent"](
    model=build_model(deps["ChatOpenAI"]),
    tools=[],
    response_format=response_format,
)
result = agent.invoke({"messages": [{"role": "user", "content": "抽取联系人"}]})
contact = result["structured_response"]
~~~

即使 tools=[]，消息轨迹中也可能出现 tool_calls；这里是 ToolStrategy 为实现结构化输出使用的内部 Schema 调用，不是调用了真实天气、数据库等业务工具。

## 十、L8：Deep Agent、Sandbox、Middleware 与子 Agent

**概念文件：** [L8_Deep_Agent_From_Scratch.py](L8_Deep_Agent_From_Scratch.py)
**本地可运行 Demo：** [L8.py](L8.py)

L8 的核心不是更换模型，而是在普通 Agent 外增加受控环境和能力层。

~~~text
普通 Agent
→ 文件系统或 Sandbox
→ 长上下文摘要
→ 按需加载 Skills
→ 任务规划
→ 子 Agent 委派
~~~

### 主要 Middleware

| Middleware | 作用 |
| --- | --- |
| FilesystemMiddleware | 将 sandbox 的读、写、执行能力暴露为工具 |
| SummarizationMiddleware | 压缩旧消息和工具输出，控制上下文长度 |
| SkillsMiddleware | 按需加载 /skills 下的领域说明 |
| TodoListMiddleware | 提供待办和规划能力 |
| SubAgentMiddleware | 将专项子 Agent 暴露为可委派能力 |

### 本地 sandbox 流程

~~~text
Agent
→ list_sandbox_files
→ read_sandbox_file("/sales.csv")
→ analyze_sales_file("/sales.csv")
→ write_analysis_report(...)
→ 最终回答关键销售数据和报告路径
~~~

L8.py 使用 safe_sandbox_path() 限制工具只能访问 .local_l8_sandbox，路径安全边界由 Python 工具代码强制，而不是只靠 Prompt。

### 核心代码：阻止路径逃逸

~~~python
candidate = (LOCAL_SANDBOX_ROOT / path.lstrip("/")).resolve()
root = LOCAL_SANDBOX_ROOT.resolve()
if candidate != root and root not in candidate.parents:
    raise ValueError("路径越界，不允许访问 sandbox 外部文件")
return candidate
~~~

远端 LangSmith sandbox 需要额外依赖、有效凭据及账号权限；学习和验证本地流程时，应以 L8.py 的本地 sandbox Demo 为准。

## 十一、L9：语义搜索与知识库

**对应文件：** [L9_Semantic_Search_Knowledge_Base.py](L9_Semantic_Search_Knowledge_Base.py)

L9 只解决“从资料中找相关内容”，尚未让模型基于资料生成答案。

### 核心知识点

- Document(page_content, metadata)：正文和来源等附加信息。
- Embeddings：向量生成接口。
  - embed_documents(texts)：文档入库时生成向量。
  - embed_query(text)：查询时生成向量。
- RecursiveCharacterTextSplitter：长文切块。
- InMemoryVectorStore：内存向量库，进程结束后数据消失。
- similarity_search(query, k)：直接检索最相近的 top-k 文档。
- @chain：把普通函数包装成 Runnable。
- as_retriever()：将向量库包装为标准 Retriever。

### 检索流程

~~~text
Document 列表
→ 文档切块
→ embed_documents
→ vector_store.add_documents
→ embed_query
→ similarity_search
→ 相关 Document 列表
~~~

### 核心代码：入库与 top-k 检索

~~~python
embeddings = build_embeddings(deps)
vector_store = deps["InMemoryVectorStore"](embeddings)
vector_store.add_documents(documents=docs)
results = vector_store.similarity_search(query, k=2)
~~~

### 三种调用层次

1. similarity_search_demo：直接调用向量库。
2. retriever_demo：用 @chain 包装检索函数，再使用 batch。
3. as_retriever_demo：使用标准 Retriever 的 invoke。

### 易错点

- build_embeddings() 返回的是 Embedding 生成器对象，不是某一个向量。
- k 是返回结果数，不是向量维度。
- 当前默认的 NewKeywordEmbeddings 是可解释、稳定的教学实现，不是生产级语义 Embedding。
- compact_documents() 只截断打印内容，不修改向量库中的原文。

## 十二、L10：RAG、检索工具与 Agentic RAG

**对应文件：** [L10_RAG_Agent.py](L10_RAG_Agent.py)

L10 在 L9 的检索能力上，学习“检索后回答”的两条路线。

### 资料构建流程

~~~text
网页或 fallback Document
→ RecursiveCharacterTextSplitter
→ InMemoryVectorStore
→ similarity_search 或 Retriever
~~~

load_web_page() 会先把网页正文放进一个 Document；后续 splitter 才将其切为多个 chunk。网络读取失败时会退回 fallback_documents()。

### 路线一：Agentic RAG

关键函数：build_rag_agent()、define_retrieval_tool()、rag_agent_stream_demo()。

~~~text
用户问题
→ AIMessage 请求 retrieve_context
→ retrieve_context 执行 similarity_search
→ ToolMessage
   content：给模型看的检索文本
   artifact：给 Python 保留的 Document 列表
→ AIMessage 基于资料组织答案
~~~

@tool(response_format="content_and_artifact") 的核心是“检索 → 序列化给模型 → 原始文档留给程序”：

~~~python
@tool(response_format="content_and_artifact")
def retrieve_context(query: str):
    retrieved_docs = vector_store.similarity_search(query, k=2)
    serialized = "\n\n".join(
        f"Source: {doc.metadata}\nContent: {doc.page_content}"
        for doc in retrieved_docs
    )
    return serialized, retrieved_docs
~~~

模型可以决定是否检索、检索几次；因此它不是固定先检索。

### 路线二：固定先检索的普通 RAG

关键函数：two_step_rag_chain_demo()。

~~~text
用户问题
→ Retriever（每次固定执行）
→ {context, question}
→ Prompt
→ Model
→ StrOutputParser
→ 字符串答案
~~~

若业务要求每个问题必须检索，应选择这条固定流程，而不是仅靠 Agent 的系统提示要求调用工具。

### 易错点

- ToolMessage.content 给模型看；artifact 给后端程序做来源展示、日志或 WebSocket 推送，不会自动发送给前端。
- LOAD_LIVE_WEB_PAGE=True 不代表必然使用了网页资料，应检查 Document.metadata["source"]。
- 默认教学路径常使用 KeywordEmbeddings，不等于真实语义检索。

## 十三、L11：安全 SQL Agent

**对应文件：** [L11_SQL_Agent.py](L11_SQL_Agent.py)

L11 让 Agent 通过受限 Tool 查询 SQLite，并展示数据库连接、表结构探索和只读保护。

### 核心知识点

- @contextmanager 与 yield conn：把“打开 → 使用 → finally 关闭”包装成 with 语法。
- database_connection(path, *, read_only=False)：星号后的 read_only 必须使用关键字传参。
- SQLite URI 的 mode=ro：用只读方式打开数据库。
- sqlite3.Row：可用 row["列名"] 读取结果。
- rows_to_dicts()：把查询结果转成可 JSON 序列化的字典列表。
- @tool 和 @tool(args_schema=...)：把数据库能力注册给 Agent。
- EXPLAIN QUERY PLAN：检查 SQL 能否生成执行计划。
- sqlite_master：查询主数据库中的表名。
- PRAGMA table_info(table)：查看表字段。

### 工具使用顺序

~~~text
list_tables()
→ describe_tables("Genre, Track")
→ check_sql_query("SELECT ...")
→ run_sql_query("SELECT ...")
~~~

### 核心代码：每次 Tool 调用使用独立只读连接

~~~python
with database_connection(database_path, read_only=True) as conn:
    cursor = conn.execute(query)
    rows = rows_to_dicts(cursor)
return json.dumps(rows[:20], ensure_ascii=False)
~~~

Agent 面对自然语言问题时，应先查表、再看字段、再生成只读 SELECT，最后根据行结果回答。

### 安全与线程

- 每一次工具调用都通过 database_connection() 新建并关闭连接，避免共享 SQLite 连接跨线程使用。
- ensure_read_only_sql() 只是一层教学用字符串检查，不是完整 SQL 安全解析器。
- 生产环境还应限制数据库权限、校验表名、使用白名单，并控制结果量和查询超时。
- SQLite 数据库通常就是一个 .db 文件；下载的 Chinook 文件已经包含 schema 和数据，不需要单独的 host、port、用户名或密码。

## 十四、L12：流式语音 Agent 管道

**对应文件：** [L12_Voice_Agent.py](L12_Voice_Agent.py)

L12 用异步生成器和 RunnableGenerator 组织持续事件流：

~~~text
STT → LangChain Agent → TTS
~~~

### 统一事件对象

VoiceAgentEvent 使用 dataclass 定义四种事件：

| 事件 type | 有意义的字段 | 含义 |
| --- | --- | --- |
| stt_chunk | text、transcript | 识别过程中的部分转写 |
| stt_output | text、transcript | 最终完整转写，触发 Agent |
| agent_chunk | text | 最终 AI 回复文本 |
| tts_chunk | audio | TTS 音频二进制片段 |

其中 text 是通用文本字段；transcript 专门表示 STT 转写；audio 是音频 bytes。

### 三段异步流

~~~text
fake_audio_stream
  AsyncIterator[bytes]
→ stt_stream
  逐步输出 stt_chunk，结束时输出 stt_output
→ agent_stream
  透传 STT 事件；仅收到 stt_output 时调用 Agent
→ tts_stream
  透传所有事件；每遇到 agent_chunk 再增加一个 tts_chunk
~~~

### 核心代码：用 RunnableGenerator 连接三段流

~~~python
pipeline = (
    deps["RunnableGenerator"](stt_stream)
    | deps["RunnableGenerator"](agent_stage)
    | deps["RunnableGenerator"](tts_stream)
)
~~~

### Agent 内部流程

~~~text
stt_output.transcript
→ HumanMessage
→ AIMessage 请求 add_to_order
→ ToolMessage 返回工具结果
→ 最终 AIMessage
→ VoiceAgentEvent.agent_chunk
→ VoiceAgentEvent.tts_chunk
~~~

agent.astream(..., stream_mode="values") 返回的是整个 Agent 的状态快照流，不是最终字符串本身。当前代码只保留：

~~~text
type == "ai"
且没有 tool_calls
→ 工具完成后最终可朗读的 AI 回复
~~~

这会排除用户消息、工具调用请求和 ToolMessage，避免把工具结果误朗读成 Agent 回复。

### 异步与管道知识点

- AsyncIterator[T]：可被 async for 持续消费，每次产出一个 T。
- await：等待异步操作或让出事件循环。
- yield：产出一个事件并暂停，等待消费者请求下一个。
- RunnableGenerator：把异步生成器包装为 LCEL 的流式阶段。
- |：连接 STT、Agent、TTS 三个阶段。
- pipeline.atransform(...)：异步输入流转换为异步输出流。

agent_stream 里的 agent_stage 是适配层：RunnableGenerator 只自动传入上游 stream，而 agent_stream 还需要 deps，因此它用 async for 和 yield 绑定 deps 并保持真正的异步生成器形式。

### 当前 Demo 的边界

- fake_audio_stream 是把文本 encode 为 bytes，模拟音频输入。
- tts_stream 是把最终文本 encode("utf-8")，模拟音频输出。
- 它们不是实际 PCM、WAV 或 MP3；接入真实 STT/TTS 服务时应替换这两个 Adapter。
- await asyncio.sleep(0) 只是模拟异步让出执行权，不改变当前 Demo 的业务结果。

## 十五、最容易混淆的四组概念

| 容易混淆 | 正确区分 |
| --- | --- |
| 模型 tool_calls 与工具执行 | tool_calls 是模型请求；Python 或 LangChain 才真的执行 |
| L5 与 L6 | L5 手写一次工具路由；L6 是 create_agent 自动循环 |
| L4/L7 的 Schema 工具调用与业务工具 | 前者用于约束结构化输出；后者执行真实业务能力 |
| L9 检索与 L10 RAG | L9 找资料；L10 把资料交给模型组织回答 |
| 固定 RAG 与 Agentic RAG | 固定 RAG 每次都检索；Agentic RAG 由模型决定是否、何时检索 |
| L12 的 agent.astream 与 pipeline.atransform | 前者流式读取 Agent 内部状态；后者流式连接整个语音管道 |

## 十六、建议的复习顺序

1. 先跑 L1，手工跟踪一次 tool_calls、tool_call_id 和 role="tool"。
2. 再跑 L2，理解 Prompt | Model | Parser 以及 invoke、batch、stream。
3. 对照 L5 和 L6，重点理解“手写循环”为什么会被 create_agent 替代。
4. 用 L7 练习把自然语言输入变成稳定的 Pydantic 数据。
5. 用 L9 → L10 理解“检索”和“基于检索回答”的分界。
6. 阅读 L11 的工具设计，理解为什么 Agent 需要权限边界。
7. 最后阅读 L12，把异步流、Agent 工具循环和 TTS 事件串起来。

## 十七、生产实践提醒

- 不要将 API Key、数据库密码等凭据硬编码或提交到仓库。
- Tool 的描述、输入 Schema、权限边界和错误处理都属于业务契约。
- 对外部 API、文件系统、数据库和 SQL 都应设置超时、白名单、最小权限和审计日志。
- 向量库、Embedding、Prompt、Tool 返回值与最终回答要分层观察，避免只看最终文本而忽略执行过程。
