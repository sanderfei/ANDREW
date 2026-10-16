from qdrant_client import QdrantClient, models

from vectorstores.base import VectorChunk

# QdrantStore 是 Qdrant 向量数据库的适配器，提供初始化、状态检查、文档替换、删除和向量搜索功能。
# 核心概念：
# Collection  集合，存放一组向量数据
# Point	一条向量记录
# ID	记录的唯一标识
# Vector	用于计算相似度的数字列表
# Payload	随向量一起保存的正文和其他信息
# {
#     "id": "片段的 UUID",
#     "vector": [0.12, -0.08, ...],
#     "payload": {
#         "document_id": "文档A",
#         "content": "离线安装时，需要先导入镜像……",
#               正文不需要单独存到另一个数据库，当前代码将它放在 payload 中，检索时一起取回来。
#         "metadata": {
#             "kubernetes_versions": ["1.32.8"],
#             "install_modes": ["offline"]
#         }
#     }
# }


# Qdrant 不支持point级别的事务操作，需要做额外的补偿
# 或者版本管理同一个文档新版写入验证完成后切换查询使用的版本，后续清理旧版
class QdrantStore:
    def __init__(self, settings, namespace: str):
        self.client = QdrantClient(url=settings.qdrant_url, timeout=15)
        self.namespace = namespace
        self.dimension = settings.dimension

    def initialize(self) -> None:
        if not self.client.collection_exists(self.namespace):
            # 准备集合并检查维度
            self.client.create_collection(
                self.namespace,
                vectors_config=models.VectorParams(
                    size=self.dimension,
                    distance=models.Distance.COSINE,  # 表示使用余弦相似度进行比较。
                ),
            )
        size = self.client.get_collection(self.namespace).config.params.vectors.size

        if size != self.dimension:
            raise ValueError("已有 Qdrant 集合的向量维度不匹配。")

    # 遍历集合中的全部片段，数据量越大，统计成本也越高
    def status(self) -> dict:
        if not self.client.collection_exists(self.namespace):
            return {
                "connected": True,
                "initialized": False,
                "chunks": 0,
                "documents": {},
            }
        documents = {}
        offset = None
        while True:
            # Qdrant 的 scroll API 用于分页遍历集合中的点（向量记录），每次返回一批点和下一个偏移量。
            points, offset = self.client.scroll(
                self.namespace,
                limit=256,  # 每次最多读取 256 条
                offset=offset,  # 从上一页返回的位置继续
                with_payload=["document_id"],  # 只取文档 ID
                with_vectors=False,  # 不返回向量，减少传输量
            )
            for point in points:
                document_id = point.payload["document_id"]
                documents[document_id] = documents.get(document_id, 0) + 1
            if offset is None:
                break
        return {
            "connected": True,
            "initialized": True,
            "chunks": sum(documents.values()),
            "documents": documents,
        }

    # 当前 Qdrant 实现包含多次独立请求，没有将整个文档替换包在一个事务中。中途失败时，前面已经成功的写入不会自动回滚。
    # 因此，wait=True 代表等待单次操作完成，不能理解成“整个替换具有事务性”。
    def replace_document(self, document_id: str, chunks: list[VectorChunk]) -> None:
        # 先写新片段，再删除该文档的旧片段；不会删除其他文档或集合。
        for start in range(0, len(chunks), 64):
            self.client.upsert(
                self.namespace,
                points=[
                    models.PointStruct(
                        id=chunk.id,
                        vector=chunk.vector,
                        payload={
                            "document_id": chunk.document_id,
                            "content": chunk.content,
                            "metadata": chunk.metadata,
                        },
                    )
                    for chunk in chunks[start : start + 64]
                ],
                wait=True,
            )
        keep = [chunk.id for chunk in chunks]
        selector = models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id", match=models.MatchValue(value=document_id)
                )
            ],
            must_not=[models.HasIdCondition(has_id=keep)] if keep else None,
        )
        # 删除属于当前文档并且ID不在本次新片段列表中的片段
        self.client.delete(
            self.namespace,
            points_selector=models.FilterSelector(filter=selector),
            wait=True,
        )

    def delete_document(self, document_id: str) -> None:
        self.replace_document(document_id, [])

    def search(self, vector: list[float], limit: int, filters: dict) -> list[dict]:
        conditions = [
            models.FieldCondition(
                key=f"metadata.{key}", match=models.MatchAny(any=[value, "any"])
            )
            for key, value in filters.items()
            if value
        ]
        response = self.client.query_points(
            self.namespace,  # 去哪个集合检索
            query=vector,  # 用问题向量寻找相近片段
            limit=limit,
            query_filter=models.Filter(must=conditions) if conditions else None,
            with_payload=True,  # 同时返回正文和元数据
        )
        return [
            {
                "chunk_id": str(point.id),
                "content": point.payload["content"],
                "metadata": point.payload["metadata"],
                "score": float(point.score),
            }
            for point in response.points
        ]

    def close(self) -> None:
        self.client.close()
