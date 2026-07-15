"""可直接执行的知识库 CLI；与 FastAPI 复用同一服务层。"""

from __future__ import annotations

import argparse
import json
from uuid import uuid4

from config import Settings
from kb_service import KnowledgeBaseService


def _print(payload: object) -> None:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    elif hasattr(payload, "to_dict"):
        payload = payload.to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="本地 RAG 知识库服务 CLI")
    parser.add_argument(
        "--mode",
        choices=("offline", "live"),
        help="覆盖 RAG_MODE；默认读取环境变量（offline）。",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    reindex = subcommands.add_parser("reindex", help="增量摄取 data/source 中的 Markdown/PDF")
    reindex.add_argument(
        "--reset", action="store_true", help="配置指纹变化时清空并重建索引。"
    )

    ask = subcommands.add_parser("ask", help="向已索引知识库提问")
    ask.add_argument("question")
    ask.add_argument("--top-k", type=int, default=None)

    subcommands.add_parser("health", help="查看本地索引状态")

    serve = subcommands.add_parser("serve", help="启动 FastAPI 服务")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env(mode=args.mode)
    service = KnowledgeBaseService(settings)

    if args.command == "reindex":
        _print(service.reindex(reset=args.reset))
        return 0
    if args.command == "ask":
        top_k = args.top_k or settings.default_top_k
        _print(
            service.ask(
                question=args.question,
                top_k=top_k,
                request_id=uuid4().hex,
            )
        )
        return 0
    if args.command == "health":
        _print(service.health(request_id=uuid4().hex))
        return 0

    from app import create_app
    import uvicorn

    uvicorn.run(create_app(settings), host=args.host, port=args.port, workers=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
