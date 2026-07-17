# RAG From Scratch（Part 1–5 + Part 15 + 检索实验）

这个目录先把官方 RAG From Scratch Part 1–4 拆成可直接运行的 Python 课件，再补入求职中必须能讲清的切块参数、score、MMR、拒答、citation、Multi Query 和 RRF 重排序。

旧 LangChain API 已更新为当前 1.x 写法。Embedding 默认使用本机 CPU 运行的多语言 MiniLM；回答生成默认是可复现的离线抽取，只有显式传入 `--live` 才在生成阶段调用在线聊天模型。

## 学习顺序

| 顺序 | 文件 | 官方对应 / 学习重点 |
| --- | --- | --- |
| 1 | [part1_overview.py](part1_overview.py) | Part 1：`Document -> indexing -> retrieval -> generation` |
| 2 | [part2_indexing.py](part2_indexing.py) | Part 2：token、`embed_query`、`embed_documents`、余弦相似度、切块与入库 |
| 3 | [part2_chunking_parameter_comparison.py](part2_chunking_parameter_comparison.py) | Part 2 求职扩展：五组 token-aware chunk 参数对比 |
| 4 | [part2_offline_vs_glm_embeddings.py](part2_offline_vs_glm_embeddings.py) | Part 2：哈希词项基线 vs 本地 MiniLM，可选对比 `embedding-3` |
| 5 | [part3_retrieval.py](part3_retrieval.py) | Part 3：`retriever.invoke(...)` 与 `batch(...)` |
| 6 | [part3_retrieval_k_score_mmr_no_answer.py](part3_retrieval_k_score_mmr_no_answer.py) | Part 3 求职扩展：`k` / score / MMR / 无答案问题 |
| 7 | [part4_generation.py](part4_generation.py) | Part 4：`prompt | model | StrOutputParser` 与固定两步 RAG |
| 8 | [part4_answer_with_citations.py](part4_answer_with_citations.py) | Part 4 求职扩展：`answer + answerable + citations + retrieval` |
| 9 | [part5_multi_query.py](part5_multi_query.py) | Part 5：生成多个查询，分别检索并保序去重；`--live` 可用在线模型改写 |
| 10 | [part15_reciprocal_rank_fusion_reranking.py](part15_reciprocal_rank_fusion_reranking.py) | Part 15：对多个排名执行 Reciprocal Rank Fusion |

Part 3 的 score、MMR 和 no-answer，以及 Part 4 的 citation 闭环，是基于官方主线增加的本地求职向实验，不冒充官方 Notebook 原样代码。

## 当前 API、本地模型与 GLM 适配

| 官方旧写法 | 本地当前写法 |
| --- | --- |
| `langchain.text_splitter` | `langchain_text_splitters` |
| `langchain.prompts.ChatPromptTemplate` | `langchain_core.prompts.ChatPromptTemplate` |
| `Chroma.from_documents(...)` | 基础课件使用 `InMemoryVectorStore` |
| `get_relevant_documents(question)` | `retriever.invoke(question)` |
| `ChatOpenAI()` | `ChatOpenAI(model=ZHIPU_CHAT_MODEL, openai_api_base=ZHIPU_BASE_URL, ...)` |
| `OpenAIEmbeddings()` | 默认 `LocalMiniLMEmbeddings`；仅 `--embedding glm` 使用远程 `OpenAIEmbeddings` |

默认模型为：

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

它由 FastEmbed / ONNX Runtime 在 CPU 上运行，输出 384 维向量，支持中英文。第一次执行 embedding 时会把约 120–220 MB（取决于量化格式与下载源）的模型文件放到 `~/.cache/fastembed`；后续复用缓存，不需要 API Key，也不会调用远程 embedding 服务。

需要在线回答、查询改写或远程 embedding 对比时，GLM 配置来自根目录 `.env` 或已导出的环境变量：

```bash
ZHIPU_API_KEY=...
ZHIPU_BASE_URL=https://ai-hub.digiwincloud.com.cn/v1
ZHIPU_CHAT_MODEL=ep-qwen2.5-72b
ZHIPU_EMBEDDING_MODEL=embedding-3
```

`--live` 只控制在线回答生成与 Multi Query 改写，不再决定 embedding。只有显式使用 `--embedding glm` 才会请求 `embedding-3`，因此现有 key 没有该模型权限也不影响默认课程运行。

