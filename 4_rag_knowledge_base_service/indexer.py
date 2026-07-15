"""持久化 Chroma 索引、稳定 chunk ID 与增量 manifest。"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import Settings
from embeddings import build_embeddings, embedding_identity
from loaders import LoadedSource, load_sources


class IndexConflictError(RuntimeError):
    """配置指纹变化时，要求调用方明确确认 reset。"""


class IndexingError(RuntimeError):
    pass


@dataclass(frozen=True)
class IndexStats:
    reset: bool
    scanned_files: int
    added_files: int
    updated_files: int
    unchanged_files: int
    removed_files: int
    indexed_chunks: int
    deleted_chunks: int
    total_indexed_chunks: int
    index_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChunkedSource:
    source: str
    source_sha256: str
    documents: list[Document]
    chunk_ids: list[str]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_chunk_id(
    *, source: str, page: int | None, chunk_index: int, content_sha256: str
) -> str:
    payload = "\0".join((source, str(page or ""), str(chunk_index), content_sha256))
    return _sha256(payload)


class IncrementalIndexer:
    """将来源文件 hash 与 Chroma 文档 ID 显式对应，支持增量同步。"""

    manifest_version = 1

    def __init__(self, settings: Settings):
        self.settings = settings
        self._embeddings = build_embeddings(settings)

    @property
    def index_fingerprint(self) -> str:
        payload = {
            "chunk_size": self.settings.chunk_size,
            "chunk_overlap": self.settings.chunk_overlap,
            "embedding": embedding_identity(self.settings),
            "collection": self.settings.collection_name,
        }
        return _sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False))[:20]

    def _store(self):
        from langchain_chroma import Chroma

        self.settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        return Chroma(
            collection_name=self.settings.collection_name,
            embedding_function=self._embeddings,
            persist_directory=str(self.settings.chroma_dir),
            collection_metadata={"hnsw:space": "cosine"},
        )

    def _empty_manifest(self) -> dict[str, Any]:
        return {
            "format_version": self.manifest_version,
            "index_fingerprint": self.index_fingerprint,
            "sources": {},
        }

    def read_manifest(self) -> dict[str, Any]:
        path = self.settings.manifest_path
        if not path.exists():
            return self._empty_manifest()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexingError(f"无法读取索引 manifest：{path}") from exc
        if payload.get("format_version") != self.manifest_version:
            raise IndexingError("manifest 格式版本不兼容；请使用 reset=true 重建。")
        if not isinstance(payload.get("sources"), dict):
            raise IndexingError("manifest 的 sources 格式无效。")
        return payload

    def _write_manifest(self, payload: dict[str, Any]) -> None:
        self.settings.runtime_dir.mkdir(parents=True, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(
            prefix=".index_manifest.", suffix=".tmp", dir=self.settings.runtime_dir
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temporary_path, self.settings.manifest_path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def _chunk_source(self, loaded: LoadedSource) -> ChunkedSource:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            add_start_index=True,
        )
        raw_chunks = splitter.split_documents(loaded.documents)
        documents: list[Document] = []
        chunk_ids: list[str] = []
        for chunk_index, raw_chunk in enumerate(raw_chunks):
            content = raw_chunk.page_content.strip()
            if not content:
                continue
            metadata = dict(raw_chunk.metadata)
            content_sha256 = _sha256(content)
            page = metadata.get("page")
            page_value = int(page) if isinstance(page, int) else None
            chunk_id = _stable_chunk_id(
                source=loaded.source,
                page=page_value,
                chunk_index=chunk_index,
                content_sha256=content_sha256,
            )
            metadata.update(
                {
                    "chunk_id": chunk_id,
                    "content_sha256": content_sha256,
                    "source_sha256": loaded.source_sha256,
                }
            )
            documents.append(Document(page_content=content, metadata=metadata))
            chunk_ids.append(chunk_id)
        return ChunkedSource(
            source=loaded.source,
            source_sha256=loaded.source_sha256,
            documents=documents,
            chunk_ids=chunk_ids,
        )

    @staticmethod
    def _batched(values: list[str] | list[Document], size: int = 100):
        for start in range(0, len(values), size):
            yield values[start : start + size]

    def _delete_ids(self, store, ids: Iterable[str]) -> int:
        ids_list = list(ids)
        for batch in self._batched(ids_list):
            store.delete(ids=batch)
        return len(ids_list)

    def _add_source_chunks(self, store, sources: Iterable[ChunkedSource]) -> int:
        added = 0
        for source in sources:
            for documents, ids in zip(
                self._batched(source.documents), self._batched(source.chunk_ids)
            ):
                store.add_documents(documents=documents, ids=ids)
                added += len(ids)
        return added

    def _manifest_source_entry(self, source: ChunkedSource) -> dict[str, Any]:
        return {
            "sha256": source.source_sha256,
            "chunk_count": len(source.chunk_ids),
            "chunk_ids": source.chunk_ids,
        }

    def reindex(self, *, reset: bool = False) -> IndexStats:
        """同步新增、变更和删除来源；所有来源可读取后才开始写向量库。"""

        loaded_sources = load_sources(self.settings.source_dir)
        chunked_sources = {
            source.source: self._chunk_source(source) for source in loaded_sources
        }
        old_manifest = self.read_manifest()
        old_sources: dict[str, dict[str, Any]] = old_manifest["sources"]
        fingerprint_changed = (
            bool(old_sources)
            and old_manifest.get("index_fingerprint") != self.index_fingerprint
        )
        if fingerprint_changed and not reset:
            raise IndexConflictError(
                "chunk 或 embedding 配置已变化；请使用 reset=true 显式重建索引。"
            )

        previous_sources = old_sources if not reset else {}
        current_names = set(chunked_sources)
        previous_names = set(previous_sources)
        changed_names = sorted(
            name
            for name, source in chunked_sources.items()
            if name not in previous_sources
            or previous_sources[name].get("sha256") != source.source_sha256
        )
        removed_names = sorted(previous_names - current_names)

        delete_ids: list[str] = []
        if reset:
            for entry in old_sources.values():
                delete_ids.extend(entry.get("chunk_ids", []))
        else:
            for name in changed_names + removed_names:
                delete_ids.extend(old_sources.get(name, {}).get("chunk_ids", []))

        store = self._store()
        deleted_chunks = self._delete_ids(store, delete_ids) if delete_ids else 0
        indexed_chunks = self._add_source_chunks(
            store, (chunked_sources[name] for name in changed_names)
        )

        new_manifest = self._empty_manifest()
        new_manifest["sources"] = {
            name: self._manifest_source_entry(source)
            for name, source in sorted(chunked_sources.items())
        }
        self._write_manifest(new_manifest)

        added_files = sum(name not in previous_sources for name in changed_names)
        updated_files = len(changed_names) - added_files
        total_chunks = sum(
            entry["chunk_count"] for entry in new_manifest["sources"].values()
        )
        return IndexStats(
            reset=reset,
            scanned_files=len(loaded_sources),
            added_files=added_files,
            updated_files=updated_files,
            unchanged_files=len(current_names) - len(changed_names),
            removed_files=len(removed_names),
            indexed_chunks=indexed_chunks,
            deleted_chunks=deleted_chunks,
            total_indexed_chunks=total_chunks,
            index_fingerprint=self.index_fingerprint,
        )

    def search(self, query: str, *, top_k: int):
        """当前 Chroma API 会返回 `(Document, relevance_score)`。"""

        return self._store().similarity_search_with_relevance_scores(query, k=top_k)
