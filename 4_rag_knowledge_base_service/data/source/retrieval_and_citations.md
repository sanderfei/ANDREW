# 检索、引用与拒答

retriever 的契约是：输入非结构化 question，输出按相关度排序的 Document 列表。当前学习 API 使用 `retriever.invoke(question)`，而不是旧的 `get_relevant_documents`。

服务不能只返回自然语言答案。每条 citation 至少要带 `chunk_id`、`source`、PDF page（如有）、`start_index`、quote 和 relevance_score；这些字段让调用方能检查答案到底依据了哪段资料。

可回答性由 answerability gate 决定：没有索引、没有检索结果，或最高 relevance_score 低于阈值时，必须返回 `answerable=false`、空 citations，并明确拒答。此时不能为了“看起来有帮助”而调用模型补全事实。

错误引用（wrong citation）指答案把 A 文档的结论标到 B 文档，或 citation 根本没有支持答案。评测必须同时检查“命中了正确来源”和“没有引用不相关来源”。
