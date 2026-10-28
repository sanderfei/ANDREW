"""私有化部署助手 Web 入口，提供文本工作流、文件录入与片段检索。"""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from hashlib import sha256
import json
import mimetypes

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from adapters.web_installer import WebInstallerAdapter
from config import Settings
from contracts import (AssistantRequest, AssistantResponse, IngestRequest, VectorSearchRequest,
                       ConnectionRequest, DiagnosticsRequest, VerificationRequest, FeedbackRequest)
from services.documents import DocumentCatalog
from services.vector_service import VectorService
from workflows.assistant import AssistantWorkflow, WorkflowExecutionError
from services.business_runtime import SessionBusyError
from services.remote_diagnostics import CHECK_CATALOG, RemoteDiagnosticError


def create_app(workflow: AssistantWorkflow | None = None) -> FastAPI:
    settings = Settings()
    catalog = DocumentCatalog(settings.document_dir)
    workflow = workflow or AssistantWorkflow()
    installer = WebInstallerAdapter()
    @asynccontextmanager
    async def lifespan(application):
        workflow.business.start()
        try:
            yield
        finally:
            workflow.close()

    application = FastAPI(title="私有化部署助手", version="0.2.0", lifespan=lifespan)
    application.state.workflow = workflow
    application.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(settings.static_dir / "index.html")

    @application.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "mode": workflow.settings.mode, "agent_enabled": workflow.settings.mode == "glm",
                "workflow_enabled": True, "persistent_checkpoints": True}

    @application.get("/api/workspace")
    def workspace() -> dict:
        return {
            "name": "私有化部署助手",
            "mode": workflow.settings.mode,
            "support_matrix": settings.support_matrix,
            "documents": catalog.list_documents(),
            "capabilities": {
                "document_download": True,
                "cluster_connection": False,
                "rag": workflow.settings.mode == "glm",
                "evaluation": False,
                "vector_retrieval": True,
                "langgraph_workflow": True,
                "remote_diagnostics": True,
                "resolution_verification": True,
                "automatic_case_archive": True,
                "persistent_checkpoints": True,
                "execution_metrics": True,
                "langfuse_reporting": workflow.business.settings.langfuse_enabled,
            },
        }

    @application.get("/api/documents")
    def documents() -> dict:
        return {"items": catalog.list_documents(), "index_status": "not_checked"}

    @application.get("/api/documents/{document_id}/download")
    def download(document_id: str) -> FileResponse:
        path = catalog.resolve(document_id)
        if path is None:
            raise HTTPException(status_code=404, detail="文档不存在。")
        return FileResponse(
            path,
            filename=path.name,
            media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )

    @application.get("/api/clusters")
    def clusters() -> dict:
        return installer.list_clusters()

    @application.post("/api/assistant/messages", response_model=AssistantResponse)
    def assistant(payload: AssistantRequest) -> AssistantResponse:
        try:
            return AssistantResponse.model_validate(workflow.invoke(payload))
        except WorkflowExecutionError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None
        except SessionBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @application.get("/api/assistant/sessions")
    def sessions() -> dict:
        return {"items": workflow.sessions()}

    @application.post("/api/assistant/connections")
    def authorize_connection(payload: ConnectionRequest) -> dict:
        try:
            return workflow.business.remote.create_connection(
                payload.thread_id, payload.host, payload.username, payload.password.get_secret_value(),
                port=payload.port, host_key_sha256=payload.host_key_sha256)
        except RemoteDiagnosticError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @application.delete("/api/assistant/connections/{connection_id}")
    def revoke_connection(connection_id: str, thread_id: str) -> dict:
        try:
            workflow.business.remote.revoke(connection_id, thread_id)
            return {"status": "revoked"}
        except RemoteDiagnosticError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @application.get("/api/assistant/diagnostics/catalog")
    def diagnostics_catalog() -> dict:
        return {"checks": CHECK_CATALOG}

    @application.post("/api/assistant/diagnostics")
    def collect_diagnostics(payload: DiagnosticsRequest) -> dict:
        try:
            return workflow.collect_evidence(payload.thread_id, payload.connection_id, payload.checks)
        except RemoteDiagnosticError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except SessionBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @application.post("/api/assistant/verification", response_model=AssistantResponse)
    def verify_resolution(payload: VerificationRequest) -> AssistantResponse:
        fingerprint = sha256(json.dumps(payload.model_dump(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        try:
            return workflow.invoke(AssistantRequest(
                thread_id=payload.thread_id, question="用户提交实际处理步骤与原故障功能复测结果。",
                request_id=f"verify-{fingerprint}", action="verify_resolution", verification=payload))
        except WorkflowExecutionError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None
        except SessionBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None

    @application.post("/api/assistant/feedback")
    def feedback(payload: FeedbackRequest) -> dict:
        try:
            return workflow.business.observability.record_feedback(payload.trace_id, payload.score, payload.comment)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    @application.get("/api/assistant/metrics")
    def metrics(thread_id: str | None = None) -> dict:
        return workflow.business.observability.metrics(thread_id)

    @application.get("/api/assistant/observability")
    def observability_status(check_connection: bool = False) -> dict:
        return workflow.business.observability.status(check_connection=check_connection)

    @application.get("/api/assistant/index-jobs")
    def index_jobs(thread_id: str | None = None) -> dict:
        return {"items": workflow.business.knowledge.list_jobs(thread_id)}

    @application.post("/api/assistant/index-jobs/retry")
    def retry_index_jobs() -> dict:
        workflow.business.wake_indexer()
        return {"status": "scheduled", "automatic_worker": workflow.business.settings.auto_index}

    @application.get("/api/assistant/graph")
    def assistant_graph() -> dict:
        return {"mode": workflow.settings.mode, "mermaid": workflow.mermaid()}

    @application.get("/api/evaluations")
    def evaluations() -> dict:
        return {"status": "ready", "items": workflow.business.observability.list_traces(),
                "metrics": workflow.business.observability.metrics(),
                "langfuse": workflow.business.observability.status(),
                "langfuse_reporting": workflow.business.settings.langfuse_enabled}

    @application.get("/api/vector/status")
    def vector_status() -> dict:
        service = None
        try:
            service = VectorService()
            return service.status()
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        finally:
            if service is not None:
                service.close()

    @application.post("/api/documents/ingest")
    def ingest_document(payload: IngestRequest) -> dict:
        service = None
        try:
            service = VectorService()
            return service.ingest(payload.file_path, payload.metadata.model_dump(exclude_none=True))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except Exception:
            raise HTTPException(status_code=503, detail="录入未完成，请检查数据库、本地向量模型和文件格式。") from None
        finally:
            if service is not None:
                service.close()

    @application.post("/api/vector/search")
    def vector_search(payload: VectorSearchRequest) -> dict:
        service = None
        try:
            service = VectorService()
            return service.search(payload.query, payload.top_k, {
                "kubernetes_versions": payload.kubernetes_version,
                "operating_systems": payload.operating_system,
                "install_modes": payload.install_mode,
            })
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except Exception:
            raise HTTPException(status_code=503, detail="检索未完成，请检查数据库和本地向量模型。") from None
        finally:
            if service is not None:
                service.close()

    return application


# 启动命令：.venv/bin/python 7_private_deployment_assistant/app.py
# 参数枚举：--host 监听地址（默认 127.0.0.1）；--port 端口（默认 8070）。
def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8070)
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
