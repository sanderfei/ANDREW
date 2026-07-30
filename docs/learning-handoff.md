# Andrew 学习交接

> 用途：在不同电脑之间通过 GitHub 同步学习进度。新建 Codex 会话后先阅读本文，再从“下一步”继续。
>
> 最后更新：2026-07-30

## 当前学习主线

- 目录：`5_langgraph_agentic_rag/`
- 当前阶段：用户已确认 `3_rag_from_scratch` 全部学完，目录 4 的主体内容已基本学完。目录 5 的 Part 1～10 课件已经按官方 LangGraph 主线完成本地适配并通过测试；目前已经逐行学习 Part 1 的 Graph 基础，下一步进入 Part 2 的受控 Agentic RAG。
- 学习方式：结合仓库中的真实代码，用中文解释运行流程、Python 语法、LangChain 类型和隐藏调用关系。

## 当前运行配置

| 环节 | 目录 3 课件 | 目录 4 知识库服务 |
| --- | --- | --- |
| 文档来源 | `_common.py` 内置 Documents；`--web-source` 才读取网页 | 递归读取 `data/source/` 中的 Markdown/PDF |
| 文本切块 | Part 2 使用 `300/50`；对比实验使用五组 token-aware 参数 | `RecursiveCharacterTextSplitter` 默认字符参数 `800/120`，保留 `start_index` |
| Embedding | 默认本地多语言 MiniLM | `local` MiniLM、教学 `hash`、可选远程 `glm` |
| 向量维度 | 本地 MiniLM 为 384 | 本地 MiniLM 与 Hash 均为 384 |
| 向量库 | `InMemoryVectorStore`，进程退出后消失 | 持久化 Chroma，默认位于 `runtime/chroma` |
| 增量账本 | 无 | `runtime/index_manifest.json` 保存配置指纹、来源 hash 和 chunk IDs |
| Retriever | 默认 `search_type="similarity"`、`k=2` | Chroma cosine 检索，默认 `top_k=4` |
| 回答模式 | 离线抽取或 `--live` 在线生成 | `RAG_MODE=offline/live`，与 Embedding 模式独立 |
| 在线生成模型 | `ep-qwen2.5-72b` | `ep-qwen2.5-72b` |

目录 4 延续同一原则：`RAG_EMBEDDING_MODE=local` 默认使用上述本地 MiniLM，`RAG_MODE=live` 只切换最终回答生成；Hash 仅用于教学/CI，GLM embedding 必须显式选择。

敏感配置只保存在两台电脑各自的根目录 `.env` 中；`.env` 已被 Git 忽略。本文和 Git 提交中不得出现任何 API Key 或 Token。

## 目录 5 Part 1 已掌握

### State、Node 与状态更新

- `LearningState(TypedDict, total=False)` 描述整张图可使用的状态字段；运行时 State 仍是普通 `dict`。`total=False` 允许初始状态只提供部分字段，但节点通过 `state["字段"]` 直接访问时，该字段在运行到节点前必须存在。
- Node 接收当前 State，只返回需要更新的部分字段。LangGraph 把节点返回值合并回图状态，因此节点不需要复制整个 State。
- Part 1 没有配置 Reducer，`steps` 通过 `[*state.get("steps", []), "节点名"]` 手动创建新列表并保留历史；后续 Part 5 再学习 Reducer 的自动合并语义。
- `graph.invoke({"question": "你好"})` 可以省略 `steps`，因为节点使用 `state.get("steps", [])` 从空列表开始；`question` 不能省略，因为分类节点使用 `state["question"]`，缺少时会触发 `KeyError`。

### Node 注册、固定边和条件边

- `workflow.add_node("节点名称", Python函数)` 把 LangGraph 节点名称注册到真正执行的 callable；条件边映射右侧填写的是已注册节点名称，不是直接调用函数。
- 条件边目标节点必须在 `workflow.compile()` 之前完成注册，但不强制在 `add_conditional_edges()` 之前注册；先注册全部节点再添加边更容易阅读。
- `workflow.add_edge(START, "classify_question")` 设置固定入口；`add_conditional_edges("classify_question", choose_route, mapping)` 在分类节点完成后，根据路由函数返回值选择目标节点。
- `add_edge()` 与 `add_conditional_edges()` 的代码书写顺序不决定运行顺序，真正顺序由图中 `START → 源节点 → 目标节点 → END` 的连接关系决定。

