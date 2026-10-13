from hashlib import sha256


def create_vector_store(settings):
    # 模型身份包含在命名空间中，避免切换模型后混用同维度但不同语义的向量。
    identity = sha256(f"{settings.model}:{settings.dimension}".encode()).hexdigest()[:10]
    namespace = f"{settings.namespace}_{identity}"
    if settings.backend == "qdrant":
        from vectorstores.qdrant_store import QdrantStore
        return QdrantStore(settings, namespace)
    from vectorstores.pgvector_store import PgvectorStore
    return PgvectorStore(settings, namespace)
