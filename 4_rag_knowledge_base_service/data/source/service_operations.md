# 知识库服务运行与增量更新

`GET /health` 用于检查服务是否存活、当前 mode、collection、source_document_count、indexed_chunk_count、index_fingerprint 和 request_id。它不触发模型调用。

`POST /v1/reindex` 只索引配置好的 data/source 目录，不接受 HTTP 传来的任意文件路径。它读取 Markdown/PDF，依据 manifest 做增量更新：未变文件跳过；新增或修改文件先删除旧 chunk IDs 再写入新 chunks；已删除源文件则删除对应向量。

manifest 保存每个 source 的 sha256 与 chunk_ids。chunk 参数或 embedding 身份改变会改变 index_fingerprint；这时 API 要求调用方显式传 `reset=true`，避免把不同维度或不同语义的向量混在同一个 collection。

每个请求都会有 request_id：如果调用者提供 `X-Request-ID`，服务回写同一个值；否则生成新的 ID。该 ID 用于关联日志、retrieval 和最终 answer。

本地 Chroma 通过 `persist_directory` 保存到 runtime/chroma。服务器保持单 worker，以避免学习阶段的本地向量库出现并发写入竞争。