### compile 与 invoke

- `StateGraph` 是图的定义或设计稿；`workflow.compile()` 检查连接关系并返回可运行的 `CompiledStateGraph`。
- `add_node()`、`add_edge()` 和 `add_conditional_edges()` 只描述图，调用 `graph.invoke(initial_state)` 时才真正从 `START` 执行节点。
- 当前 Part 1 没有 Checkpointer，两次 `invoke()` 是相互独立的执行，不会自动继承上一次 State。
- 根目录新增 `LangGraph基础语法笔记.md`，后续学习到新的 LangGraph API 和运行机制时继续去重补充。

## 目录 3 Part 1 已掌握

### RAG 主流程

```text
Document
  -> split_documents
list[Document chunk]
  -> embed_documents
list[384 维向量]
  -> InMemoryVectorStore
  -> retriever.invoke(question)
list[Document]
  -> format_documents
context 字符串
  -> Prompt(context + question)
  -> 在线 Qwen 或离线抽取器
  -> StrOutputParser
str 答案
```

### `build_rag_chain` 的真实含义

`build_rag_chain()` 先构造 LCEL 管道，调用 `.invoke(question)` 时才真正执行：

```text
同一个 question
  |- retriever -> list[Document] -> format_documents -> context
  `- RunnablePassthrough -> 原始 question

context + question -> Prompt -> Model -> str
```

模型看不到向量、相似度计算过程或完整向量库，只能看到被检索出来的 `Document.page_content` 和原始问题。

### 已确认的代码细节

- `Document` 主要包含 `page_content` 和 `metadata`。
- `WebBaseLoader` 当前只有一个网址，通常返回一个合并后的 `Document`；`class_=(...)` 是过滤 HTML 区域，不是每个 class 生成一个 `Document`。
- `split_documents()` 返回 `list[Document]`；`Iterable[Document]` 表示入参只要求可遍历。
- `Sequence[Document]` 表示有顺序且可按下标访问，常见实现包括 `list` 和 `tuple`。
- `tuple` 是有序、创建后不能增删或替换元素的元组。
- 函数签名中的 `*` 表示后续参数必须使用 `参数名=值` 传递。
- `Embeddings | None` 是联合类型；`= None` 是默认值，因此既可以省略，也可以显式传 `None`。
- `InMemoryVectorStore.from_documents(..., embedding=active_embeddings)` 中的 `embedding` 是负责文本转向量的对象，不是布尔值。
- `search_type="similarity"` 使用普通相似度检索，不是 MMR。
- MMR 中 `fetch_k` 是第一阶段候选数量，`k` 是最终返回数量，`lambda_mult` 控制相关性和多样性的权重。
- Part 1 为了同时打印检索结果并演示完整 Chain，当前会执行两次 `retriever.invoke()`：一次显式检索，一次在 Chain 内部检索。

### 已理解的 Python 语法

- `argparse.ArgumentParser`：解析命令行参数。
- `os.environ.setdefault(...)`：环境变量不存在时才设置默认值；网页加载时用它设置 HTTP `USER_AGENT`。
- `@dataclass(frozen=True)`：自动生成初始化等方法，并禁止实例创建后修改字段。
- `list` 可修改；`tuple` 不可修改。
- 类型注解描述允许的值，不等于运行时赋值；例如 `Embeddings | None` 与 `= None` 分别承担不同作用。

## 目录 3 Part 2 已掌握

### Indexing 与 Embedding 调用关系

```text
原始 Document
  -> split_documents / split_documents_token_aware
list[Document chunk]
  -> embed_documents(list[str])
list[list[float]]
  -> InMemoryVectorStore 保存文本、metadata 与向量

question
  -> embed_query(str)
list[float]
  -> 与 chunk 向量计算余弦相似度
  -> 降序返回 top-k Document
