# Andrew 学习交接

> 用途：在不同电脑之间通过 GitHub 同步学习进度。新建 Codex 会话后先阅读本文，再从“下一步”继续。
>
> 最后更新：2026-07-22

## 当前学习主线

- 目录：`4_rag_knowledge_base_service/`
- 当前阶段：用户已确认 `3_rag_from_scratch` 全部学完；目录 4 的本地适配代码和运行环境已准备并验证，下一步从第 5 周“摄取与持久化”开始逐文件学习。
- 学习方式：结合仓库中的真实代码，用中文解释运行流程、Python 语法、LangChain 类型和隐藏调用关系。

## 当前运行配置

| 环节 | 当前实现 |
| --- | --- |
| 文档来源 | 主课件默认使用 `_common.py` 内置的 4 个 `Document`；chunking 对比使用内置的 1773-token 长文；`--web-source` 才读取网页 |
| 文本切块 | `RecursiveCharacterTextSplitter`；Part 2 Indexing 使用 `300/50`，chunking 对比使用 token-aware 的 `80/0`、`80/10`、`140/0`、`140/30`、`260/60` |
| Embedding | 本地 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| 向量维度 | 384 |
| 向量库 | `InMemoryVectorStore`，进程退出后数据消失 |
| Retriever | 默认 `search_type="similarity"`、`k=2` |
| 在线生成模型 | `ep-qwen2.5-72b` |
| `--live` 的作用 | 只切换在线回答/查询改写，不改变默认本地 Embedding |

目录 4 延续同一原则：`RAG_EMBEDDING_MODE=local` 默认使用上述本地 MiniLM，`RAG_MODE=live` 只切换最终回答生成；Hash 仅用于教学/CI，GLM embedding 必须显式选择。

敏感配置只保存在两台电脑各自的根目录 `.env` 中；`.env` 已被 Git 忽略。本文和 Git 提交中不得出现任何 API Key 或 Token。

## Part 1 已掌握

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

## Part 2 已掌握

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

## Part 3 已掌握

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

## Part 4 已掌握

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

## 目录 3 完成状态

- 用户已确认 `3_rag_from_scratch` 的后续 Multi Query 与 Reciprocal Rank Fusion / reranking 学习也已完成，目录 3 不再作为下一步。
- 目录 4 不反向修改目录 3 的课件，而是把已掌握的 indexing、retrieval、answerability、generation 和 citation 契约工程化为持久化知识库服务。
- 目录 4 的建议顺序是：`loaders.py` → `embeddings.py` → `indexer.py` → `contracts.py` → `kb_service.py` → `app.py` / `cli.py` → `evaluate.py` / `scripts/smoke.py`。

## 已验证命令

在仓库根目录运行：

```bash
# 本地 MiniLM 检索 + 离线抽取式回答，不需要在线聊天模型
.venv/bin/python 3_rag_from_scratch/part1_overview.py

# 本地 MiniLM 检索 + 在线 ep-qwen2.5-72b 回答
.venv/bin/python 3_rag_from_scratch/part1_overview.py --live

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
.venv/bin/python 3_rag_from_scratch/part4_2_answer_with_citations.py --live

# 目录 4：用本地 MiniLM 完整重建持久化 Chroma 索引
.venv/bin/python 4_rag_knowledge_base_service/cli.py reindex --reset

# 目录 4：健康检查与离线问答
.venv/bin/python 4_rag_knowledge_base_service/cli.py health
.venv/bin/python 4_rag_knowledge_base_service/cli.py ask "本机默认 embedding 使用什么模型，向量维度是多少？"

# 目录 4：本机 MiniLM 黄金集与无需模型下载的 Hash 回归
.venv/bin/python 4_rag_knowledge_base_service/evaluate.py --embedding local
.venv/bin/python 4_rag_knowledge_base_service/evaluate.py --embedding hash

# 目录 4：FastAPI 端到端冒烟
.venv/bin/python 4_rag_knowledge_base_service/scripts/smoke.py
```

已验证结果：Part 1 默认本地资料产生 4 个 chunk，检索返回 2 个 `Document`；`--live` 可以由 `ep-qwen2.5-72b` 正常回答。Part 2 Indexing 退出码为 0，token 示例为 8、向量维度为 384、示例余弦相似度为 `0.706493`，本地资料产生 4 个 chunk 并检索返回 2 条。Part 2 chunking demo 连续运行两次均成功且 JSON 完全一致，五组分别产生 32、34、18、21、10 个 chunk，所有 `start_index` 均有效。Part 3-1、Part 3-2、Part 4-1、Part 4-2 使用重命名后的入口以默认本地模式运行，退出码均为 0。Part 4-2 在线模式由 `ep-qwen2.5-72b` 正常回答 citation 问题；天气问题的三个候选全部低于 `0.2`，在生成前返回 `answerable=false` 和空 citations，未调用在线模型。目录 4 已用本地 MiniLM 重建 5 个来源/5 个 chunk；重复 reindex 显示 5 个文件全部 unchanged、写入和删除均为 0；已知问题引用 `local_runtime.md`，天气问题正确拒答；MiniLM 与 Hash 两套 20 条黄金集均为 20/20，FastAPI smoke 通过，在线 Qwen 回答仍保持 `embedding_mode=local`。

## 下一步

进入 `4_rag_knowledge_base_service` 第 5 周“摄取与持久化”，按以下顺序学习：

1. 先运行 `cli.py reindex --reset`，对照输出理解 source、Document、chunk、chunk ID、向量和 manifest 的数量关系。
2. 阅读 `loaders.py`，追踪 Markdown/PDF 如何产生 `Document`，以及 `source`、`source_type`、`page`、`source_sha256` metadata 从哪里来。
3. 阅读 `embeddings.py`，对比 local MiniLM、Hash 与 GLM 三种 backend，明确 `RAG_MODE` 不控制 embedding。
4. 阅读 `indexer.py`，追踪 `load_sources -> split_documents -> add_documents -> manifest`，再实际修改一份临时学习文档观察 added / updated / unchanged / removed。
5. 完成摄取与增量索引后，再进入 `contracts.py` 与 `kb_service.py` 学习 API 问答服务，不提前跳到 Agent/LangGraph。

## 新电脑继续学习时的启动提示

首次在新电脑运行时，先完成 [新电脑环境搭建](setup-new-machine.md)，验证离线 Part 1 后再使用下面的启动提示。

克隆或更新仓库后，在 Codex 新会话中发送：

```text
先阅读 AGENTS.md 和 docs/learning-handoff.md。
不要重复 3_rag_from_scratch 已完成内容，从“下一步”开始分析
4_rag_knowledge_base_service/loaders.py，仍然结合真实代码用中文讲解。
先分析，不要修改代码。
```

## 每次学习结束时的交接清单

1. 更新“当前阶段”和“下一步”。
2. 只记录真正验证过的命令与结果。
3. 记录新的关键概念和容易混淆点，删除已经失效的结论。
4. 检查文档中没有 API Key、Token、`.env` 内容和原始会话文本。
5. 查看 `git diff`，确认后再由用户提交并推送到 GitHub。

## 跨机器边界

- GitHub 同步：代码、`AGENTS.md`、本交接文档。
- 每台机器单独配置：`.env`、Python 虚拟环境、本地模型缓存、Codex 插件和账号授权；具体步骤见 [新电脑环境搭建](setup-new-machine.md)。
- 不同步到 Git：`~/.codex/sessions/`、`~/.codex/memories/`、`auth.json`、原始聊天记录。
