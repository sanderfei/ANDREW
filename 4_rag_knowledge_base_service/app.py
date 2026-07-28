"""FastAPI 入口：健康检查、增量重建、固定两步 RAG 问答。"""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request

from config import Settings
from contracts import (
    AskRequest,
    AskResponse,
    HealthResponse,
    ReindexRequest,
    ReindexResponse,
)
from indexer import IndexConflictError, IndexingError
from kb_service import KnowledgeBaseService
from loaders import SourceLoadError


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid4().hex)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    service = KnowledgeBaseService(settings)
    app = FastAPI(
        title="Andrew RAG Knowledge Base Service",
        version="0.1.0",
        description="离线优先、带稳定引用与增量索引的两步 RAG 学习项目。",
    )
    app.state.service = service

    # 一个 FastAPI HTTP 中间件：每次收到请求时，为请求分配一个唯一的 request_id，并返回给客户端，方便追踪一次完整请求。
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        return service.health(request_id=_request_id(request))

    @app.post("/v1/reindex", response_model=ReindexResponse)
    def reindex(payload: ReindexRequest, request: Request) -> ReindexResponse:
        try:
            stats = service.reindex(reset=payload.reset)
        except IndexConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (SourceLoadError, IndexingError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ReindexResponse(request_id=_request_id(request), **stats.to_dict())

    @app.post("/v1/ask", response_model=AskResponse)
    def ask(payload: AskRequest, request: Request) -> AskResponse:
        try:
            return service.ask(
                question=payload.question.strip(),
                top_k=payload.top_k,
                request_id=_request_id(request),
            )
        except IndexingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


app = create_app()


# 在仓库根目录运行（mode=live，embedding_mode=local）：
# RAG_MODE=live RAG_EMBEDDING_MODE=local \
#   .venv/bin/python 4_rag_knowledge_base_service/app.py
def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)


if __name__ == "__main__":
    main()
