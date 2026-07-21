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


QUESTION = "对于 LLM Agent，什么是任务分解？"
MULTI_QUERY_PROMPT = ChatPromptTemplate.from_template(
    """你是一名负责提升向量检索效果的助手。
请针对下面的用户问题生成五种不同的检索查询。
保持原始意图不变，使用不同的措辞或视角，每行只输出一个查询。
不要添加解释或编号。

问题：{question}
"""
)

MULTI_QUERY_DOCUMENTS = [
    Document(
        page_content="任务分解是在执行前把复杂任务拆分成更小、更易管理的步骤。",
        metadata={"source": "task-decomposition.md", "topic": "decomposition"},
    ),
    Document(
        page_content="LLM Agent 可以先规划子任务，再为每个已规划的子任务选择合适的工具。",
        metadata={"source": "agent-planning.md", "topic": "planning"},
    ),
    Document(
        page_content="把一个大型目标拆成一系列小目标，可以让自主工作过程更容易监控。",
        metadata={"source": "agent-goals.md", "topic": "goals"},
    ),
    Document(
        page_content="检索增强生成（RAG）会在回答前，把外部文档注入模型的上下文。",
        metadata={"source": "rag-overview.md", "topic": "rag"},
    ),
    Document(
        page_content="Docker 会把应用程序及其依赖打包成可复现的容器镜像。",
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
LLM Agent 在行动前如何规划子任务？
自主 Agent 如何把一个大型目标拆分成更小的目标？
哪种规划策略会把复杂的 Agent 工作拆分成易于管理的步骤？
为什么 Agent 应该在选择工具前先分解任务？
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


# question: str
#   ↓ build_query_variants()第一次调用 Chat Model 生成多个查询表达
# queries: list[str]
#   ↓ retriever.map()每个查询分别执行向量相似度搜索
# per_query_documents: list[list[Document]]
#   ↓ unique_union()合并并去重 Document
# merged_documents: list[Document]
#   ↓ format_documents()
# context: str 第二次调用 Chat Model
#   ↓ Prompt → Model → StrOutputParser
# answer: str
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

    # RunnableLambda(...)：把普通 Python 函数包装成 LangChain 的 Runnable。
    # 包装后可以使用 .invoke()、.batch()、.map() 以及 | 管道组合；即使普通
    # Python 函数返回固定字符串，invoke() 也会返回该字符串。
    # invoke(question) 会把 question 传给 lambda 的 value 参数。
    query_generator = RunnableLambda(
        lambda value: build_query_variants(str(value), use_live=options.use_live)
    )
    queries = query_generator.invoke(question)
    # 保留官方 retriever.map() 的数据流，但复用已生成的 queries，
    # 避免 live 模式为了打印查询而额外调用一次 GLM。
    # question
    #   ↓ 顺序执行
    # RunnableLambda(lambda _: queries)
    #   ↓ 返回 queries: list[str]
    # retriever.map()
    #   ├─ query 1 → retriever.invoke(query 1) ┐
    #   ├─ query 2 → retriever.invoke(query 2) ├─ 默认线程池并发
    #   ├─ query 3 → retriever.invoke(query 3) │
    #   └─ query 4 → retriever.invoke(query 4) ┘
    #   ↓ 等全部查询完成
    # list[list[Document]] 最后仍按 query 1、query 2 的输入顺序返回。
    per_query_documents = (
        RunnableLambda(lambda _: queries) | retriever.map()  # 外层顺序，内层并发
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
