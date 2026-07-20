"""Part 3 补充：k、score、MMR 与无答案问题的检索实验。"""

from __future__ import annotations

try:
    from ._common import (
        CURRENT_KNOWLEDGE_BASE_DOCS_URL,
        OFFICIAL_TUTORIAL_URL,
        Document,
        build_embeddings,
        build_retriever,
        build_vector_store,
        compact_documents,
        embedding_runtime_config,
        parse_runtime_options,
        print_json,
    )
except ImportError:
    from _common import (
        CURRENT_KNOWLEDGE_BASE_DOCS_URL,
        OFFICIAL_TUTORIAL_URL,
        Document,
        build_embeddings,
        build_retriever,
        build_vector_store,
        compact_documents,
        embedding_runtime_config,
        parse_runtime_options,
        print_json,
    )


QUESTION = "RAG 检索阶段的 top-k 有什么作用？"
NO_ANSWER_QUESTION = "南京今天会下雨吗？"
MIN_SCORE = 0.15

DOCUMENTS = [
    Document(
        page_content="top-k 控制检索器返回的候选文档数量。k 较小时噪声低，但可能漏掉正确资料。",
        metadata={"source": "retrieval-basics.md", "topic": "top-k"},
    ),
    Document(
        page_content="增大 top-k 通常可以提高召回率，但会带入更多无关 chunk，同时增加 prompt token 成本。",
        metadata={"source": "retrieval-tuning.md", "topic": "top-k tradeoff"},
    ),
    Document(
        page_content="MMR 在相关性与多样性之间做平衡，用于减少结果列表中内容高度重复的片段。",
        metadata={"source": "mmr.md", "topic": "MMR"},
    ),
    Document(
        page_content="检索分数可以帮助设置最低阈值。当所有候选都低于阈值时，系统应该拒答而不是强行生成。",
        metadata={"source": "answerability.md", "topic": "threshold"},
    ),
    Document(
        page_content="chunk overlap 能保留切块边界附近的重复上下文，但过大会增加存储与去重成本。",
        metadata={"source": "chunking.md", "topic": "chunking"},
    ),
    Document(
        page_content="Docker 用于封装运行时依赖，使服务可在开发机与服务器上以相同方式启动。",
        metadata={"source": "deployment.md", "topic": "deployment"},
    ),
]


def _scored(vector_store, question: str, k: int) -> list[dict[str, object]]:
    return [
        {
            "rank": rank,
            "source": document.metadata["source"],
            "score": round(float(score), 6),
            # 不是 Embedding 模型或 Retriever 给出的判断，只是本地代码做了一次数字比较。
            "accepted": float(score) >= MIN_SCORE,
            "content": document.page_content,
        }
        for rank, (document, score) in enumerate(
            vector_store.similarity_search_with_score(question, k=k), start=1
        )
    ]

# similarity 只关心“文档与问题有多相似”；
# MMR 平衡相关性和多样性，同时关心“与问题相关”和“返回结果之间不要太重复”。
# 当 k=1 时，MMR 和 Similarity 通常没有明显区别，因为只返回一个文档，还不存在“多个结果互相重复”的问题。
# MMR 这组结果反而暴露了一个重要风险——多样性权重过高时，会把明显无关的 Docker 文档选进来
# k 增大
#   → 找到互补证据的机会增加
#   → 同时也会带入更多间接相关内容
#   → 后续 Prompt token 增加
# 更合理的实际策略通常是：
#   → 先用相关性阈值排除明显无关候选
#   → 再在剩余候选中使用 MMR 去重
def main() -> None:
    options = parse_runtime_options("RAG Part 3 补充：k / score / MMR / no-answer")
    embeddings = build_embeddings(mode=options.embedding_mode)
    vector_store = build_vector_store(DOCUMENTS, embeddings=embeddings)

    k_comparison = {str(k): _scored(vector_store, QUESTION, k) for k in (1, 2, 4)}
    # search_type="similarity"
    similarity_retriever = build_retriever(vector_store, k=3)
    # 先按相似度找出 6 个候选文档
    # 使用 MMR 平衡相关性和多样性
    # 最终返回 3 个文档
    mmr_retriever = build_retriever(
        vector_store,
        k=3,
        search_type="mmr",
        fetch_k=6,
        lambda_mult=0.5,# 越接近 1 越重视相关性，越接近 0 越重视多样性
    )
    no_answer_candidates = _scored(vector_store, NO_ANSWER_QUESTION, 3)

    print_json(
        "Part 3 - Retrieval Quality Experiments",
        {
            "official_basis": OFFICIAL_TUTORIAL_URL,
            "current_api_docs": CURRENT_KNOWLEDGE_BASE_DOCS_URL,
            "embedding": embedding_runtime_config(options.embedding_mode),
            "question": QUESTION,
            "min_score_for_demo": MIN_SCORE,
            "threshold_warning": "阈值只对当前 embedding/数据集有意义，切换模型后必须重新用评测集标定。",
            "k_comparison": k_comparison,
            "similarity_top3": compact_documents(similarity_retriever.invoke(QUESTION)),
            "mmr_top3": compact_documents(mmr_retriever.invoke(QUESTION)),
            "no_answer_demo": {
                "question": NO_ANSWER_QUESTION,
                "candidates": no_answer_candidates,
                "answerable": any(item["accepted"] for item in no_answer_candidates),
                "lesson": "top-k 永远会尝试返回结果；候选文档不等于有答案，还需要 score/gate。",
            },
        },
    )


if __name__ == "__main__":
    main()
