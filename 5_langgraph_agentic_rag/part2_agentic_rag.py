"""Part 2：运行本地受控版 LangGraph Agentic RAG。

确定性离线教学：
    .venv/bin/python 5_langgraph_agentic_rag/part2_agentic_rag.py

本地 MiniLM 检索 + 在线智谱兼容模型：
    .venv/bin/python 5_langgraph_agentic_rag/part2_agentic_rag.py \
      --mode live --embedding local
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agentic_rag import (
    OFFICIAL_TUTORIAL,
    build_agentic_rag_graph,
    initial_state,
    public_result,
)
from local_rag_adapter import (
    LocalKnowledgeRetriever,
    build_chat_model,
    build_tutorial_settings,
)


DEFAULT_QUESTION = "本地知识库默认使用什么 Embedding 模型？"


def run(
    *,
    question: str,
    mode: str,
    embedding_mode: str,
    reset: bool,
    max_rewrites: int,
    runtime_dir: Path | None,
) -> dict[str, object]:
    settings = build_tutorial_settings(
        mode=mode,  # type: ignore[arg-type]
        embedding_mode=embedding_mode,  # type: ignore[arg-type]
        runtime_dir=runtime_dir,
    )
    retriever = LocalKnowledgeRetriever(settings)
    index_stats = retriever.ensure_index(reset=reset)
    model = build_chat_model(settings)
    graph = build_agentic_rag_graph(
        retriever,
        model=model,
        top_k=settings.default_top_k,
        max_context_chars=settings.max_context_chars,
    )
    final_state = graph.invoke(
        initial_state(question, max_rewrites=max_rewrites)
    )
    return {
        "official_source": OFFICIAL_TUTORIAL,
        "mode": settings.mode,
        "embedding_mode": settings.embedding_mode,
        "chat_model": settings.chat_model if settings.is_live else None,
        "index": index_stats.to_dict(),
        "result": public_result(final_state),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="运行官方教程的本地受控 Agentic RAG 适配版"
    )
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument(
        "--mode",
        choices=("offline", "live"),
        default="offline",
        help="offline 使用确定性节点；live 使用根目录 .env 中的聊天模型。",
    )
    parser.add_argument(
        "--embedding",
        choices=("hash", "local", "glm"),
        default="hash",
        help="默认 hash 便于无网络学习；真实运行推荐 local。",
    )
    parser.add_argument(
        "--max-rewrites",
        type=int,
        default=1,
        help="检索证据不足时最多改写问题的次数。",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="显式清空目录 5 当前 embedding 模式的索引并完整重建。",
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        help="可选运行目录；默认使用 5_langgraph_agentic_rag/runtime/<embedding>。",
    )
    args = parser.parse_args(argv)
    payload = run(
        question=args.question,
        mode=args.mode,
        embedding_mode=args.embedding,
        reset=args.reset,
        max_rewrites=args.max_rewrites,
        runtime_dir=args.runtime_dir,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

