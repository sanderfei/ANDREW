"""Part 9：把受控 LangGraph 暴露为 invoke / stream / resume API。

FastAPI 是本地服务化适配，不是 LangGraph 托管平台替代品。本课重点是把
thread_id、暂停状态和恢复命令明确放进 HTTP 合同。

启动：
    .venv/bin/uvicorn \
      part9_fastapi_runtime:create_default_app \
      --factory --app-dir 5_langgraph_agentic_rag --port 8001
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from part8_controlled_multi_tool_graph import (
    ControlledAssistantService,
    build_default_service,
)


class InvokeRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(default=None, min_length=1, max_length=200)


class ResumeRequest(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=1000)


class AssistantResponse(BaseModel):
    request_id: str | None = None
    thread_id: str
    turn_count: int
    previous_question: str
    status: Literal["completed", "interrupted"]
    route: str
    answer: str
    answerable: bool
    grounded: bool
    citations: list[dict[str, Any]]
    metric_result: dict[str, Any] | None
    approved: bool | None
    reviewer_note: str
    audit_log: list[dict[str, Any]]
    interrupts: list[Any]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    runtime: str
    capabilities: list[str]


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid4().hex)


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "value"):
        return getattr(value, "value")
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return str(value)


def _sse(event: dict[str, Any]) -> str:
    event_type = str(event.get("type", "message"))
    payload = {
        "type": event_type,
        "namespace": list(event.get("ns", ())),
        "data": event.get("data"),
    }
    data = json.dumps(
        payload,
        ensure_ascii=False,
        default=_json_default,
    )
    return f"event: {event_type}\ndata: {data}\n\n"


def create_app(service: ControlledAssistantService) -> FastAPI:
    app = FastAPI(
        title="Andrew Controlled LangGraph Tutorial",
        version="0.2.0",
        description=("目录 5 的受控 RAG、只读 SQL、Streaming 与 HITL 恢复接口。"),
    )
    app.state.service = service

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or uuid4().hex
        # call_next(request) 返回可等待对象；await 取得后续请求链的 Response。
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            runtime="in_process_langgraph",
            capabilities=[
                "invoke",
                "sse_stream",
                "thread_resume",
                "rag",
                "readonly_sql",
                "human_approval",
            ],
        )

    @app.post("/v1/invoke", response_model=AssistantResponse)
    def invoke(
        payload: InvokeRequest,
        request: Request,
    ) -> AssistantResponse:
        try:
            result = service.ask(
                payload.question,
                thread_id=payload.thread_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        result["request_id"] = _request_id(request)
        return AssistantResponse.model_validate(result)

    @app.post("/v1/stream")
    def stream(payload: InvokeRequest) -> StreamingResponse:
        def generate():
            try:
                for event in service.stream(
                    payload.question,
                    thread_id=payload.thread_id,
                ):
                    yield _sse(event)
            except ValueError as exc:
                yield _sse(
                    {
                        "type": "error",
                        "ns": (),
                        "data": {"detail": str(exc)},
                    }
                )

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post(
        "/v1/threads/{thread_id}/resume",
        response_model=AssistantResponse,
    )
    def resume(
        thread_id: str,
        payload: ResumeRequest,
        request: Request,
    ) -> AssistantResponse:
        config = service.config(thread_id)
        snapshot = service.graph.get_state(config)
        if not snapshot.values:
            raise HTTPException(status_code=404, detail="thread_id 不存在。")
        is_paused = any(getattr(task, "interrupts", ()) for task in snapshot.tasks)
        if not is_paused:
            raise HTTPException(
                status_code=409,
                detail="该线程当前没有等待恢复的 interrupt。",
            )
        try:
            result = service.resume(
                thread_id,
                decision=payload.decision,
                note=payload.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        result["request_id"] = _request_id(request)
        return AssistantResponse.model_validate(result)

    return app


def create_default_app() -> FastAPI:
    """供 uvicorn ``--factory`` 使用，避免 import 时立刻建立索引。"""

    return create_app(build_default_service())


# 启动命令：.venv/bin/python 5_langgraph_agentic_rag/part9_fastapi_runtime.py
# 参数枚举：无 CLI 参数；固定监听 127.0.0.1:8001，单 worker。
def main() -> None:
    import uvicorn

    uvicorn.run(create_default_app(), host="127.0.0.1", port=8001, workers=1)


if __name__ == "__main__":
    main()
