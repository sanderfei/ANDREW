"""Part 1：把 Indexing、Retrieval、Generation 串成一个最小两步 RAG。"""

from __future__ import annotations

try:  # 支持 `python 3_rag_from_scratch/part1_overview.py` 直接运行。
    from ._common import (
        CURRENT_RETRIEVAL_DOCS_URL,
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        build_rag_chain,
        build_retriever,
        build_vector_store,
        compact_documents,
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
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents,
    )


def main() -> None:
    options = parse_runtime_options("RAG From Scratch Part 1：完整最小 RAG")

    # 1) Indexing：Document -> chunk -> embedding -> vector store。
    source_documents = load_source_documents(options.use_web_source)
    chunks = split_documents(source_documents, chunk_size=1_000, chunk_overlap=200)
    vector_store = build_vector_store(chunks, use_live=options.use_live)

    # 2) Retrieval：把 vector store 包装为可 invoke 的 retriever。
    retriever = build_retriever(vector_store, k=2)
    retrieved_documents = retriever.invoke(DEFAULT_QUESTION)

    # 3) Generation：固定先检索，再把 context 和问题交给 prompt | model | parser。
    answer = build_rag_chain(retriever, use_live=options.use_live).invoke(DEFAULT_QUESTION)

    print_json(
        "Part 1 - Overview",
        {
            "official_tutorial": OFFICIAL_TUTORIAL_URL,
            "current_api_docs": CURRENT_RETRIEVAL_DOCS_URL,
            "source_mode": "web" if options.use_web_source else "local fixture",
            "runtime_mode": "live GLM" if options.use_live else "offline teaching",
            "pipeline": "Document -> chunks -> InMemoryVectorStore -> retriever.invoke -> prompt -> model",
            "question": DEFAULT_QUESTION,
            "indexed_chunk_count": len(chunks),
            "retrieved_documents": compact_documents(retrieved_documents),
            "answer": answer,
        },
    )


if __name__ == "__main__":
    main()
