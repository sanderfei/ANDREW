from qdrant_client import QdrantClient, models

from vectorstores.base import VectorChunk


class QdrantStore:
    def __init__(self, settings, namespace: str):
        self.client = QdrantClient(url=settings.qdrant_url, timeout=15)
        self.namespace = namespace
        self.dimension = settings.dimension

    def initialize(self) -> None:
        if not self.client.collection_exists(self.namespace):
            self.client.create_collection(
                self.namespace,
                vectors_config=models.VectorParams(size=self.dimension, distance=models.Distance.COSINE),
            )
        size = self.client.get_collection(self.namespace).config.params.vectors.size
        if size != self.dimension:
            raise ValueError("已有 Qdrant 集合的向量维度不匹配。")

    def status(self) -> dict:
        if not self.client.collection_exists(self.namespace):
            return {"connected": True, "initialized": False, "chunks": 0, "documents": {}}
        documents = {}
        offset = None
        while True:
            points, offset = self.client.scroll(
                self.namespace, limit=256, offset=offset, with_payload=["document_id"], with_vectors=False
            )
            for point in points:
                document_id = point.payload["document_id"]
                documents[document_id] = documents.get(document_id, 0) + 1
            if offset is None:
                break
        return {"connected": True, "initialized": True, "chunks": sum(documents.values()), "documents": documents}

    def replace_document(self, document_id: str, chunks: list[VectorChunk]) -> None:
        # 先写新片段，再删除该文档的旧片段；不会删除其他文档或集合。
        for start in range(0, len(chunks), 64):
            self.client.upsert(
                self.namespace,
                points=[models.PointStruct(id=chunk.id, vector=chunk.vector, payload={
                    "document_id": chunk.document_id, "content": chunk.content, "metadata": chunk.metadata,
                }) for chunk in chunks[start:start + 64]],
                wait=True,
            )
        keep = [chunk.id for chunk in chunks]
        selector = models.Filter(
            must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))],
            must_not=[models.HasIdCondition(has_id=keep)] if keep else None,
        )
        self.client.delete(self.namespace, points_selector=models.FilterSelector(filter=selector), wait=True)

    def delete_document(self, document_id: str) -> None:
        self.replace_document(document_id, [])

    def search(self, vector: list[float], limit: int, filters: dict) -> list[dict]:
        conditions = [models.FieldCondition(
            key=f"metadata.{key}", match=models.MatchAny(any=[value, "any"])
        ) for key, value in filters.items() if value]
        response = self.client.query_points(
            self.namespace, query=vector, limit=limit,
            query_filter=models.Filter(must=conditions) if conditions else None,
            with_payload=True,
        )
        return [{"chunk_id": str(point.id), "content": point.payload["content"],
                 "metadata": point.payload["metadata"], "score": float(point.score)}
                for point in response.points]

    def close(self) -> None:
        self.client.close()
