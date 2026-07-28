"""Part 1：把 Indexing、Retrieval、Generation 串成一个最小两步 RAG。"""

from __future__ import annotations

# 支持两种启动方式：
#
# 1. 包模块方式：
#    `.venv/bin/python -m 3_rag_from_scratch.part1_overview`
#    `-m` 表示按“包名.模块名”查找并运行；Python 知道当前模块属于
#    `3_rag_from_scratch` 包，因此 `._common` 中的 `.` 能表示“当前包”。
#
# 2. 直接脚本方式：
#    `.venv/bin/python 3_rag_from_scratch/part1_overview.py`
#    此时文件通常没有父包上下文，`from ._common` 会触发 ImportError；
#    except 再通过 `from _common` 从脚本所在目录加载同一个 `_common.py`。
#
# 两段代码导入的名称相同，只是模块查找方式不同；任意一次成功后，后面的
# Part 1 逻辑都可以使用同一组函数和常量。
try:
    from ._common import (
        CURRENT_RETRIEVAL_DOCS_URL,
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        build_rag_chain,
        build_retriever,
        build_vector_store,
        compact_documents,
        embedding_runtime_config,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents,
    )
except ImportError:  # pragma: no cover - 仅 direct-script 入口会走到这里。
    from _common import (
        CURRENT_RETRIEVAL_DOCS_URL,
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        build_rag_chain,
        build_retriever,
        build_vector_store,
        compact_documents,
        embedding_runtime_config,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents,
    )


# question
#    ↓
# Retriever 做向量检索
#    ↓
# list[Document]
#    ↓
# 提取 Document.page_content，拼成 context 字符串
#    ↓
# context + 原始 question 填入 Prompt
# 经过填充后，模型实际看到的内容类似：
# Answer the question using only the supplied context.
# <context>
# [source=local-rag-notes]
# Task decomposition breaks a complex task into smaller...
# [source=local-rag-notes]
# Indexing normally loads source documents...
# </context>
# Question: What is Task Decomposition?
#    ↓
# 交给模型回答
#    ↓
# 得到字符串答案
#
# 在仓库根目录运行（mode=live，embedding_mode=local）：
# .venv/bin/python 3_rag_from_scratch/part1_overview.py --live --embedding local
def main() -> None:
    options = parse_runtime_options("RAG From Scratch Part 1：完整最小 RAG")

    # 1) Indexing：Document -> chunk -> embedding -> vector store。
    source_documents = load_source_documents(options.use_web_source)
    chunks = split_documents(source_documents, chunk_size=1_000, chunk_overlap=200)
    # 生成向量并建立向量库
    vector_store = build_vector_store(
        chunks,
        embedding_mode=options.embedding_mode,
    )

    # 2) Retrieval：把 vector store 包装为可 invoke 的 retriever。
    retriever = build_retriever(vector_store, k=2)
    # retriever.invoke实际执行 LocalMiniLMEmbeddings.embed_query() 返回相似度最高的两个 Document
    retrieved_documents = retriever.invoke(DEFAULT_QUESTION)

    # 3) Generation：固定先检索，再把 context 和问题交给 prompt | model | parser。
    answer = build_rag_chain(retriever, use_live=options.use_live).invoke(DEFAULT_QUESTION)

    print_json(
        "Part 1 - Overview",
        {
            "official_tutorial": OFFICIAL_TUTORIAL_URL,
            "current_api_docs": CURRENT_RETRIEVAL_DOCS_URL,
            "source_mode": "web" if options.use_web_source else "local fixture",
            "embedding": embedding_runtime_config(options.embedding_mode),
            "generation_mode": "online chat model" if options.use_live else "offline extractive",
            "pipeline": "Document -> chunks -> InMemoryVectorStore -> retriever.invoke -> prompt -> model",
            "question": DEFAULT_QUESTION,
            "indexed_chunk_count": len(chunks),
            "retrieved_documents": compact_documents(retrieved_documents),
            "answer": answer,
        },
    )


if __name__ == "__main__":
    main()
