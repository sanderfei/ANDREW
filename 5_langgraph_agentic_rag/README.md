# 目录 5：LangGraph Agentic RAG

本目录对应学习路线第 8–9 周的 LangGraph 主线：先把目录 4 已验证的本地知识库检索能力包装成 Tool，再逐步学习显式控制流、Reducer、Streaming、容错、持久化、时间旅行、人工确认、多工具编排、FastAPI 服务化、评测、并行任务、子图、异步运行和 Functional API。

主教程来自 LangChain 官方：

- [Build a custom RAG agent with LangGraph](https://docs.langchain.com/oss/python/langgraph/agentic-rag)
- [Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)
- [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)
- [Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Use time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)
- [Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [Build a SQL agent](https://docs.langchain.com/oss/python/langchain/sql-agent)
- [Test LangGraph applications](https://docs.langchain.com/oss/python/langgraph/test)

## 与前面目录的关系

| 目录 | 控制方式 | 重点 |
| --- | --- | --- |
| `2_langchain/L10_RAG_Agent.py` | `create_agent()` 隐藏大部分 Agent 循环 | 理解 Model → Tool → ToolMessage → Model |
| `4_rag_knowledge_base_service` | 固定两步 RAG，每次都检索 | 持久化索引、gate、拒答、引用和 API |
| `5_langgraph_agentic_rag` | 显式 `StateGraph` | State、Node、条件边、重试、改写循环、人工确认 |

目录 5 不修改目录 4，也不重新发明 Loader、Embedding 或 Chroma。`local_rag_adapter.py` 直接复用目录 4 的：

- `Settings`
- `IncrementalIndexer`
- 本地 MiniLM、Hash 和可选 GLM Embedding
- Chroma 持久化
- 稳定 `chunk_id`
- 中文/英文词项和技术词 gate

目录 5 使用自己的 `runtime/`，不会覆盖目录 4 的 Chroma 与 manifest。

## 学习顺序

这里按“一个完整主题一个文件”组织，没有把每个 API 拆成许多很短的脚本：

| Part | 文件 | 合并后的主题 |
| --- | --- | --- |
| 1 | `part1_graph_basics.py` | State、Node、Edge、条件边 |
| 2 | `part2_agentic_rag.py` | 路由、检索、证据判断、改写、回答、拒答 |
| 3 | `part3_persistence_hitl.py` | 内存 checkpoint、thread、interrupt/resume |
| 4 | `part4_readonly_sql_tools.py` | Tool Schema、SQL 白名单、只读连接 |
| 5 | `part5_state_reducers_streaming.py` | Reducer、消息更新、v2 Streaming、Mermaid |
| 6 | `part6_fault_tolerance.py` | 业务分支、RetryPolicy、NodeError、失败补偿 |
| 7 | `part7_sqlite_persistence_time_travel.py` | SQLite、跨重建恢复、历史、replay、fork |
| 8 | `part8_controlled_multi_tool_graph.py` | RAG + SQL + HITL 受控多工具图 |
| 9 | `part9_fastapi_runtime.py` | invoke、SSE stream、thread resume API |
| 10 | `part10_evaluate.py` | 路由轨迹、引用、只读与审批合同评测 |
| 11 | `part11_parallel_send.py` | 并行分支、fan-in、Reducer、`Send` 动态任务 |
| 12 | `part12_subgraphs.py` | 子图、状态 Schema、checkpoint 模式、父图跳转 |
| 13 | `part13_async_streaming.py` | 异步 Graph、完整 Streaming、运行限制 |
| 14 | `part14_functional_api.py` | `@task`、`@entrypoint`、恢复与增量运行 |

### Part 1：Graph 基础

[part1_graph_basics.py](part1_graph_basics.py) 不调用模型，先看清四个概念：

```text
State
  ↓
Node：读取 state，返回部分更新
  ↓
Edge：固定进入下一节点
  ↓
Conditional Edge：根据 state 选择下一节点
```

运行：

```bash
.venv/bin/python 5_langgraph_agentic_rag/part1_graph_basics.py
```

### Part 2：受控 Agentic RAG

[part2_agentic_rag.py](part2_agentic_rag.py) 对应官方 Agentic RAG 主教程。

```text
START
  ↓
generate_query_or_respond
  ├─ 闲聊 ───────────────────────────────→ END
  └─ tool_call
       ↓
     retrieve
       ↓
     assess_evidence
       ├─ relevant ─→ generate_answer ───→ END
       ├─ weak + 未超上限 → rewrite_question ─┐
       │                                      │
       └─ weak + 已到上限 → refuse ────────→ END
                                              │
                 generate_query_or_respond ←──┘
```

官方示例主要展示 Graph API。本地适配增加了四道边界：

1. Chroma Top-K 后仍执行目录 4 的确定性 relevance gate。
2. `max_rewrites` 限制问题改写次数，避免无限循环。
3. 先确定真正进入 Prompt 的 `used_evidence`。
4. 在线模型结构化返回 `answer + cited_chunk_ids`；程序验证 ID 是本次上下文 ID 的子集，再根据真实 Document 构造 citation。无有效引用时 fail closed。

离线教学模式不调用模型和网络：

```bash
.venv/bin/python 5_langgraph_agentic_rag/part2_agentic_rag.py
```

第一次会在 `5_langgraph_agentic_rag/runtime/hash/` 建立独立 Hash 索引。

本地 MiniLM 检索、在线模型做路由/判断/改写/回答：

```bash
.venv/bin/python 5_langgraph_agentic_rag/part2_agentic_rag.py \
  --mode live \
  --embedding local
```

需要根目录 `.env` 已配置 `ZHIPU_API_KEY`、`ZHIPU_BASE_URL` 和 `ZHIPU_CHAT_MODEL`。代码和文档中不保存真实凭据。

测试拒答与一次改写：

```bash
.venv/bin/python 5_langgraph_agentic_rag/part2_agentic_rag.py \
  --question "QUASAR_TIDE_9999 是什么？" \
  --max-rewrites 1
```

### Part 3：Persistence 与人工确认

[part3_persistence_hitl.py](part3_persistence_hitl.py) 演示：

```text
compile(checkpointer=InMemorySaver())
configurable.thread_id
interrupt(...)
Command(resume=...)
```

运行批准和拒绝两条分支：

```bash
.venv/bin/python 5_langgraph_agentic_rag/part3_persistence_hitl.py
.venv/bin/python 5_langgraph_agentic_rag/part3_persistence_hitl.py --reject
```

`InMemorySaver` 只在当前 Python 进程内保存 checkpoint。生产环境需要 SQLite、PostgreSQL 等持久化 checkpointer。

### Part 4：只读 SQL 白名单 Tool

[part4_readonly_sql_tools.py](part4_readonly_sql_tools.py) 没有让模型直接提交任意 SQL，而是只暴露两个参数：

```text
metric：固定业务指标枚举
region：固定区域枚举
```

程序根据白名单选择固定 `SELECT`，数据库连接同时使用：

```text
SQLite URI mode=ro
PRAGMA query_only = ON
```

因此 Tool Schema、SQL 模板和数据库连接形成三层边界。

运行：

```bash
.venv/bin/python 5_langgraph_agentic_rag/part4_readonly_sql_tools.py
```

### Part 5：Reducer、Streaming 与图可视化

[part5_state_reducers_streaming.py](part5_state_reducers_streaming.py) 把“状态如何合并”和“如何观察状态变化”放在同一课：

- 普通字段默认覆盖。
- `Annotated[list, operator.add]` 追加列表。
- `add_messages` 追加新消息，并按 message ID 更新旧消息。
- `version="v2"` 同时消费 `values`、`updates` 和 `custom`。
- `get_stream_writer()` 从 Node 发出自定义进度。
- `draw_mermaid()` 生成无需联网的 Mermaid 文本。

```bash
.venv/bin/python \
  5_langgraph_agentic_rag/part5_state_reducers_streaming.py
```

### Part 6：重试与失败补偿

[part6_fault_tolerance.py](part6_fault_tolerance.py) 明确区分：

```text
业务不满足 → 普通条件边，不重试
暂时性错误 → RetryPolicy 只重跑失败 Node
重试耗尽   → error_handler(NodeError) → 补偿分支
```

```bash
.venv/bin/python 5_langgraph_agentic_rag/part6_fault_tolerance.py
```

示例把间隔缩短到 `0.01` 秒以便学习测试；生产参数应按真实依赖的限流和恢复时间配置。

### Part 7：SQLite Persistence 与时间旅行

[part7_sqlite_persistence_time_travel.py](part7_sqlite_persistence_time_travel.py) 使用官方独立包 `langgraph-checkpoint-sqlite`。示例会：

1. 同一线程连续执行 `+2`、`+3`。
2. 关闭连接并重建 Graph，恢复值 `5` 后继续 `+1`。
3. 用 `get_state_history()` 找到旧 checkpoint。
4. replay 旧路径，仍得到 `5`。
5. 用 `update_state()` 把旧输入改成 `+10`，fork 后得到 `12`。

```bash
.venv/bin/python \
  5_langgraph_agentic_rag/part7_sqlite_persistence_time_travel.py
```

默认数据库写入 `runtime/`，已被 `.gitignore` 忽略。

### Part 8：RAG + SQL + HITL 受控多工具图

[part8_controlled_multi_tool_graph.py](part8_controlled_multi_tool_graph.py) 把前面相似能力组合成一个显式 Graph：

```text
route_request
  ├─ knowledge → retrieval Tool → grounded answer / refusal
  ├─ business  → readonly metric Tool
  ├─ export    → preview → interrupt
  │                         ├─ approve → metric Tool → preview result
  │                         └─ reject  → no Tool call
  └─ smalltalk → direct answer
```

这仍是单 Agent 的受控编排，不是多 Agent。路由只是选择被允许的能力，模型不会收到任意 SQL，也不能绕过审批执行导出分支。

同一个 `thread_id` 再次调用时，checkpointer 会保留 `turn_count` 和
`last_question`；新请求会重置上一轮 answer/citations/metric 等结果字段，避免
结果串线。示例只演示会话状态，不把上一轮答案自动塞入当前知识回答。

```bash
.venv/bin/python \
  5_langgraph_agentic_rag/part8_controlled_multi_tool_graph.py \
  --question "华东已完成订单营收是多少？"

.venv/bin/python \
  5_langgraph_agentic_rag/part8_controlled_multi_tool_graph.py \
  --question "导出华东已完成订单营收" \
  --decision approve
```

“导出”只返回教学预览，不创建文件、不发送消息。

### Part 9：FastAPI invoke、SSE 与恢复接口

[part9_fastapi_runtime.py](part9_fastapi_runtime.py) 将 Part 8 的运行时合同暴露为：

| 方法与路径 | 用途 |
| --- | --- |
| `GET /health` | 查看本地运行时能力 |
| `POST /v1/invoke` | 普通调用；可能返回 `interrupted` |
| `POST /v1/stream` | 用 SSE 返回 v2 `updates/custom/result` |
| `POST /v1/threads/{thread_id}/resume` | 使用同一 thread 恢复审批 |

```bash
.venv/bin/uvicorn \
  part9_fastapi_runtime:create_default_app \
  --factory \
  --app-dir 5_langgraph_agentic_rag \
  --port 8001
```

本课使用进程内 `InMemorySaver`，因此教学服务固定单 worker；重启后线程消失。要跨重启恢复，应采用 Part 7 的持久化 checkpointer，并按服务并发模型配置数据库连接。

### Part 10：Graph 合同评测

[part10_evaluate.py](part10_evaluate.py) 使用临时来源、Hash Embedding 和临时 SQLite，不调用外部模型。六条用例、31 项合同检查覆盖：

- 已知知识的检索轨迹和真实引用。
- 未知知识的拒答与空引用。
- 只读业务指标的精确结果和数据源。
- 闲聊跳过工具。
- 导出在批准前暂停，批准后才查指标。
- 拒绝导出时不产生指标结果。

```bash
.venv/bin/python 5_langgraph_agentic_rag/part10_evaluate.py

# 可选保存报告；reports/ 已被忽略
.venv/bin/python 5_langgraph_agentic_rag/part10_evaluate.py \
  --output 5_langgraph_agentic_rag/reports/evaluation.json
```

### Part 11：并行分支、fan-in 与 `Send`

[part11_parallel_send.py](part11_parallel_send.py) 同时演示两类并行：

- 静态 fan-out：一条边进入多个 Node，再由列表边等待全部完成后 fan-in。
- 动态 fan-out：路由 Node 返回多个 `Send("analyze_subject", item)`，按运行时数据创建任务。
- 并行 Node 更新同一字段时必须配置 Reducer，否则触发 `InvalidUpdateError`。
- `config["max_concurrency"]` 控制同一批任务的最大并发数。

```bash
.venv/bin/python \
  5_langgraph_agentic_rag/part11_parallel_send.py \
  --max-concurrency 3
```

### Part 12：Subgraph 子图

[part12_subgraphs.py](part12_subgraphs.py) 展示父图组合子图时最容易混淆的边界：

- 子图可以和父图共享 State，也可以通过包装 Node 转换不同 State Schema。
- `input_schema`、`output_schema` 与内部私有字段可以限制对子图的输入输出。
- 子图 `checkpointer=None/True/False` 分别表示默认继承、同 thread 保留内部状态和关闭持久化。
- `stream(..., subgraphs=True)` 会返回 namespace，用于识别事件属于哪层图。
- 子图可以用 `Command.PARENT` 把控制权交给父图中的指定 Node。

```bash
.venv/bin/python 5_langgraph_agentic_rag/part12_subgraphs.py
```

### Part 13：异步 Graph 与完整 Streaming

[part13_async_streaming.py](part13_async_streaming.py) 使用真正的 `async def` Node 和
`astream()`，覆盖 `values`、`updates`、`messages`、`custom`、`checkpoints`、`tasks`
及 `debug` 事件。示例还演示：

- `RunnableConfig` 传递 `thread_id`、tags、metadata 和 `max_concurrency`。
- `aget_state()` 异步读取最新 checkpoint。
- `recursion_limit` 阻止失控循环。
- Graph 的 `timeout` 把过慢 Node 转换为 `NodeTimeoutError`。

```bash
.venv/bin/python \
  5_langgraph_agentic_rag/part13_async_streaming.py \
  --max-concurrency 2
```

### Part 14：Functional API

[part14_functional_api.py](part14_functional_api.py) 用 `@task` 和 `@entrypoint` 表达动态
工作流。它与 Graph API 使用同一套 persistence、interrupt 和 `Command(resume=...)`
能力，但控制流写成普通 Python：

- `task()` 返回 Future，读取 `.result()` 时取得结果。
- checkpoint 会保存已完成 Task 的结果，恢复 entrypoint 时不会重复其外部副作用。
- entrypoint 函数的 `previous` 参数读取同一 thread 上一轮的持久化输出。
- `entrypoint.final(value=..., save=...)` 分开“本轮返回值”和“下一轮 previous”。

```bash
.venv/bin/python \
  5_langgraph_agentic_rag/part14_functional_api.py \
  --decision approve
```

## 安装依赖

当前 `.venv` 已包含目录 4 的依赖和 LangGraph。新环境运行：

```bash
.venv/bin/pip install \
  -r 2_langchain/requirements.txt \
  -r 4_rag_knowledge_base_service/requirements.txt \
  -r 5_langgraph_agentic_rag/requirements.txt
```

## 确定性冒烟测试

Part 1～4 原有冒烟：

```bash
.venv/bin/python 5_langgraph_agentic_rag/scripts/smoke.py
```

测试全部使用临时目录，覆盖：

- Hash Embedding 建库。
- 有答案问题：检索、gate、`used_evidence`、citation ID 子集校验。
- 无答案问题：改写一次、重新检索、最终拒答。
- 闲聊不检索。
- `thread_id`、interrupt、批准和拒绝恢复。
- SQLite 白名单指标。
- `mode=ro` 拒绝写入。
- Schema 拒绝不存在的业务指标。

测试没有创建测试类；临时来源、Chroma 和 SQLite 会在进程结束时自动清理。

Part 5～10 高级冒烟：

```bash
.venv/bin/python 5_langgraph_agentic_rag/scripts/smoke_advanced.py
```

高级冒烟覆盖 Reducer/Streaming、重试与补偿、SQLite 恢复/replay/fork、受控多工具路线、approve/reject、FastAPI、SSE 和六条评测用例。它同样只使用临时目录，不保留测试数据库或测试索引。

L13～L15 与 Part 11～14 基础补充冒烟：

```bash
.venv/bin/python 5_langgraph_agentic_rag/scripts/smoke_foundations.py
```

它覆盖 Runtime Context/Store、Middleware 生命周期、动态 Model/Tool、调用重试与限制、
摘要与 PII、MCP 子进程协议、并行与 `Send`、子图、异步 Streaming、运行限制和
Functional API 的 interrupt/resume。全部使用 Fake Model 或本地进程，不需要 API Key
和网络。

## 关键输入输出

`graph.invoke(initial_state(...))` 返回完整 State；`public_result()` 提取稳定字段：

| 字段 | 含义 |
| --- | --- |
| `answer` | 最终回答、固定拒答或引用校验失败提示 |
| `answerable` | 是否存在通过 gate 且具有有效引用的知识库回答 |
| `grounded` | 最终回答是否通过本次上下文引用校验 |
| `route` | `direct`、`grounded_answer`、`refused` 等最终路径 |
| `retrieval_attempts` | 实际执行检索的次数 |
| `rewrite_count` | 实际改写问题的次数 |
| `used_evidence_ids` | 真正进入 Prompt 的 chunk IDs |
| `citations` | 根据模型有效引用 ID 从真实证据构建的引用 |
| `retrieval_trace` | 每轮检索的候选、分数和 gate 审计信息 |

## 当前边界

- `offline` 是确定性 Graph 教学模式，不伪装成模型推理。
- `live` 才让聊天模型决定工具调用、判断证据、改写查询和生成答案。
- 本目录已经补齐单 Agent/Graph 的常用基础，但不做多 Agent、Supervisor 或远程 Agent；这些属于下一阶段 Agent Harness 编排。
- SQL 示例是本地教学数据，不连接真实业务数据库。
- 人工确认后的“导出”仍只产生教学预览，不执行外部副作用。
- SQLite checkpointer 用于本地学习；生产 PostgreSQL、连接池和多副本并发不在本目录内。
- FastAPI 是单进程本地适配，不等同于 LangGraph Platform 部署。
- Part 10 是确定性合同评测；LangSmith 在线 tracing、数据集和线上反馈闭环留给后续 Harness 可观测性专题。
