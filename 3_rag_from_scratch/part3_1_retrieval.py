"""Part 3：用当前 retriever.invoke(...) API 检索 Document。"""

from __future__ import annotations

try:  # 支持 `python 3_rag_from_scratch/part3_1_retrieval.py` 直接运行。
    from ._common import (
        CURRENT_KNOWLEDGE_BASE_DOCS_URL,
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        build_embeddings,
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
        CURRENT_KNOWLEDGE_BASE_DOCS_URL,
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        build_embeddings,
        build_retriever,
        build_vector_store,
        compact_documents,
        embedding_runtime_config,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents,
    )


SECOND_QUESTION = "How does RAG use retrieved context?"


# 在仓库根目录运行（mode=live，embedding_mode=local）：
# .venv/bin/python 3_rag_from_scratch/part3_1_retrieval.py --live --embedding local
# 本课只有检索阶段，没有回答生成阶段；--live 不会触发聊天模型。
def main() -> None:
    options = parse_runtime_options("RAG From Scratch Part 3：Retrieval")

    chunks = split_documents(
        load_source_documents(options.use_web_source),
        chunk_size=300,
        chunk_overlap=50,
    )
    embeddings = build_embeddings(mode=options.embedding_mode)
    vector_store = build_vector_store(chunks, embeddings=embeddings)

    # 旧教程的 get_relevant_documents(...) 已改为当前 Runnable API：invoke(...)。
    retriever = build_retriever(vector_store, k=1)
    retrieved_documents = retriever.invoke(DEFAULT_QUESTION)
    batch_documents = retriever.batch([DEFAULT_QUESTION, SECOND_QUESTION])

    print_json(
        "Part 3 - Retrieval",
        {
            "official_tutorial": OFFICIAL_TUTORIAL_URL,
            "current_api_docs": CURRENT_KNOWLEDGE_BASE_DOCS_URL,
            "embedding": embedding_runtime_config(options.embedding_mode),
            "retriever_contract": "retriever.invoke(question) -> list[Document]",
            "search_type": "similarity",
            "k": 1,
            "question": DEFAULT_QUESTION,
            "result_count": len(retrieved_documents),
            "retrieved_documents": compact_documents(retrieved_documents),
            "batch_example": [
                {
                    "question": question,
                    "documents": compact_documents(documents),
                }
                # 配对加“元组解包”的写法，zip() 会按相同下标配对：然后格式化batch_example输出json
                # [
                #     ("问题1", [doc1, doc2]),
                #     ("问题2", [doc3, doc4]),
                # ]
                for question, documents in zip(
                    [DEFAULT_QUESTION, SECOND_QUESTION], batch_documents
                )
            ],
        },
    )


if __name__ == "__main__":
    main()
