"""Part 2 补充：比较哈希基线、本地 MiniLM 与可选 GLM embedding。"""

from __future__ import annotations

try:
    from ._common import (
        OFFICIAL_TUTORIAL_URL,
        Document,
        build_embeddings,
        build_vector_store,
        embedding_runtime_config,
        parse_runtime_options,
        print_json,
        zhipu_runtime_config,
    )
except ImportError:
    from _common import (
        OFFICIAL_TUTORIAL_URL,
        Document,
        build_embeddings,
        build_vector_store,
        embedding_runtime_config,
        parse_runtime_options,
        print_json,
        zhipu_runtime_config,
    )


QUESTION = "如何减少文本切块边界导致的语义丢失？"
DOCUMENTS = [
    Document(
        page_content="相邻片段保留适量重叠内容，可以让落在分段交界处的完整概念不至于被完全拆散。",
        metadata={"source": "chunk-overlap.md", "topic": "overlap"},
    ),
    Document(
        page_content="向量库通过计算查询向量与文档向量的相似度返回 top-k 候选片段。",
        metadata={"source": "vector-search.md", "topic": "retrieval"},
    ),
    Document(
        page_content="Docker 镜像应固定依赖版本，并在运行时通过环境变量注入配置。",
        metadata={"source": "deployment.md", "topic": "deployment"},
    ),
]


def _evaluate(embeddings) -> dict[str, object]:
    vector = embeddings.embed_query(QUESTION)
    vector_store = build_vector_store(DOCUMENTS, embeddings=embeddings)
    matches = vector_store.similarity_search_with_score(QUESTION, k=3)
    return {
        "vector_dimension": len(vector),
        "vector_norm": round(sum(value * value for value in vector) ** 0.5, 6),
        "ranking": [
            {
                "rank": rank,
                "source": document.metadata["source"],
                "score": round(float(score), 6),
                "content": document.page_content,
            }
            # enumerate 给列表中的每个元素加一个序号：
            for rank, (document, score) in enumerate(matches, start=1)
        ],
    }


def main() -> None:
    options = parse_runtime_options("RAG Part 2 补充：本地与远程 embedding 对比")
    stable_hash_result = _evaluate(build_embeddings(mode="hash"))
    local_result = _evaluate(build_embeddings(mode="local"))
    if options.embedding_mode == "glm":
        glm_result: dict[str, object] = _evaluate(build_embeddings(mode="glm"))
    else:
        glm_result = {
            "status": "skipped",
            "how_to_run": (
                "需要远程对比时配置 ZHIPU_API_KEY，并加 --embedding glm；"
                "token 还需有 embedding-3 权限。"
            ),
        }

    print_json(
        "Part 2 - Local MiniLM vs Hash / Optional GLM",
        {
            "official_basis": OFFICIAL_TUTORIAL_URL,
            "question": QUESTION,
            "stable_hash_baseline": {
                "embedding": embedding_runtime_config("hash"),
                "result": stable_hash_result,
            },
            "local_multilingual_minilm": {
                "embedding": embedding_runtime_config("local"),
                "result": local_result,
            },
            "glm_embedding_3": glm_result,
            "glm_config": (
                zhipu_runtime_config()
                if options.embedding_mode == "glm"
                else None
            ),
            "reading": (
                "哈希基线主要依赖词项重合；本地 MiniLM 与 GLM 都属于语义模型，"
                "应更容易识别不同表达下的相近含义。"
            ),
        },
    )


if __name__ == "__main__":
    main()
