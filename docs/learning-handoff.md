# Andrew 学习交接

> 用途：在不同电脑之间通过 GitHub 同步学习进度。新建 Codex 会话后先阅读本文，再从“下一步”继续。
>
> 最后更新：2026-07-17

## 当前学习主线

- 目录：`3_rag_from_scratch/`
- 当前阶段：Part 2 Indexing 与 chunking 参数对比已完成，下一步对比不同 Embedding 模式。
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
```

已验证结果：Part 1 默认本地资料产生 4 个 chunk，检索返回 2 个 `Document`；`--live` 可以由 `ep-qwen2.5-72b` 正常回答。Part 2 Indexing 退出码为 0，token 示例为 8、向量维度为 384、示例余弦相似度为 `0.706493`，本地资料产生 4 个 chunk 并检索返回 2 条。Part 2 chunking demo 连续运行两次均成功且 JSON 完全一致，五组分别产生 32、34、18、21、10 个 chunk，所有 `start_index` 均有效。

## 下一步

进入 `3_rag_from_scratch/part2_offline_vs_glm_embeddings.py`，按以下顺序学习：

1. 追踪 `local`、`hash`、`glm` 三种模式如何创建 Embeddings 对象。
2. 对比教学哈希向量与本地 MiniLM 的检索结果，理解“词项匹配”和“真实语义向量”的差异。
3. 默认继续使用本地 MiniLM；只有确认远程 `embedding-3` 权限后才运行 `--embedding glm`。
4. Part 2 Embedding 对比完成后进入 Part 3，学习 `k`、score、MMR 与无答案问题。
5. 如果继续优化 chunk 参数，应先扩展为多问题评估集，不再围绕单个问题调参。

## 新电脑继续学习时的启动提示

首次在新电脑运行时，先完成 [新电脑环境搭建](setup-new-machine.md)，验证离线 Part 1 后再使用下面的启动提示。

克隆或更新仓库后，在 Codex 新会话中发送：

```text
先阅读 AGENTS.md 和 docs/learning-handoff.md。
不要重复 Part 1、Part 2 Indexing 和 chunking 已完成内容，从“下一步”开始分析
3_rag_from_scratch/part2_offline_vs_glm_embeddings.py，仍然结合真实代码用中文讲解。
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