```

- 本地 MiniLM 为每段文本生成一个 384 维向量；单个维度没有可直接阅读的固定语义。
- `InMemoryVectorStore.from_documents(...)` 在写入时调用 `embed_documents()`；`similarity_search...` 在查询时调用 `embed_query()`。
- `score` 是余弦相似度，不是正确概率；不能只用最高分判断切块参数好坏。
- `cl100k_base` 在当前实验中负责切块与 token 统计；MiniLM 生成向量时使用自己的 tokenizer，两者不能视为同一套精确 token 数。
- `start_index` 是 chunk 在原文中的字符位置，不是 token 下标。

### Chunking 参数对比

- 实验文档已扩展为 1773 个 `cl100k_base` token、8 个自然段，包含明确答案、边界例子、相关背景和干扰内容，避免短文下 `k=2` 几乎召回全文。
- 五组参数按控制变量排列：`80/0` 对比 `80/10`、`140/0` 对比 `140/30`，`260/60` 用于观察大 chunk 的上下文成本。
- `80/0` 的 Top-1 在“并提高”处截断；`80/10` 保留了“提高完整证据进入 top-k 的概率”这一完整结论，两组 Top-2 都是 131 token。
- `140/30` 比 `140/0` 保留了更多因果桥接文本，但 Top-2 从 192 增加到 228 token；`260/60` 的 Top-1 分数最高，但 Top-2 达到 357 token。
- 配置 `chunk_overlap=N` 不代表每对相邻 chunk 一定精确重复 N 个 token。实测 `80/10` 有 26 对真实重叠、最大 10 token；`140/30` 有 13 对、最大 30 token；`260/60` 只有 2 对、最大 55 token，因为递归分隔器会优先保留自然段边界。
- 当前单问题下，`80/10` 的完整性与检索 token 成本最平衡；这不是所有文档的通用最优值，生产参数仍需多问题评估集验证。

### Embedding 模式对比

- `StableHashEmbeddings` 是可复现的离线教学基线：中文按相邻双字词项切分，再稳定哈希到 384 个槽位；它不理解真实语义，并可能发生哈希槽碰撞。
- 本次 Hash 对照中，问题与正确文档没有直接词项重合，`0.042258` 来自“如何”和“在分”落入同一槽位；正确文档排第一属于可重复的语义偶然，不能当作模型理解。
- 本地多语言 MiniLM 能把“切块边界/语义丢失”与“分段交界/完整概念被拆散”识别为相近表达，适合作为当前默认 Embedding。
- Hash 向量范数为 `1.0` 是代码主动归一化的结果；MiniLM 范数不同不代表质量更高或更低。不同模型的绝对 score 不能按倍数直接比较，切换模型后必须重建全部文档向量。
- `embed_documents()` 用于写入文档，返回 `list[list[float]]`；`embed_query()` 用于查询，返回单个 `list[float]`。
- Python 调用处的 `**config` 会把字典展开成关键字参数；函数定义中的单个 `*` 表示后续参数只能按名称传递。`enumerate(matches, start=1)` 为结果添加从 1 开始的序号，并可与 `(document, score)` 同时解包。

## 目录 3 Part 3 已掌握

### Retriever API 与批量调用

- 学习顺序已明确为 `part3_1_retrieval.py`、`part3_2_retrieval_k_score_mmr_no_answer.py`。
- `vector_store.as_retriever(...)` 只是把 VectorStore 包装成符合 Runnable 接口的 `VectorStoreRetriever`，没有引入第二套检索算法。
- `retriever.invoke(question)` 内部根据 `search_type` 调度到 `vector_store.similarity_search(...)`；真正流程仍是 `embed_query -> 相似度排序 -> top-k Document`。
- `retriever.batch([q1, q2])` 逻辑上相当于对多个输入分别调用 `invoke()`；默认 Runnable 实现可使用线程池并发，返回值为 `list[list[Document]]`。
- `zip(questions, batch_documents)` 只负责把第 i 个问题与第 i 组结果重新配对，便于生成 JSON，不参与 Embedding 或检索。
- `build_retriever(vector_store, k=3)` 可以省略其他参数，是因为 `search_type`、`fetch_k`、`lambda_mult` 都有默认值；函数签名中的 `*` 要求这些参数按名称传递。

### k、score、MMR 与无答案问题

- `k` 只控制截取多少个候选，不改变已有候选的相似度分数；过小可能漏证据，过大会增加噪声和 Prompt token。
- `similarity` 只按问题相关性排序；MMR 先取 `fetch_k` 个候选，再用 `lambda_mult` 平衡问题相关性和结果多样性，最终返回 `k` 个。
- 当前六文档实验中，`lambda_mult=0.5` 的 MMR 把无关的 Docker 文档选入 Top-3，说明多样性不是准确性的保证；实际使用应先做相关性 gate，或重新标定候选池与权重。
- `similarity_search_with_score()` 返回 `(Document, score)`；当前本地 InMemoryVectorStore 的 score 是余弦相似度，不是答案概率。
- Top-k 即使面对知识库无法回答的问题也会返回候选；`accepted = score >= threshold` 和 `answerable` 是本地程序增加的 gate，不是 Retriever 自动理解“有没有答案”。

## 目录 3 Part 4 已掌握

### Generation 与固定两步 RAG

- 学习顺序已明确为 `part4_1_generation.py`、`part4_2_answer_with_citations.py`，应先理解基础生成链，再学习 citation 闭环。
- `format_documents()` 把 `list[Document]` 转成可注入 Prompt 的 context 字符串；模型看不到向量、完整向量库或未被接受的文档。
- `prompt | model | StrOutputParser()` 是 LCEL 管道：Prompt 生成消息，Chat Model 返回消息，解析器最终得到 `str`。
- 完整固定两步 RAG 使用同一个 question 分成两路：`retriever | format_documents` 生成 context，`RunnablePassthrough()` 保留原始 question，然后一起进入 Prompt。
- 组合 Chain 时只是在定义流水线，调用 `.invoke(...)` 才真正执行。教学脚本同时演示手动链和完整 Chain，因此会重复检索并生成两次；生产代码通常只保留一种。
- 默认模式使用离线抽取 Runnable；`--live` 只把生成阶段切换到在线 `ep-qwen2.5-72b`，默认 Embedding 仍是本地 MiniLM。

### Answer、拒答与 citation 数据契约

- `candidates` 是 Top-k 全部候选；`accepted` 是通过 score 阈值的 `(Document, score)` 子集；`retrieval` 保留全部候选并标记 `accepted=true/false`；`citations` 只从 accepted 构建。
- 列表推导式末尾的 `if score >= min_score` 才会过滤；字典中的 `"accepted": score >= min_score` 只是写入布尔字段，不会过滤元素。
- 没有 accepted 文档时，代码在调用 Chat Model 前直接返回固定拒答、`answerable=false`、`citations=[]`，但仍保留 retrieval 供调试和审计。
- 有答案时，生成模型的 context 与 citations 来自同一批 accepted Documents；citation 的 `source/page/start_index/score/excerpt` 由本地程序从真实 Document 构建，模型无权自由编造来源。
- 当前 citation 是文档级来源追踪：能保证来源进入过 context，但不能证明模型实际使用了每一篇，也没有实现答案句子到证据片段的一一绑定。
- `RAG_TEMPLATE` 明确要求只依据 context 回答，这会降低越界生成；当前代码没有生成后忠实性验证，因此 Prompt 约束不是程序层面的绝对保证。
- 本地 citation 示例中的 `citations.md`、`grounding.md`、`answerability.md` 是手写 metadata 标签，不是仓库中的真实文件；生产实现还需要真实 URI、document/chunk ID、页码与版本信息。

## 目录 4 第 5 周已掌握

### 配置、来源加载与 Embedding

- `Settings.from_env()` 统一解析回答模式、Embedding 模式、来源/运行目录、Chroma collection、切块参数、召回阈值和模型配置；类型标注用于说明约定，不会自动创建或强制转换对象。
- `RAG_MODE=offline/live` 只控制最终回答；`RAG_EMBEDDING_MODE=local/hash/glm` 独立控制建库和查询向量，切换 Embedding 后需要重建索引。
- `load_sources()` 先完整读取所有支持的来源再返回：非空 Markdown 文件产生一个原始 `Document`，PDF 按有可提取文本的页面产生 Documents；`source` 使用相对 POSIX 路径，文件字节 SHA-256 用于增量比较。
- `lexical_tokens()` 同时提取英文技术词项和中文相邻双字词；`grounding_tokens()` 去除高频停用词；`technical_tokens()` 识别 API 名和英文术语。`min_relevance_score` 是综合得分门槛，`min_lexical_overlap` 是问题有效词项被候选覆盖的比例门槛。

### Chroma、manifest 与增量索引

- 一个 Chroma 记录对应一个切分后的 `Document` chunk，保存稳定 ID、原文、metadata 和 Embedding；collection 是 Chroma 内部的一组逻辑记录。
- `ChunkedSource` 保存一个来源切块后的 Documents 与 chunk IDs；`IncrementalIndexer` 负责切块、比较、增删、manifest 更新和搜索；`IndexStats` 只是一次 `reindex()` 的统计报告。
- `index_manifest.json` 是项目维护的控制账本，Chroma 是实际向量数据仓库；两者通过相同 `chunk_id` 对应，必须作为一组持久化状态维护。
- `index_fingerprint` 只覆盖 `chunk_size`、`chunk_overlap`、Embedding 身份和 collection 名称，不是全部来源内容的总指纹；各来源内容变化由 `sources[name]["sha256"]` 单独判断。
- `manifest_matches_config()` 在 `sources` 为空时视为兼容；已有来源时比较旧 fingerprint 与当前动态计算值。配置不兼容时 `ensure_compatible_manifest()` 抛出 `IndexConflictError`，要求 `reindex --reset`。
- `_write_manifest()` 使用 `mkstemp -> json.dump -> with 关闭文件 -> os.replace` 原子替换正式 manifest；`finally` 中的 `unlink` 只清理失败后残留的临时文件，不负责关闭文件锁。
- `_batched()` 用 `range(0, len(values), size)` 和列表切片逐批 `yield`；本身返回生成器，每次产生一个小列表。`_delete_ids()` 与 `_add_source_chunks()` 默认最多按 100 条一批操作 Chroma。
- `reindex()` 先得到当前 `loaded_sources` 和 `chunked_sources`，再与旧 manifest 的 `old_sources` 比较，识别新增、更新、未变化和删除来源；随后删除旧 Chroma chunk、写入变化后的新 chunk、原子写入完整新 manifest，最后返回 `IndexStats`。未变化来源不会重复生成 Embedding。

### 本阶段补充的 Python 基础

- 已区分 `set.difference()`、不可修改的 `frozenset`、`re.Pattern.findall()`、字典推导式和 dataclass `asdict()`。
- 已掌握 `mkstemp()` 返回的文件描述符与临时路径、`os.fdopen()`、`with` 自动关闭、`json.dump()` 与 `json.dumps()`、`os.replace()` 和 `os.unlink()` 的职责。
- 已区分 `Iterable`、`Sequence`、`list`、生成器和 `range`：`for`/`in` 才是循环关键字，`range(...)` 返回不可修改的 `range` Sequence。
- Python 参数允许省略类型标注；参数名没有固定类型，但传入对象始终有实际运行时类型。当前未标注的 `store` 实际由 `_store()` 返回 Chroma 对象。

## 目录 4 第 6 周与第 7 周评测已掌握

### contracts、候选筛选与回答流程

- `contracts.py` 中的 Pydantic 模型定义 API/CLI 共用的数据契约：`AskRequest` 校验问题和 `top_k`，`AskResponse` 汇总答案、可回答性、citations 与 retrieval trace，`ReindexResponse` 和 `HealthResponse` 分别描述索引变更与健康状态。
- `KnowledgeBaseService.ask()` 先确认索引兼容，再提取问题词项并执行 Chroma Top-K 检索。`candidates` 保存完成分数计算但尚未过滤的全部候选，`matches` 保存全部候选的审计记录，`accepted_pairs` 只保存通过 gate 的候选。
- `lexical_overlap = |问题词项 ∩ 文档词项| / |问题词项|`；`relevance_score = 0.25 * vector_score + 0.75 * lexical_overlap` 是项目自定义综合分数，不是正确概率。
- `technical_tokens()` 只提取英文/ASCII 技术标识。纯中文问题通常得到空集合，虽然单条候选的 `technical_match` 为 `False`，但最终 `not query_technical_tokens or technical_match` 为 `True`，因此不会阻止中文问题继续通过向量和词面条件筛选。
- 没有 `accepted_pairs` 时，服务在创建聊天模型前直接返回固定拒答。通过 gate 后先按 `relevance_score` 降序；offline 返回原文摘录，live 才把上下文交给在线聊天模型。
- `with self._lock` 使用进程内 `threading.RLock` 串行化 ask/reindex。同一进程中 A 持锁时，B 默认在进入 `with` 处持续等待，直到 A 释放锁；当前没有配置获取锁的超时时间。该锁不跨 Uvicorn 多进程或多台机器。

### citation 边界与推荐生产设计

- 当前目录 4 的 citations 从 `accepted_pairs` 前三条构建，offline 答案取前两条 quote，live context 则按 `max_context_chars` 从 `accepted_pairs` 依次加入，因此三组证据不保证严格相等；这是学习型文档级来源追踪。
- `StrOutputParser()` 只返回答案字符串，程序只能知道哪些 chunk 进入过 context，不能确认模型实际使用了哪些。推荐生产设计是先确定 `used_evidence`，在 Prompt 中携带稳定 `chunk_id`，让模型结构化返回 `answer + cited_chunk_ids`，再由程序校验这些 ID 是本次 context IDs 的子集。
- Citation 的 `source`、`quote`、score 等字段仍应由程序根据校验后的真实 `Document` 构建，不能直接信任模型自由生成的来源信息。若需要句子级归因，应进一步返回 claim 与 chunk IDs 的映射。

### evaluate.py 与启动入口

- `evaluate.py` 在临时目录复制来源、建立独立 Chroma、运行 20 条黄金样本，再通过修改和删除临时文档验证增量索引与 manifest 清理，不污染主运行目录。
- 默认评估组合为 `--embedding local --mode live`：本地 MiniLM 负责建库和查询向量，通过 gate 的问题调用在线模型；CI 显式使用 `--embedding hash --mode offline`。
- live 答案可能把 `manifest` 改写成“清单”等同义表达，因此关键术语必须存在于 citation 证据中；答案未逐字复述时记录 warning。offline 摘录仍执行逐字确定性断言。
- 目录 3 的 10 个课件入口及目录 4 的 `app.py`、`cli.py`、`evaluate.py` 已在 `main()` 上方补充可复制启动命令。目录 3 实际参数名为 `--live --embedding local`，目录 4 为 `--mode live --embedding local`。
- Part 2/Part 3 课件没有聊天生成阶段，`--live` 只由公共参数解析器接收，不会触发 LLM；Generation、citation、Multi Query 与 RRF 等包含生成或改写阶段的课件才会调用聊天模型。

## 目录 3 完成状态

- 用户已确认 `3_rag_from_scratch` 的后续 Multi Query 与 Reciprocal Rank Fusion / reranking 学习也已完成，目录 3 不再作为下一步。
- 目录 4 不反向修改目录 3 的课件，而是把已掌握的 indexing、retrieval、answerability、generation 和 citation 契约工程化为持久化知识库服务。
- 目录 4 已按 `loaders.py` → `embeddings.py` → `indexer.py` → `contracts.py` → `kb_service.py` → `app.py` / `cli.py` → `evaluate.py` 学习；尚未逐行学习 `scripts/smoke.py`。

## 已验证命令

在仓库根目录运行：

```bash
# 本地 MiniLM 检索 + 离线抽取式回答，不需要在线聊天模型
.venv/bin/python 3_rag_from_scratch/part1_overview.py

