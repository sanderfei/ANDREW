"""共用录入与搜索逻辑，数据库差异只存在于存储适配层。"""

from dataclasses import replace
import threading

from pathlib import Path

from config import PROJECT_DIR, Settings, load_vector_settings
from contracts import DocumentMetadata
from services.embedding import get_embedding
from services.ingestion import SUPPORTED_SUFFIXES, read_document, chunk_document
from vectorstores.base import VectorChunk
from vectorstores.factory import create_vector_store


INDEX_LOCK = threading.Lock()


class VectorService:
    def __init__(self, backend: str | None = None, config_path=None):
        self.settings = load_vector_settings(config_path)
        if backend is not None:
            if backend not in {"qdrant", "pgvector"}:
                raise ValueError("未知向量后端。")
            self.settings = replace(self.settings, backend=backend)
        self.store = create_vector_store(self.settings)

    def status(self) -> dict:
        try:
            state = self.store.status()
        except Exception:
            state = {"connected": False, "initialized": False, "chunks": 0, "documents": {},
                     "message": "数据库未连接，请检查本地服务、config.toml 和数据库环境文件。"}
        return {"backend": self.settings.backend, "namespace": self.store.namespace,
                "model": self.settings.model, "dimension": self.settings.dimension,
                "retrieval_mode": "dense_vector", **state}

    def ingest(self, file_path: str, metadata: dict | None = None) -> dict:
        if not INDEX_LOCK.acquire(blocking=False):
            raise RuntimeError("已有文档录入任务正在运行，请稍后重试。")
        try:
            path = (PROJECT_DIR / Path(file_path).expanduser()).resolve()
            if not any(path.is_relative_to(root) for root in self.settings.allowed_roots):
                raise ValueError("文件不在 ingestion.allowed_roots 允许的目录中。")
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                raise ValueError("文件不存在或格式不支持；当前支持 DOCX、Markdown、TXT。")
            source_root = Settings().document_dir.resolve()
            root = source_root if path.is_relative_to(source_root) else Path(path.anchor)
            document = read_document(path, root)
            checked = DocumentMetadata.model_validate(metadata or {}).model_dump(exclude_none=True)
            document.metadata.update(checked)
            DocumentMetadata.model_validate({key: document.metadata[key] for key in DocumentMetadata.model_fields})
            chunks = chunk_document(document, self.settings.chunk_size, self.settings.chunk_overlap)
            if not chunks:
                raise ValueError("文档未提取出正文，请先检查文件内容。")
            embedder = get_embedding(self.settings)
            self.store.initialize()
            vectors = embedder.documents([chunk["content"] for chunk in chunks])
            self.store.replace_document(document.id, [VectorChunk(**chunk, vector=vector) for chunk, vector in zip(chunks, vectors, strict=True)])
            return {"backend": self.settings.backend, "documents": 1, "document_id": document.id,
                    "chunks": len(chunks),
                    "images_unprocessed": document.images_unprocessed,
                    "message": "正文和表格已录入；截图未执行 OCR。重复录入会替换同一文档的片段。"}
        finally:
            INDEX_LOCK.release()

    def search(self, query: str, limit: int = 5, filters: dict | None = None) -> dict:
        query = query.strip()
        if not query or len(query) > 2000:
            raise ValueError("检索问题必须为 1～2000 个非空字符。")
        if not 1 <= limit <= 20:
            raise ValueError("返回数量必须为 1～20。")
        if not self.store.status()["initialized"]:
            raise ValueError("当前后端尚未录入文档，请先执行录入。")
        selected = filters or {}
        if set(selected) - {"kubernetes_versions", "operating_systems", "install_modes"}:
            raise ValueError("不支持的检索过滤字段。")
        vector = get_embedding(self.settings).query(query)
        items = self.store.search(vector, limit, selected)
        return {"backend": self.settings.backend, "query": query, "items": items,
                "message": "返回的是文档片段及余弦相似度，不是模型答案或正确率。"}

    def close(self) -> None:
        self.store.close()
