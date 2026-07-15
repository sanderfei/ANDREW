# 4. 本地 RAG 知识库问答服务

这是第一个综合工程项目：把 `3_rag_from_scratch` 的两步 RAG 课件扩展为可运行、可评测、可部署的服务。它默认离线，不会在导入或启动时调用任何模型；只有 `RAG_MODE=live` 且提供 `OPENAI_API_KEY` 时，才使用 `OpenAIEmbeddings` 和 `ChatOpenAI`。

## 能力边界

- 递归读取 `data/source/` 的 Markdown、PDF；PDF 每页保留 page metadata。
- 用 `RecursiveCharacterTextSplitter(add_start_index=True)` 切块；稳定 chunk ID 由来源相对路径、页码、chunk 序号、内容 hash 组成。
- 用当前独立集成包 `langchain_chroma.Chroma` 通过 `persist_directory` 持久化向量。
- `runtime/index_manifest.json` 记录来源 hash 与 chunk IDs，因此新增、修改、删除文件会增量同步。
- `POST /v1/ask` 始终返回 `answer`、`answerable`、`citations`、`retrieval`、`request_id`；相关度不足时固定拒答且不调用模型。
- 默认离线 embedding 是稳定 hash 版本，回答是可检查的检索摘录；它用于学习与 CI，不应当被当作生产 embedding。

## 安装与直接运行

在仓库根目录执行：

```bash
.venv/bin/python -m pip install -r 4_rag_knowledge_base_service/requirements.txt

.venv/bin/python 4_rag_knowledge_base_service/cli.py reindex
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

## Live 模式

复制项目内模板并填入自己的变量（不要写到 Python 文件）：

```bash
cp 4_rag_knowledge_base_service/.env.example 4_rag_knowledge_base_service/.env
# 编辑 .env：RAG_MODE=live、OPENAI_API_KEY、可选 OPENAI_BASE_URL
.venv/bin/python 4_rag_knowledge_base_service/cli.py --mode live reindex --reset
```

Live 模式使用固定两步链 `retrieval -> context -> prompt -> model -> StrOutputParser`，citation 仍由服务端检索结果生成，模型不能伪造来源。

## 评测与冒烟

```bash
.venv/bin/python 4_rag_knowledge_base_service/scripts/smoke.py
.venv/bin/python 4_rag_knowledge_base_service/evaluate.py
```

`data/eval/golden_cases.json` 有 18 条离线黄金样本，覆盖命中、相近问法、拒答、引用和服务运维知识；`evaluate.py` 还会在临时目录验证文档更新和删除的增量回归。报告默认写入被忽略的 `reports/evaluation.json`。

## Docker

```bash
docker build -t andrew-rag-kb 4_rag_knowledge_base_service
docker run --rm -p 8000:8000 \
  -v "$PWD/4_rag_knowledge_base_service/data/source:/app/data/source:ro" \
  -v rag-kb-runtime:/app/runtime \
  andrew-rag-kb
```

镜像默认离线运行、单 Uvicorn worker；不复制 `.env`，运行时向量数据放在 Docker volume。

## 文档与官方依据

- [架构说明](docs/architecture.md)
- [评测指南](docs/evaluation-guide.md)
- [3 分钟演示脚本](docs/demo-script.md)
- [LangChain Retrieval](https://docs.langchain.com/oss/python/langchain/retrieval)
- [LangChain Knowledge Base](https://docs.langchain.com/oss/python/langchain/knowledge-base)
- [LangChain Chroma integration](https://docs.langchain.com/oss/python/integrations/vectorstores/chroma)
