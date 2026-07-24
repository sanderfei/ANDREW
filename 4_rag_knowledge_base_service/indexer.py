"""持久化 Chroma 索引、稳定 chunk ID 与增量 manifest。"""
# 把知识库文本转换成向量后保存起来，并建立能够快速寻找“最相似向量”的检索结构。
# Chroma：向量数据库。
# 索引：为了快速查找相似内容而建立的数据和检索结构。
# Embedding：负责把文本转换成向量。
# Chroma 本身不负责生成最终答案
# {
#     "id": "a5344d...",
#     "document": "本机默认 embedding 模型是 MiniLM。",
#     "metadata": {
#         "source": "local_runtime.md",
#         "start_index": 0,
#     },
#     "embedding": [0.012, -0.034, 0.018, ...],
# }
# 问题文本
#   ↓ embed_query()
# 问题的 384 维向量
#   ↓ Chroma 余弦近邻搜索
# 寻找距离最近的文档向量
#   ↓
# 返回对应的 Document

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


class IndexingError(RuntimeError):
    pass


class IndexConflictError(IndexingError):
    """配置指纹变化时，要求调用方明确确认 reset。"""

# IndexStats 是一次 reindex() 执行结束后的“统计报告对象”，不保存 Chroma 的文档或向量。
@dataclass(frozen=True)
class IndexStats:
    reset: bool  # 本次是否执行完整重建。
    scanned_files: int  # 本次扫描到的来源文件数。
    added_files: int  # 本次新增的来源文件数。
    updated_files: int  # 本次内容改变并重新索引的文件数。
    unchanged_files: int  # 本次没有变化的文件数。
    removed_files: int  # 本次已从来源目录删除的文件数。
    indexed_chunks: int  # 本次新增或重新写入 Chroma 的 chunk 数。
    deleted_chunks: int  # 本次从 Chroma 删除的旧 chunk 数。
    total_indexed_chunks: int  # 执行结束后整个索引的 chunk 总数。
    index_fingerprint: str  # 当前切块、Embedding 和 collection 的配置指纹。

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

# 自定义的 dataclass 对象，用来保存：一个来源文件完成切块以后产生的全部 chunk 和对应 ID。
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


# 当前知识库项目的“增量索引执行器”： 真正执行切块、比较、增删和查询的业务对象
# index_manifest.json
# ├── index_fingerprint     索引使用什么配置构建
# └── sources               索引中有哪些来源数据
#     ├── A.md
#     │   ├── sha256        文件内容是否变化
#     │   └── chunk_ids     对应哪些 Chroma chunk
#     └── B.md
#         ├── sha256
#         └── chunk_ids

# manifest.json 和 Chroma 数据通过 chunk_id 关联。
# index_manifest.json（管理账本）
#     source_sha256 + chunk_ids
#                     │
#                     │ 相同的 chunk_id
#                     ▼
# Chroma（实际数据仓库）
#     id + 原文 + metadata + embedding
# manifest demo:{
#   "rag_basics.md": {
#     "sha256": "64e334...",
#     "chunk_count": 1,
#     "chunk_ids": [
#       "00e78acce445..."
#     ]
#   }
# }
# chroma demo{
#     "id": "00e78acce445...",
#     "document": "# 两步 RAG 与索引基础 ...",
#     "metadata": {
#         "source": "rag_basics.md",
#         "chunk_id": "00e78acce445...",
#     },
#     "embedding": [0.012, -0.034, ...],  # 384 维
# }

# sources：manifest 中“已经纳入索引的来源文件状态表”。
# "sources": {
#     "rag_basics.md": {
#         "sha256": "64e334...",
#         "chunk_count": 1,
#         "chunk_ids": ["00e78a..."],
#     },
#     "evaluation.md": {
#         "sha256": "1d1444...",
#         "chunk_count": 1,
#         "chunk_ids": ["c76316..."],
#     },
# }
class IncrementalIndexer:
    """将来源文件 hash 与 Chroma 文档 ID 显式对应，支持增量同步。"""

    manifest_version = 1

    def __init__(self, settings: Settings):
        self.settings = settings
        self._embeddings = build_embeddings(settings)

    # 索引构建配置的指纹
    @property
    def index_fingerprint(self) -> str:
        payload = {
            "chunk_size": self.settings.chunk_size,
            "chunk_overlap": self.settings.chunk_overlap,
            "embedding": embedding_identity(self.settings),
            "collection": self.settings.collection_name,
        }
        return _sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False))[:20]

    # 创建或连接持久化 Chroma VectorStore，并绑定当前 Embedding 对象。
    def _store(self):
        from langchain_chroma import Chroma

        self.settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        return Chroma(
            collection_name=self.settings.collection_name,
            embedding_function=self._embeddings,
            persist_directory=str(self.settings.chroma_dir),
            # 设置向量相似度搜索使用 cosine distance，即余弦距离。
            collection_metadata={"hnsw:space": "cosine"},
        )


    def _empty_manifest(self) -> dict[str, Any]:
        return {
            "format_version": self.manifest_version,
            "index_fingerprint": self.index_fingerprint,
            # manifest 中“已经纳入索引的来源文件状态表”。
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

    def manifest_matches_config(self, manifest: dict[str, Any] | None = None) -> bool:
        active_manifest = manifest if manifest is not None else self.read_manifest()
        sources = active_manifest.get("sources", {})

        # 没有 sources 时（还没有已经持久化的来源向量）直接返回 True；
        # 只有 sources 非空时才比较 fingerprint。
        return not sources or active_manifest.get("index_fingerprint") == self.index_fingerprint

    def ensure_compatible_manifest(self) -> None:
        if not self.manifest_matches_config():
            raise IndexConflictError(
                "当前持久化索引由另一组 chunk/embedding 配置生成；"
                "请先执行 reindex --reset。"
            )

    # 原来的 index_manifest.json 保持不动
    # 创建 .index_manifest.xxx.tmp
    # 把完整 JSON 写进临时文件
    # with 退出，关闭临时文件
    # 临时文件原子替换 index_manifest.json
    # 避免程序写到一半出错，导致正式的 index_manifest.json 只剩半截 JSON。
    def _write_manifest(self, payload: dict[str, Any]) -> None:
        self.settings.runtime_dir.mkdir(parents=True, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(
            prefix=".index_manifest.", suffix=".tmp", dir=self.settings.runtime_dir
        )
        try:
            # with 保证离开代码块时自动关闭文件，即使 json.dump() 中途报错。
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                # 将 payload 序列化成 JSON，并直接写入 handle 指向的文件。
                # 中文不转成 \u4e2d，使用两个空格缩进，并按 key 排序。
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
            # 把临时文件替换为 index_manifest.json。
            os.replace(temporary_path, self.settings.manifest_path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    # LoadedSource 转 ChunkedSource 对象
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

    # _batched() 返回的不是二维列表，而是生成器：
    # for batch in batches: print(batch)
    # staticmethod 表示它不依赖 IncrementalIndexer 实例状态，所以没有 self 参数。
    @staticmethod
    def _batched(values: list[str] | list[Document], size: int = 100):
        for start in range(0, len(values), size):
            # 产出当前这一批数据，然后暂停函数；调用方需要下一批时，再恢复循环。
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
        """将 Chroma 的 cosine distance 转成 0..1 relevance score。"""

        self.ensure_compatible_manifest()
        matches = self._store().similarity_search_with_score(query, k=top_k)
        return [
            (document, max(0.0, min(1.0, 1.0 - float(distance))))
            for document, distance in matches
        ]
