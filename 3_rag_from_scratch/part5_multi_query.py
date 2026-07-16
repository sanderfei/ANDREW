"""Part 5：基于官方 Multi Query 课程，可选用在线模型改写查询并合并召回。"""

from __future__ import annotations

import json
import re

try:
    from ._common import (
        DEFAULT_QUESTION,
        OFFICIAL_MULTI_QUERY_URL,
        ChatPromptTemplate,
        Document,
        RunnableLambda,
        StrOutputParser,
        build_chat_model,
        build_embeddings,
        build_rag_prompt,
        build_retriever,
        build_vector_store,
        compact_documents,
        embedding_runtime_config,
        format_documents,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents_token_aware,
        zhipu_runtime_config,
    )
except ImportError:
    from _common import (
        DEFAULT_QUESTION,
        OFFICIAL_MULTI_QUERY_URL,
        ChatPromptTemplate,
        Document,
        RunnableLambda,
        StrOutputParser,
        build_chat_model,
        build_embeddings,
        build_rag_prompt,
        build_retriever,
        build_vector_store,
        compact_documents,
        embedding_runtime_config,
        format_documents,
        load_source_documents,
        parse_runtime_options,
        print_json,
        split_documents_token_aware,
        zhipu_runtime_config,
    )


QUESTION = "What is task decomposition for LLM agents?"
MULTI_QUERY_PROMPT = ChatPromptTemplate.from_template(
    """You are an assistant that improves vector retrieval.
Generate five different search queries for the user question below.
Keep the original intent, use different wording or perspectives, and output one query per line.
Do not add explanations or numbering.

Question: {question}
"""
)

MULTI_QUERY_DOCUMENTS = [
    Document(
        page_content="Task decomposition breaks a complex task into smaller manageable steps before execution.",
        metadata={"source": "task-decomposition.md", "topic": "decomposition"},
    ),
    Document(
        page_content="An LLM agent can plan subtasks first, then select a tool for each planned subtask.",
        metadata={"source": "agent-planning.md", "topic": "planning"},
    ),
    Document(
        page_content="Breaking a large objective into a sequence of small goals makes autonomous work easier to monitor.",
        metadata={"source": "agent-goals.md", "topic": "goals"},
    ),
    Document(
        page_content="Retrieval augmented generation injects external documents into the model context before answering.",
        metadata={"source": "rag-overview.md", "topic": "rag"},
    ),
    Document(
        page_content="Docker packages an application and its dependencies into a reproducible container image.",
        metadata={"source": "deployment.md", "topic": "deployment"},
    ),
]


def _clean_query(line: str) -> str:
    return re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()


def parse_query_lines(text: str, original_question: str) -> list[str]:
    """清理 GLM 可能输出的序号，并保序去重。"""

    candidates = [original_question]
    candidates.extend(_clean_query(line) for line in text.splitlines())
    unique: list[str] = []
    seen: set[str] = set()
    for query in candidates:
        normalized = query.casefold().strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(query.strip())
    return unique[:6]


def build_query_variants(question: str, *, use_live: bool) -> list[str]:
    if not use_live:
        offline_variants = """
How do LLM agents plan subtasks before acting?
How can an autonomous agent break a large objective into smaller goals?
What planning strategy divides complex agent work into manageable steps?
Why should an agent decompose work before selecting tools?
"""
        return parse_query_lines(offline_variants, question)

    generated = (
        MULTI_QUERY_PROMPT
        | build_chat_model(use_live=True)
        | StrOutputParser()
    ).invoke({"question": question})
    return parse_query_lines(generated, question)


def document_key(document: Document) -> str:
    metadata = json.dumps(document.metadata, ensure_ascii=False, sort_keys=True, default=str)
    return f"{document.page_content}\n{metadata}"


def unique_union(document_lists: list[list[Document]]) -> list[Document]:
    """对应官方 get_unique_union，但保留首次命中顺序。"""

    unique: list[Document] = []
    seen: set[str] = set()
    for documents in document_lists:
        for document in documents:
            key = document_key(document)
            if key in seen:
                continue
            seen.add(key)
            unique.append(document)
    return unique


def main() -> None:
    options = parse_runtime_options("RAG From Scratch Part 5：Multi Query")
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
    retriever = build_retriever(vector_store, k=2)

    query_generator = RunnableLambda(
        lambda value: build_query_variants(str(value), use_live=options.use_live)
    )
    queries = query_generator.invoke(question)
    # 保留官方 retriever.map() 的数据流，但复用已生成的 queries，
    # 避免 live 模式为了打印查询而额外调用一次 GLM。
    per_query_documents = (
        RunnableLambda(lambda _: queries) | retriever.map()
    ).invoke(question)
    merged_documents = unique_union(per_query_documents)
    single_query_documents = retriever.invoke(question)

    answer_chain = build_rag_prompt() | build_chat_model(use_live=options.use_live) | StrOutputParser()
    answer = answer_chain.invoke(
        {
            "context": format_documents(merged_documents),
            "question": question,
        }
    )

    print_json(
        "Part 5 - Multi Query",
        {
            "official_tutorial": OFFICIAL_MULTI_QUERY_URL,
            "embedding": embedding_runtime_config(options.embedding_mode),
            "query_generation_mode": "online chat model" if options.use_live else "offline fixed query variants",
            "answer_generation_mode": "online chat model" if options.use_live else "offline extractive",
            "glm_config": (
                zhipu_runtime_config()
                if options.use_live or options.embedding_mode == "glm"
                else None
            ),
            "question": question,
            "generated_queries": queries,
            "single_query_documents": compact_documents(single_query_documents),
            "per_query_retrieval": [
                {
                    "query": query,
                    "documents": compact_documents(retrieved),
                }
                for query, retrieved in zip(queries, per_query_documents)
            ],
            "unique_union_count": len(merged_documents),
            "unique_union_documents": compact_documents(merged_documents),
            "answer": answer,
        },
    )


if __name__ == "__main__":
    main()
