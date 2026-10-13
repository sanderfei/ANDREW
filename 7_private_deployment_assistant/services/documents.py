"""原始文档目录；当前不解析、切块或生成向量。"""

from hashlib import sha256
from pathlib import Path

from services.ingestion import source_paths


class DocumentCatalog:
    def __init__(self, directory: Path):
        self.directory = directory

    def document_id(self, path: Path) -> str:
        return sha256(path.relative_to(self.directory).as_posix().encode("utf-8")).hexdigest()[:16]

    def list_documents(self) -> list[dict]:
        return [
            {
                "id": self.document_id(path),
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "format": path.suffix.lstrip(".").upper(),
                "category": "私有化部署",
                "modes": ["在线", "离线"],
                "index_status": "not_checked",
                "download_url": f"/api/documents/{self.document_id(path)}/download",
            }
            for path in source_paths(self.directory)
        ]

    def resolve(self, document_id: str) -> Path | None:
        for path in source_paths(self.directory):
            if (
                path.is_file()
                and not path.is_symlink()
                and self.document_id(path) == document_id
            ):
                return path
        return None
