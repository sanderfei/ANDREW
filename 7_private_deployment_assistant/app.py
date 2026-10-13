"""私有化部署助手 Web 入口，提供显式文件录入与片段检索；不启动 Agent。"""

from __future__ import annotations

import argparse
import mimetypes

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from adapters.web_installer import WebInstallerAdapter
from config import Settings
from contracts import AssistantRequest, IngestRequest, VectorSearchRequest
from services.documents import DocumentCatalog
from services.vector_service import VectorService
from workflows.assistant import AssistantWorkflow, WorkflowNotReady


def create_app() -> FastAPI:
    settings = Settings()
    catalog = DocumentCatalog(settings.document_dir)
    workflow = AssistantWorkflow()
    installer = WebInstallerAdapter()
    application = FastAPI(title="私有化部署助手", version="0.1.0")
    application.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(settings.static_dir / "index.html")

    @application.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "mode": "scaffold", "agent_enabled": False}

    @application.get("/api/workspace")
    def workspace() -> dict:
        return {
            "name": "私有化部署助手",
            "mode": "scaffold",
            "support_matrix": settings.support_matrix,
            "documents": catalog.list_documents(),
            "capabilities": {
                "document_download": True,
                "cluster_connection": False,
                "rag": False,
                "evaluation": False,
                "vector_retrieval": True,
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

    @application.post("/api/assistant/messages")
    def assistant(payload: AssistantRequest) -> JSONResponse:
        try:
            workflow.invoke(payload)
        except WorkflowNotReady as exc:
            return JSONResponse(
                status_code=501,
                content={
                    "status": "not_implemented",
                    "message": str(exc),
                    "thread_id": payload.thread_id,
                },
            )
        raise HTTPException(status_code=501, detail="智能问答尚未接入。")

    @application.get("/api/evaluations")
    def evaluations() -> dict:
        return {
            "status": "not_implemented",
            "items": [],
            "message": "评测与 Langfuse 尚未接入。",
        }

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
