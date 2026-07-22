# 4. 本地 RAG 知识库问答服务

这是第一个综合工程项目：把 `3_rag_from_scratch` 已学完的 indexing、retrieval、拒答、generation 和 citation 串成可运行、可评测、可部署的服务。

本机默认配置已经与目录 3 对齐：`FastEmbed + paraphrase-multilingual-MiniLM-L12-v2` 负责本地 384 维向量，离线模式返回可检查的检索摘录；`--mode live` 只把最终生成切到根目录 `.env` 中的 `ep-qwen2.5-72b`，不会偷偷改用远程 embedding。

## 建议学习顺序

| 阶段 | 先看代码 | 重点 |
| --- | --- | --- |
| 第 5 周：摄取与持久化 | `loaders.py` → `embeddings.py` → `indexer.py` | Markdown/PDF、切块、稳定 chunk ID、Chroma、manifest 增量索引 |
| 第 6 周：问答服务 | `contracts.py` → `kb_service.py` → `app.py` / `cli.py` | score + lexical gate、拒答、citation、FastAPI 契约、request ID |
| 第 7 周：质量与交付 | `evaluate.py` → `scripts/smoke.py` → Docker / CI | 20 条黄金集、更新/删除回归、API 冒烟、可复现运行 |

## 能力边界

- 递归读取 `data/source/` 的 Markdown、PDF；PDF 每页保留 page metadata。
- 用 `RecursiveCharacterTextSplitter(add_start_index=True)` 切块；稳定 chunk ID 由来源相对路径、页码、chunk 序号、内容 hash 组成。
- 用当前独立集成包 `langchain_chroma.Chroma` 通过 `persist_directory` 持久化向量。
- `runtime/index_manifest.json` 记录来源 hash 与 chunk IDs，因此新增、修改、删除文件会增量同步。
- `POST /v1/ask` 始终返回 `answer`、`answerable`、`citations`、`retrieval`、`request_id`；相关度不足时固定拒答且不调用聊天模型。
- embedding 与回答模式是两个独立开关：`local` MiniLM 是本机默认，`hash` 是无需模型下载的 CI/教学基线，`glm` 才调用远程 `embedding-3`。

## 安装与直接运行

在仓库根目录执行：

```bash
.venv/bin/python -m pip install -r 4_rag_knowledge_base_service/requirements.txt

.venv/bin/python 4_rag_knowledge_base_service/cli.py reindex --reset
.venv/bin/python 4_rag_knowledge_base_service/cli.py ask "stable_chunk_id 如何帮助增量索引？"
.venv/bin/python 4_rag_knowledge_base_service/cli.py health

# HTTP 服务（默认 http://127.0.0.1:8000）
.venv/bin/python 4_rag_knowledge_base_service/app.py
```

公开入口均能直接执行：`app.py`、`cli.py`、`evaluate.py`、`scripts/smoke.py`。内部模块不作为独立课件入口。

首次索引后可调用 API：

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/v1/reindex \
  -H 'Content-Type: application/json' \
  -d '{}'

curl -X POST http://127.0.0.1:8000/v1/ask \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: demo-rag-001' \
  -d '{"question":"citation 必须包含哪些定位字段？","top_k":4}'
```

## API 契约

| 路由 | 请求 | 关键结果 |
| --- | --- | --- |
| `GET /health` | 无 | `status`、`mode`、`index_ready`、文档/片段数、`index_fingerprint`、`request_id` |
| `POST /v1/reindex` | `{ "reset": false }` | 新增/更新/跳过/删除文件数，写入/删除 chunk 数；配置改变时用 `{ "reset": true }` |
| `POST /v1/ask` | `{ "question": "...", "top_k": 4 }` | `answer`、`answerable`、`citations`、`retrieval`、`request_id` |

HTTP 请求如果传入 `X-Request-ID`，响应 header 和 JSON 字段会保留它。`/v1/reindex` 不接受任意本地路径，避免把服务变成远程文件读取入口。

## 本机三种 embedding 与两种回答模式

两个开关彼此独立：

| 配置 | 实际行为 | 是否需要 Key |
| --- | --- | --- |
| `--embedding local`（默认） | 本地 MiniLM 写入和查询 Chroma | 否 |
| `--embedding hash` | 稳定 Hash 教学/CI 基线 | 否 |
| `--embedding glm` | 在线 `embedding-3` | 是 |
| `--mode offline`（默认） | 通过 gate 后返回检索摘录 | 否 |
| `--mode live` | 通过 gate 后调用 `ep-qwen2.5-72b` 生成 | 是 |

根目录 `.env` 已配置过目录 3 时可直接复用，不必复制第二份 Key。若希望目录 4 使用独立非敏感参数，可复制项目内模板（不要提交生成的 `.env`）：

```bash
cp 4_rag_knowledge_base_service/.env.example 4_rag_knowledge_base_service/.env

# 仍用本地 MiniLM 检索，只把回答交给在线 Qwen；无需重建索引
.venv/bin/python 4_rag_knowledge_base_service/cli.py --mode live \
  ask "citation 为什么必须来自 accepted chunks？"

# 仅用于远程 embedding 对比；切换 embedding 后必须重建索引
.venv/bin/python 4_rag_knowledge_base_service/cli.py --embedding glm \
  reindex --reset
```

Live 模式仍使用固定两步链 `retrieval -> context -> prompt -> model -> StrOutputParser`。citation 始终由服务端从 accepted Documents 构建，模型不能自由编造来源。

## 评测与冒烟

```bash
.venv/bin/python 4_rag_knowledge_base_service/scripts/smoke.py

# 验证本机默认 MiniLM（推荐学习时运行）
.venv/bin/python 4_rag_knowledge_base_service/evaluate.py --embedding local

# 无需下载模型的确定性 Hash 回归（CI 使用）
.venv/bin/python 4_rag_knowledge_base_service/evaluate.py --embedding hash
```

`data/eval/golden_cases.json` 有 20 条离线黄金样本，覆盖命中、相近问法、拒答、引用、本机模型配置和服务运维知识；`evaluate.py` 还会在临时目录验证文档更新和删除的增量回归。报告默认写入被忽略的 `reports/evaluation.json`。

## Docker

```bash
docker build -t andrew-rag-kb 4_rag_knowledge_base_service
docker run --rm -p 8000:8000 \
  -v "$PWD/4_rag_knowledge_base_service/data/source:/app/data/source:ro" \
  -v rag-kb-runtime:/app/runtime \
  andrew-rag-kb
```

镜像为了无需内置或联网下载 122 MB 模型，默认使用 `hash + offline`、单 Uvicorn worker；本机直接运行仍默认 `local MiniLM + offline`。镜像不复制 `.env`，运行时向量数据放在 Docker volume。

## 文档与官方依据

- [架构说明](docs/architecture.md)
- [评测指南](docs/evaluation-guide.md)
- [3 分钟演示脚本](docs/demo-script.md)
- [LangChain Retrieval](https://docs.langchain.com/oss/python/langchain/retrieval)
- [LangChain Knowledge Base](https://docs.langchain.com/oss/python/langchain/knowledge-base)
- [LangChain Chroma integration](https://docs.langchain.com/oss/python/integrations/vectorstores/chroma)
