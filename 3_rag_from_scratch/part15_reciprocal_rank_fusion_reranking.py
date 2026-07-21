"""Part 15：基于官方 RAG-Fusion 的 Reciprocal Rank Fusion 重排序。"""

from __future__ import annotations

try:
    from ._common import (
        DEFAULT_QUESTION,
        OFFICIAL_RERANK_URL,
        Document,
        build_embeddings,
        build_retriever,
        build_vector_store,
        compact_documents,
        embedding_runtime_config,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents_token_aware,
        zhipu_runtime_config,
    )
    from .part5_multi_query import (
        MULTI_QUERY_DOCUMENTS,
        QUESTION,
        build_query_variants,
        document_key,
    )
except ImportError:
    from _common import (
        DEFAULT_QUESTION,
        OFFICIAL_RERANK_URL,
        Document,
        build_embeddings,
        build_retriever,
        build_vector_store,
        compact_documents,
        embedding_runtime_config,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents_token_aware,
        zhipu_runtime_config,
    )
    from part5_multi_query import (
        MULTI_QUERY_DOCUMENTS,
        QUESTION,
        build_query_variants,
        document_key,
    )

# 累加同一文档在不同排名中的 RRF 分数：一种把多组检索排名合并成一组统一排名的算法
# Σ 1 / (k + rank) 多条查询都把某篇文档排在前面，说明它得到多路检索结果的共同支持，因此融合后的排名应该更高。
def reciprocal_rank_fusion(
    ranked_document_lists: list[list[Document]],
    *,
    k: int = 60,  # k=60 是 RRF 公式中的平滑常数
) -> list[tuple[Document, float]]:
    """官方 Part 15 核心公式：同一文档在多个排名中的得分累加。"""

    scores: dict[str, float] = {}
    documents_by_key: dict[str, Document] = {}
    for documents in ranked_document_lists:
        for rank, document in enumerate(documents):
            key = document_key(document)
            documents_by_key.setdefault(key, document)
            scores[key] = scores.get(key, 0.0) + 1.0 / (rank + k)
    return [
        (documents_by_key[key], score)
        for key, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
    ]

# RRF（Reciprocal Rank Fusion，倒数排名融合）算法
def main() -> None:
    options = parse_runtime_options("RAG From Scratch Part 15：RRF Re-ranking")
    if options.use_web_source:
        documents = split_documents_token_aware(
            load_source_documents(True),
            chunk_size=300,
            chunk_overlap=50,
        )
    else:
        documents = MULTI_QUERY_DOCUMENTS
    question = DEFAULT_QUESTION if options.use_web_source else QUESTION
    embeddings = build_embeddings(mode=options.embedding_mode)
    vector_store = build_vector_store(documents, embeddings=embeddings)
    # 小样例每个查询取 2 条，保留一定多样性又避免把所有噪声都送入 RRF。
    retriever = build_retriever(vector_store, k=2)

    queries = build_query_variants(question, use_live=options.use_live)[:4]
    # batch 返回的数据格式
    # ranked_lists = [
    #   [query1_top1, query1_top2],
    #   [query2_top1, query2_top2],
    #   [query3_top1, query3_top2],
    #   [query4_top1, query4_top2],
    # ]
    ranked_lists = retriever.batch(queries)
    fused = reciprocal_rank_fusion(ranked_lists, k=60)

    print_json(
        "Part 15 - Reciprocal Rank Fusion Re-ranking",
        {
            "official_tutorial": OFFICIAL_RERANK_URL,
            "embedding": embedding_runtime_config(options.embedding_mode),
            "query_generation_mode": "online chat model" if options.use_live else "offline fixed query variants",
            "glm_config": (
                zhipu_runtime_config()
                if options.use_live or options.embedding_mode == "glm"
                else None
            ),
            "question": question,
            "queries": queries,
            "rankings_before_fusion": [
                {
                    "query": query,
                    "documents": compact_documents(retrieved),
                }
                for query, retrieved in zip(queries, ranked_lists)
            ],
            "rrf_k": 60,
            "ranking_after_fusion": [
                {
                    "rank": rank,
                    "rrf_score": round(score, 8),
                    "source": document.metadata.get("source", "unknown"),
                    "content": document.page_content,
                }
                for rank, (document, score) in enumerate(fused, start=1)
            ],
            "boundary": "RRF 融合多个召回排名；它不是 Cohere/cross-encoder 语义 reranker。",
        },
    )


if __name__ == "__main__":
    main()