# 本地 MiniLM 检索 + 在线 ep-qwen2.5-72b 回答
.venv/bin/python 3_rag_from_scratch/part1_overview.py --live --embedding local

# Part 2：Embedding、余弦相似度、切块与入库
.venv/bin/python 3_rag_from_scratch/part2_indexing.py

# Part 2：五组 token-aware chunk 参数对比
.venv/bin/python 3_rag_from_scratch/part2_chunking_parameter_comparison.py

# Part 2：Hash 教学基线、本地 MiniLM 与可选 GLM Embedding 对比
.venv/bin/python 3_rag_from_scratch/part2_offline_vs_glm_embeddings.py

# Part 3-1：Retriever invoke 与 batch
.venv/bin/python 3_rag_from_scratch/part3_1_retrieval.py

# Part 3-2：k、score、MMR 与无答案问题
.venv/bin/python 3_rag_from_scratch/part3_2_retrieval_k_score_mmr_no_answer.py

# Part 4-1：context、Prompt、Model、Parser 与固定两步 RAG
.venv/bin/python 3_rag_from_scratch/part4_1_generation.py

# Part 4-2：回答、拒答、citations 与 retrieval 审计
.venv/bin/python 3_rag_from_scratch/part4_2_answer_with_citations.py

# Part 4-2：本地 MiniLM 检索 + 在线 ep-qwen2.5-72b 生成
.venv/bin/python 3_rag_from_scratch/part4_2_answer_with_citations.py --live --embedding local

