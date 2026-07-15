"""Markdown/PDF 摄取；保持来源元数据以支撑稳定引用。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document


SUPPORTED_SUFFIXES = {".md", ".markdown", ".pdf"}


class SourceLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedSource:
    source: str
    source_sha256: str
    documents: list[Document]


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _markdown_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback


def _load_markdown(path: Path, source: str, source_sha256: str) -> list[Document]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    return [
        Document(
            page_content=text,
            metadata={
                "source": source,
                "source_type": "markdown",
                "title": _markdown_title(text, path.stem),
                "source_sha256": source_sha256,
            },
        )
    ]


def _load_pdf(path: Path, source: str, source_sha256: str) -> list[Document]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SourceLoadError("读取 PDF 需要 pypdf；请安装 requirements.txt。") from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # pypdf 的异常类型会随版本变化。
        raise SourceLoadError(f"无法读取 PDF {source}: {exc}") from exc

    documents: list[Document] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        documents.append(
            Document(
                page_content=text,
                metadata={
                    "source": source,
                    "source_type": "pdf",
                    "title": path.stem,
                    "page": page_number,
                    "source_sha256": source_sha256,
                },
            )
        )
    return documents


def load_sources(source_dir: Path) -> list[LoadedSource]:
    """先完整读取所有来源；任一失败时不返回半成品，避免索引半更新。"""

    if not source_dir.exists() or not source_dir.is_dir():
        raise SourceLoadError(f"知识库目录不存在或不是目录：{source_dir}")

    loaded: list[LoadedSource] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        source = path.relative_to(source_dir).as_posix()
        raw = path.read_bytes()
        digest = _sha256(raw)
        if path.suffix.lower() in {".md", ".markdown"}:
            documents = _load_markdown(path, source, digest)
        else:
            documents = _load_pdf(path, source, digest)
        loaded.append(LoadedSource(source, digest, documents))
    return loaded
