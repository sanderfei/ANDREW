"""Part 2 补充：用三组 token-aware 参数比较切块与检索结果。"""

from __future__ import annotations

try:
    from ._common import (
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        Document,
        build_embeddings,
        build_vector_store,
        count_tokens,
        embedding_runtime_config,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents_token_aware,
    )
except ImportError:
    from _common import (
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        Document,
        build_embeddings,
        build_vector_store,
        count_tokens,
        embedding_runtime_config,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents_token_aware,
    )


CHUNK_QUESTION = "chunk overlap 为什么能减少切块边界的信息丢失？"
CHUNK_CONFIGS = (
    {"chunk_size": 80, "chunk_overlap": 0},
    {"chunk_size": 140, "chunk_overlap": 30},
    {"chunk_size": 260, "chunk_overlap": 60},
)

LOCAL_LONG_DOCUMENT = Document(
    page_content="""
RAG 的 indexing 阶段会先加载原始文档，再把长文本分成可检索的 chunk。chunk 太大时，一次召回会夹带较多无关信息，并占用更多上下文 token；chunk 太小时，一个完整概念可能被拆散到多个片段。

chunk overlap 会让相邻 chunk 保留一小段重复文本。当关键句子恰好落在切块边界时，overlap 能减少上下文被截断造成的信息丢失。但 overlap 越大，索引中的重复内容也越多，embedding 成本、存储占用和检索去重压力都会增加。

选择参数不能只看 chunk 数量。应该用一组真实问题比较：正确资料是否进入 top-k，召回内容是否有足够语义，是否带入大量噪声，以及最终注入 prompt 的 token 数。这些指标必须结合具体文档类型调整。

递归字符分隔器会优先尝试段落、换行和空格等自然边界。from_tiktoken_encoder 则把 chunk_size 和 chunk_overlap 解释为 token 数，比简单的字符数更接近模型实际上下文预算。
""".strip(),
    metadata={"source": "chunking-lab.md", "topic": "chunking"},
)


def _top_matches(vector_store, question: str, k: int = 2) -> list[dict[str, object]]:
    return [
        {
            "score": round(float(score), 6),
            "start_index": document.metadata.get("start_index"),
            "token_count": count_tokens(document.page_content),
            "content": " ".join(document.page_content.split())[:280],
        }
        for document, score in vector_store.similarity_search_with_score(question, k=k)
    ]


def main() -> None:
    options = parse_runtime_options("RAG Part 2 补充：切块参数对比")
    documents = (
        load_source_documents(True)
        if options.use_web_source
        else [LOCAL_LONG_DOCUMENT]
    )
    question = DEFAULT_QUESTION if options.use_web_source else CHUNK_QUESTION
    embeddings = build_embeddings(mode=options.embedding_mode)

    experiments: list[dict[str, object]] = []
    for config in CHUNK_CONFIGS:
        chunks = split_documents_token_aware(documents, **config)
        token_counts = [count_tokens(chunk.page_content) for chunk in chunks]
        vector_store = build_vector_store(chunks, embeddings=embeddings)
        experiments.append(
            {
                **config,
                "chunk_count": len(chunks),
                "chunk_token_min": min(token_counts),
                "chunk_token_max": max(token_counts),
                "chunk_token_average": round(sum(token_counts) / len(token_counts), 2),
                "top_matches": _top_matches(vector_store, question),
            }
        )

    print_json(
        "Part 2 - Chunking Parameter Comparison",
        {
            "official_basis": OFFICIAL_TUTORIAL_URL,
            "embedding": embedding_runtime_config(options.embedding_mode),
            "question": question,
            "experiments": experiments,
            "completion_rule": "比较 chunk 数、top-k 命中内容、噪声与 token 成本，不只看一个参数。",
        },
    )


if __name__ == "__main__":
    main()