# 目录 4：用本地 MiniLM 完整重建持久化 Chroma 索引
.venv/bin/python 4_rag_knowledge_base_service/cli.py --mode live --embedding local reindex --reset

# 目录 4：健康检查与本地 MiniLM 检索、在线回答
.venv/bin/python 4_rag_knowledge_base_service/cli.py --mode live --embedding local health
.venv/bin/python 4_rag_knowledge_base_service/cli.py --mode live --embedding local ask "本机默认 embedding 使用什么模型，向量维度是多少？"

# 目录 4：本机 MiniLM 检索 + 在线回答，以及无需模型下载/API 的 Hash 离线回归
.venv/bin/python 4_rag_knowledge_base_service/evaluate.py --embedding local --mode live
.venv/bin/python 4_rag_knowledge_base_service/evaluate.py --embedding hash --mode offline

# 目录 4：FastAPI 端到端冒烟
.venv/bin/python 4_rag_knowledge_base_service/scripts/smoke.py

# 目录 5：Part 1～4 原有冒烟
.venv/bin/python 5_langgraph_agentic_rag/scripts/smoke.py

# 目录 5：单独运行 Part 1 Graph 基础
.venv/bin/python 5_langgraph_agentic_rag/part1_graph_basics.py

# 目录 5：Part 5～10 高级冒烟
.venv/bin/python 5_langgraph_agentic_rag/scripts/smoke_advanced.py

