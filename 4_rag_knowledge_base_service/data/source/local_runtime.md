# 本机模型与运行开关

本机默认 embedding 是 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`。它通过 FastEmbed 和 ONNX Runtime 在 CPU 上运行，每个 chunk 生成一个 384 维向量，不需要 API Key。`RAG_EMBEDDING_MODE=hash` 只用于教学基线和 CI；只有显式设置 `RAG_EMBEDDING_MODE=glm` 才会调用远程 `embedding-3`。

回答模式和 embedding 模式彼此独立。`RAG_MODE=offline` 在通过 answerability gate 后返回可检查的检索摘录；`RAG_MODE=live` 仍使用本地 MiniLM 检索，只把 accepted chunks 组成的 context 交给 `ep-qwen2.5-72b` 生成答案。

目录 4 会复用仓库根目录 `.env` 中的 `ZHIPU_API_KEY`、`ZHIPU_BASE_URL` 和 `ZHIPU_CHAT_MODEL`。任何 Key、Token 或完整 `.env` 都不能写入源码、文档、评测报告和 Git。
