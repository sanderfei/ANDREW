"""Part 2：拆开看 token、embedding、相似度、加载、切块和入库。"""

from __future__ import annotations

try:  # 支持 `python 3_rag_from_scratch/part2_indexing.py` 直接运行。
    from ._common import (
        CURRENT_KNOWLEDGE_BASE_DOCS_URL,
        OFFICIAL_TUTORIAL_URL,
        build_embeddings,
        build_vector_store,
        compact_documents,
        cosine_similarity,
        count_tokens,
        embedding_runtime_config,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents,
    )
except ImportError:  # pragma: no cover - 仅 direct-script 入口会走到这里。
    from _common import (
        CURRENT_KNOWLEDGE_BASE_DOCS_URL,
        OFFICIAL_TUTORIAL_URL,
        build_embeddings,
        build_vector_store,
        compact_documents,
        cosine_similarity,
        count_tokens,
        embedding_runtime_config,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents,
    )


QUESTION = "What kinds of pets do I like?"
DOCUMENT = "My favorite pet is a cat."
RETRIEVAL_CHECK_QUESTION = "What is Task Decomposition?"


def main() -> None:
    options = parse_runtime_options("RAG From Scratch Part 2：Indexing")

    # 手动调用时：embed_query 给问题，embed_documents 给待写入的文档列表。
    embeddings = build_embeddings(mode=options.embedding_mode)
    question_vector = embeddings.embed_query(QUESTION)
    document_vector = embeddings.embed_documents([DOCUMENT])[0]

    # 原教程的 indexing 主线：加载文档 -> 切块 -> 写入 vector store。
    source_documents = load_source_documents(options.use_web_source)
    chunks = split_documents(source_documents, chunk_size=300, chunk_overlap=50)
    vector_store = build_vector_store(chunks, embeddings=embeddings)
    matched_documents = vector_store.similarity_search(RETRIEVAL_CHECK_QUESTION, k=2)

    print_json(
        "Part 2 - Indexing",
        {
            "official_tutorial": OFFICIAL_TUTORIAL_URL,
            "current_api_docs": CURRENT_KNOWLEDGE_BASE_DOCS_URL,
            "source_mode": "web" if options.use_web_source else "local fixture",
            "embedding": embedding_runtime_config(options.embedding_mode),
            "token_example": {
                "text": QUESTION,
                "encoding": "cl100k_base",
                "token_count": count_tokens(QUESTION),
            },
            "manual_embedding_example": {
                "query_method": "embed_query(question)",
                "document_method": "embed_documents([document])[0]",
                "vector_dimension": len(question_vector),
                "cosine_similarity": round(
                    cosine_similarity(question_vector, document_vector), 6
                ),
            },
            "indexing_pipeline": "load -> split_documents -> InMemoryVectorStore.from_documents",
            "indexed_chunk_count": len(chunks),
            "similarity_search_check": {
                "query": RETRIEVAL_CHECK_QUESTION,
                "results": compact_documents(matched_documents),
            },
        },
    )


if __name__ == "__main__":
    main()
