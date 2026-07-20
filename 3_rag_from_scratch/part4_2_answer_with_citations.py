"""Part 4 补充：用同一批检索文档生成回答与可验证引用。"""

from __future__ import annotations

try:
    from ._common import (
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        Document,
        StrOutputParser,
        build_chat_model,
        build_embeddings,
        build_rag_prompt,
        build_vector_store,
        embedding_runtime_config,
        format_documents,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents,
        zhipu_runtime_config,
    )
except ImportError:
    from _common import (
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        Document,
        StrOutputParser,
        build_chat_model,
        build_embeddings,
        build_rag_prompt,
        build_vector_store,
        embedding_runtime_config,
        format_documents,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents,
        zhipu_runtime_config,
    )


QUESTION = "为什么 RAG 的 citation 必须来自本次检索结果？"
NO_ANSWER_QUESTION = "明天南京的最高气温是多少？"
MIN_SCORE = 0.2

DOCUMENTS = [
    Document(
        page_content=(
            "RAG 的 citation 应由程序根据本次真实检索到的 Document.metadata "
            "生成，而不是让语言模型自由编写来源。"
        ),
        metadata={"source": "citations.md", "topic": "citation", "page": 1},
    ),
    Document(
        page_content=(
            "回答所使用的 context 与 citation 必须来自同一批被接受的 chunk，"
            "否则用户点开引用时可能无法找到支撑答案的原文。"
        ),
        metadata={"source": "grounding.md", "topic": "grounding", "page": 2},
    ),
    Document(
        page_content=(
            "检索阈值用于拦截资料不足的问题。没有足够相关的 chunk 时，"
            "应返回不知道，并保持 citations 为空。"
        ),
        metadata={"source": "answerability.md", "topic": "refusal", "page": 1},
    ),
]


def _citation(document: Document, score: float) -> dict[str, object]:
    return {
        "source": document.metadata.get("source", "unknown"),
        "topic": document.metadata.get("topic"),
        "page": document.metadata.get("page"),
        "start_index": document.metadata.get("start_index"),
        "score": round(float(score), 6),
        "excerpt": " ".join(document.page_content.split())[:240],
    }


# candidates（Top-3 全部候选）
#     ├─ retrieval：全部保留，标记 accepted=true/false
#     └─ accepted：只保留通过阈值的文档
#            ├─ 生成模型的 context
#            └─ citations
def ask_with_citations(
    vector_store,
    question: str,
    *,
    use_live: bool,
    min_score: float = MIN_SCORE,
) -> dict[str, object]:
    candidates = vector_store.similarity_search_with_score(question, k=3)

    # 只保留通过阈值的文档
    accepted = [
        (document, float(score))
        for document, score in candidates
        if float(score) >= min_score
    ]

    # retrieval：全部保留，标记 accepted=true/false
    retrieval = [
        {
            **_citation(document, float(score)),
            "accepted": float(score) >= min_score,
        }
        for document, score in candidates
    ]

    if not accepted:
        return {
            "question": question,
            "answerable": False,
            "answer": "我不知道，当前知识库中没有足够相关资料。",
            "citations": [],
            "retrieval": retrieval,
        }

    accepted_documents = [document for document, _ in accepted]
    chain = build_rag_prompt() | build_chat_model(use_live=use_live) | StrOutputParser()
    answer = chain.invoke(
        {
            "context": format_documents(accepted_documents),
            "question": question,
        }
    )
    return {
        "question": question,
        "answerable": True,
        "answer": answer,
        # citation 由本地程序从 accepted Documents 构建，模型无权编造。
        "citations": [_citation(document, score) for document, score in accepted],
        "retrieval": retrieval,
    }


def main() -> None:
    options = parse_runtime_options("RAG Part 4 补充：answer + citations")
    if options.use_web_source:
        source_documents = load_source_documents(True)
        question = DEFAULT_QUESTION
    else:
        source_documents = DOCUMENTS
        question = QUESTION

    chunks = split_documents(source_documents, chunk_size=500, chunk_overlap=80)
    embeddings = build_embeddings(mode=options.embedding_mode)
    vector_store = build_vector_store(chunks, embeddings=embeddings)

    print_json(
        "Part 4 - Answer With Citations",
        {
            "official_basis": OFFICIAL_TUTORIAL_URL,
            "embedding": embedding_runtime_config(options.embedding_mode),
            "generation_mode": "online chat model" if options.use_live else "offline extractive",
            "glm_config": (
                zhipu_runtime_config()
                if options.use_live or options.embedding_mode == "glm"
                else None
            ),
            "min_score_for_demo": MIN_SCORE,
            "threshold_warning": (
                "阈值只对当前 embedding 和数据集有意义；切换模型后，"
                "必须使用评测集重新标定。"
            ),
            "known_answer": ask_with_citations(
                vector_store,
                question,
                use_live=options.use_live,
            ),
            "no_answer": ask_with_citations(
                vector_store,
                NO_ANSWER_QUESTION,
                use_live=options.use_live,
            ),
            "citation_contract": "context 与 citations 必须来自同一批 accepted Documents。",
        },
    )


if __name__ == "__main__":
    main()