# 目录 3、目录 4、目录 5 Python 文件编译检查
.venv/bin/python -m compileall -q \
  3_rag_from_scratch \
  4_rag_knowledge_base_service \
  5_langgraph_agentic_rag

# 提交前检查补丁格式
git diff --check
```

已验证结果：Part 1 默认本地资料产生 4 个 chunk，检索返回 2 个 `Document`；`--live` 可以由 `ep-qwen2.5-72b` 正常回答。Part 2 Indexing 退出码为 0，token 示例为 8、向量维度为 384、示例余弦相似度为 `0.706493`，本地资料产生 4 个 chunk 并检索返回 2 条。Part 2 chunking demo 连续运行两次均成功且 JSON 完全一致，五组分别产生 32、34、18、21、10 个 chunk，所有 `start_index` 均有效。Part 3-1、Part 3-2、Part 4-1、Part 4-2 使用重命名后的入口以默认本地模式运行，退出码均为 0。Part 4-2 在线模式由 `ep-qwen2.5-72b` 正常回答 citation 问题；天气问题的三个候选全部低于 `0.2`，在生成前返回 `answerable=false` 和空 citations，未调用在线模型。目录 4 已用本地 MiniLM 重建 5 个来源/5 个 chunk；重复 reindex 显示 5 个文件全部 unchanged、写入和删除均为 0；已知问题引用 `local_runtime.md`，天气问题正确拒答。2026-07-28 再次验证 Hash + offline 黄金集 `20/20`、FastAPI smoke 的 health/reindex/ask/refusal/update/delete 全部通过；local + live 黄金集也为 `20/20`，其中 4 条仅因模型同义改写产生 warning，在线回答仍保持 `embedding_mode=local`。目录 3 的 10 个入口以及目录 4 评估/CLI 参数帮助检查全部通过，两个目录全量编译和 `git diff --check` 通过。2026-07-29 验证目录 5 的原有冒烟和高级冒烟均通过：Part 5～10 覆盖 Reducer/Streaming、重试与补偿、SQLite 恢复/replay/fork、受控 RAG+SQL+HITL、同 thread 多轮状态、FastAPI/SSE，以及 6 个评测用例、31 项合同检查；Part 1～4 文件哈希保持不变。2026-07-30 单独运行目录 5 Part 1 成功，`smalltalk` 与 `knowledge` 两条条件分支输出正确；最小输入只传 `question` 时会自动生成完整 `steps`。本次提交前再次验证目录 5 基础冒烟和高级冒烟均通过，高级冒烟保持 6 个评测用例、31 项合同检查全部通过；目录 5 全量编译、Markdown 代码块/相对链接、敏感信息扫描和 `git diff --check` 均通过。

## 下一步

继续逐课学习 `5_langgraph_agentic_rag`，不重复目录 3 和目录 4 已掌握的 RAG 基础，也不要因为代码已通过测试就把尚未讲解的章节标记为已学会：

1. Part 1 的 State、Node、Edge、条件边、`compile()` 和 `invoke()` 已学习完成。
2. 下一步学习 `part2_agentic_rag.py`，重点追踪消息类型、ToolNode、检索 artifact、证据判断、改写回边和引用校验。
3. 学习 Part 3～4 的 `thread_id`、interrupt/resume、Tool Schema 与 SQL 三层只读边界。
4. 学习 Part 5～7 的 Reducer、v2 Streaming、RetryPolicy/error_handler、SQLite checkpoint、历史、replay 和 fork。
5. 学习 Part 8～10 的受控多工具图、同 thread 多轮状态、FastAPI/SSE/恢复接口与确定性合同评测。
6. 目录 5 学完后再进入独立的 LangSmith tracing/实验记录；多 Agent 不属于当前路线。目录 4 尚未处理的 Docker / CI 一致性留到第 11 周上线工程化阶段。

## 新电脑继续学习时的启动提示

首次在新电脑运行时，先完成 [新电脑环境搭建](setup-new-machine.md)，验证离线 Part 1 后再使用下面的启动提示。

克隆或更新仓库后，在 Codex 新会话中发送：

```text
先阅读 AGENTS.md 和 docs/learning-handoff.md。
不要重复 3_rag_from_scratch 和目录 4 已掌握的内容。
目录 5 代码已经通过测试，Part 1 已学习完成；从“下一步”的 Part 2 开始。
先分析，不要修改代码。
```

## 每次学习结束时的交接清单

1. 更新“当前阶段”和“下一步”。
2. 只记录真正验证过的命令与结果。
3. 记录新的关键概念和容易混淆点，删除已经失效的结论。
4. 检查文档中没有 API Key、Token、`.env` 内容和原始会话文本。
5. 查看 `git diff`，确认后再由用户提交并推送到 GitHub。

## 跨机器边界

- GitHub 同步：代码、`AGENTS.md`、本交接文档以及根目录的 Python、LangChain、LangGraph 基础语法笔记。
- 每台机器单独配置：`.env`、Python 虚拟环境、本地模型缓存、Codex 插件和账号授权；具体步骤见 [新电脑环境搭建](setup-new-machine.md)。
- 不同步到 Git：`~/.codex/sessions/`、`~/.codex/memories/`、`auth.json`、原始聊天记录。
