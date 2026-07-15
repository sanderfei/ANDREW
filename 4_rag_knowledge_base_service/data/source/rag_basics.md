# 两步 RAG 与索引基础

`two_step_rag` 的固定数据流是：先执行 indexing，再由 retriever 检索，最后把检索到的 context 交给生成步骤。检索与生成各执行一次，因此在文档问答中比自由 Agent 更容易预测和调试。

Indexing 的顺序是：加载 Document、按 chunk_size / chunk_overlap 切块、调用 `embed_documents(chunks)`、把向量和 metadata 写入向量库。查询时必须调用 `embed_query(question)`；不要把“写入多个文档”和“查询一个问题”的两个 embedding 契约混为一谈。

`chunk_overlap` 会保留相邻 chunk 的边界内容，减少一句话正好被切断时的检索损失；它不是越大越好，过大会增加重复和成本。

每个片段都需要稳定的 `stable_chunk_id`。本项目用来源相对路径、页码、chunk 序号和 chunk 内容 hash 生成 ID，因此重建时可以准确删除旧向量、写入新向量，并让 citation 指向可复查的片段。
