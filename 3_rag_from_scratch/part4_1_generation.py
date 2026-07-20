"""Part 4：先看 prompt + model，再组合为完整固定两步 RAG chain。"""

from __future__ import annotations

try:  # 支持 `python 3_rag_from_scratch/part4_1_generation.py` 直接运行。
    from ._common import (
        CURRENT_RETRIEVAL_DOCS_URL,
        DEFAULT_QUESTION,
        OFFICIAL_TUTORIAL_URL,
        StrOutputParser,
        build_chat_model,
        build_embeddings,
        build_rag_chain,
        build_rag_prompt,
        build_retriever,
        build_vector_store,
        compact_documents,
        embedding_runtime_config,
        format_documents,
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
        StrOutputParser,
        build_chat_model,
        build_embeddings,
        build_rag_chain,
        build_rag_prompt,
        build_retriever,
        build_vector_store,
        compact_documents,
        embedding_runtime_config,
        format_documents,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents,
    )


def main() -> None:
    options = parse_runtime_options("RAG From Scratch Part 4：Generation")

    chunks = split_documents(
        load_source_documents(options.use_web_source),
        chunk_size=300,
        chunk_overlap=50,
    )
    embeddings = build_embeddings(mode=options.embedding_mode)
    vector_store = build_vector_store(chunks, embeddings=embeddings)
    retriever = build_retriever(vector_store, k=2)

    # 先显式展示 Part 3 返回的 list[Document] 如何变为 prompt 的 {context} 文本。
    retrieved_documents = retriever.invoke(DEFAULT_QUESTION)
    prompt = build_rag_prompt()
    manual_chain = prompt | build_chat_model(use_live=options.use_live) | StrOutputParser()
    manual_answer = manual_chain.invoke(
        {
            "context": format_documents(retrieved_documents),
            "question": DEFAULT_QUESTION,
        }
    )

    # 再复用公共函数组成真正的固定两步 RAG：问题一定先经过 retriever。
    rag_answer = build_rag_chain(retriever, use_live=options.use_live).invoke(
        DEFAULT_QUESTION
    )

    print_json(
        "Part 4 - Generation",
        {
            "official_tutorial": OFFICIAL_TUTORIAL_URL,
            "current_api_docs": CURRENT_RETRIEVAL_DOCS_URL,
            "embedding": embedding_runtime_config(options.embedding_mode),
            "generation_mode": "online chat model" if options.use_live else "offline extractive",
            "manual_generation": {
                "chain": "prompt | model | StrOutputParser",
                "retrieved_documents": compact_documents(retrieved_documents),
                "formatted_context": format_documents(retrieved_documents),
                "answer": manual_answer,
            },
            "two_step_rag": {
                "chain": "question -> retriever -> format_documents -> prompt -> model -> StrOutputParser",
                "answer": rag_answer,
            },
        },
    )


if __name__ == "__main__":
    main()
