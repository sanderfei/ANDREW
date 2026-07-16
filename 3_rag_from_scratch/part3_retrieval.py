"""Part 3：用当前 retriever.invoke(...) API 检索 Document。"""

from __future__ import annotations

try:  # 支持 `python 3_rag_from_scratch/part3_retrieval.py` 直接运行。
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
                for question, documents in zip(
                    [DEFAULT_QUESTION, SECOND_QUESTION], batch_documents
                )
            ],
        },
    )


if __name__ == "__main__":
    main()