## 安装与本地运行

在仓库根目录执行：

```bash
.venv/bin/python -m pip install -r 3_rag_from_scratch/requirements.txt

.venv/bin/python 3_rag_from_scratch/part1_overview.py
.venv/bin/python 3_rag_from_scratch/part2_indexing.py
.venv/bin/python 3_rag_from_scratch/part2_chunking_parameter_comparison.py
.venv/bin/python 3_rag_from_scratch/part2_offline_vs_glm_embeddings.py
.venv/bin/python 3_rag_from_scratch/part3_retrieval.py
.venv/bin/python 3_rag_from_scratch/part3_retrieval_k_score_mmr_no_answer.py
.venv/bin/python 3_rag_from_scratch/part4_generation.py
.venv/bin/python 3_rag_from_scratch/part4_answer_with_citations.py
.venv/bin/python 3_rag_from_scratch/part5_multi_query.py
.venv/bin/python 3_rag_from_scratch/part15_reciprocal_rank_fusion_reranking.py
```

默认使用本地 `LocalMiniLMEmbeddings`。如果想观察“词项哈希”和“真实语义模型”的差异，可加 `--embedding hash`：

```bash
.venv/bin/python 3_rag_from_scratch/part1_overview.py --embedding hash
```

Part 1 / 4 / 5 不加 `--live` 时，回答生成器仍是明确标注的离线抽取式基线，不伪装成在线模型生成。

## 在线模型 live 运行

复制根目录配置模板，填写自己的 key，不要写入 Python 文件：

```bash
cp .env.example .env

.venv/bin/python 3_rag_from_scratch/part1_overview.py --live
.venv/bin/python 3_rag_from_scratch/part4_answer_with_citations.py --live
.venv/bin/python 3_rag_from_scratch/part5_multi_query.py --live
.venv/bin/python 3_rag_from_scratch/part15_reciprocal_rank_fusion_reranking.py --live
```

上面这些命令仍使用本地 MiniLM 检索，只把生成/查询改写交给配置的在线模型。若 provider 以后开放 `embedding-3`，可单独运行远程对比：

```bash
.venv/bin/python 3_rag_from_scratch/part2_offline_vs_glm_embeddings.py --embedding glm
```

涉及资料源的课件可加 `--web-source`，改用官方 Lilian Weng 博客资料。切块实验使用的 `cl100k_base` 只是为了复现官方 tiktoken 实验与估算上下文大小，不能当作 GLM 的精确 tokenizer。

## 完成线与目录边界

学完目录 3 后，应该能独立说明：

- `chunk_size` / `chunk_overlap` 如何影响 chunk 数、命中与 token 成本；
- `k` 过小会漏召回，过大会引入噪声；
- top-k 返回候选不代表问题有答案；
- similarity 与 MMR 的取舍；
- citation 为什么必须由 accepted Documents 构建；
- Multi Query 如何提高召回，RRF 如何融合多个排名。

RRF 是基于排名的融合算法，不是 Cohere/cross-encoder 语义 reranker。PDF/Markdown 摄取、Chroma 持久化、稳定 chunk ID、增量索引、正式拒答、FastAPI、黄金集评测、Docker 和 CI 继续由 `4_rag_knowledge_base_service` 承接，不在这里复制一套。

## 官方依据

- [RAG From Scratch Part 1–4](https://github.com/langchain-ai/rag-from-scratch/blob/main/rag_from_scratch_1_to_4.ipynb)
- [RAG From Scratch Part 5–9](https://github.com/langchain-ai/rag-from-scratch/blob/main/rag_from_scratch_5_to_9.ipynb)
- [RAG From Scratch Part 15–18](https://github.com/langchain-ai/rag-from-scratch/blob/main/rag_from_scratch_15_to_18.ipynb)
- [LangChain Retrieval / RAG](https://docs.langchain.com/oss/python/langchain/retrieval)
- [LangChain token splitting](https://docs.langchain.com/oss/python/integrations/splitters/split_by_token)
- [FastEmbed 支持的模型](https://qdrant.github.io/fastembed/examples/Supported_Models/)
- [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
- [GLM OpenAI API 兼容说明](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)
