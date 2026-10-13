import psycopg
from psycopg.types.json import Jsonb

from vectorstores.base import VectorChunk


class PgvectorStore:
    def __init__(self, settings, namespace: str):
        self.settings = settings
        self.namespace = namespace

    def _connect(self):
        if not self.settings.pg_password:
            raise ValueError("缺少 PostgreSQL 密码，请先运行 setup_local_databases.py。")
        return psycopg.connect(
            host=self.settings.pg_host, port=self.settings.pg_port,
            dbname=self.settings.pg_database, user=self.settings.pg_user,
            password=self.settings.pg_password, connect_timeout=5,
        )

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            # dimension 已由配置验证为 384；其余 SQL 值始终参数绑定。
            connection.execute("""CREATE TABLE IF NOT EXISTS private_rag_chunks (
                namespace text NOT NULL, id uuid NOT NULL, document_id text NOT NULL,
                content text NOT NULL, metadata jsonb NOT NULL, embedding vector(384) NOT NULL,
                PRIMARY KEY (namespace, id)
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS private_rag_chunks_document_idx ON private_rag_chunks (namespace, document_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS private_rag_chunks_vector_idx ON private_rag_chunks USING hnsw (embedding vector_cosine_ops)")

    def status(self) -> dict:
        with self._connect() as connection:
            exists = connection.execute("SELECT to_regclass('public.private_rag_chunks')").fetchone()[0]
            if exists is None:
                return {"connected": True, "initialized": False, "chunks": 0, "documents": {}}
            records = connection.execute(
                "SELECT document_id, count(*) FROM private_rag_chunks WHERE namespace=%s GROUP BY document_id",
                (self.namespace,),
            ).fetchall()
            documents = dict(records)
            return {"connected": True, "initialized": True, "chunks": sum(documents.values()), "documents": documents}

    @staticmethod
    def _vector(vector: list[float]) -> str:
        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    def replace_document(self, document_id: str, chunks: list[VectorChunk]) -> None:
        with self._connect() as connection:
            # 删除和写入在同一事务内，失败时保留原文档数据。
            connection.execute("DELETE FROM private_rag_chunks WHERE namespace=%s AND document_id=%s", (self.namespace, document_id))
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO private_rag_chunks (namespace,id,document_id,content,metadata,embedding) VALUES (%s,%s,%s,%s,%s,%s::vector)",
                    [(self.namespace, chunk.id, chunk.document_id, chunk.content, Jsonb(chunk.metadata), self._vector(chunk.vector)) for chunk in chunks],
                )

    def delete_document(self, document_id: str) -> None:
        self.replace_document(document_id, [])

    def search(self, vector: list[float], limit: int, filters: dict) -> list[dict]:
        predicates = ["namespace=%s"]
        values = [self.namespace]
        for key, value in filters.items():
            if value:
                predicates.append("(metadata -> %s) ?| %s")
                values.extend([key, [value, "any"]])
        text_vector = self._vector(vector)
        with self._connect() as connection:
            # 当前资料规模使用精确查询，避免 ANN 后过滤导致结果不足；已预留 HNSW 索引。
            connection.execute("SET LOCAL enable_indexscan = off")
            records = connection.execute(
                "SELECT id, content, metadata, 1 - (embedding <=> %s::vector) AS score "
                "FROM private_rag_chunks WHERE " + " AND ".join(predicates) +
                " ORDER BY embedding <=> %s::vector LIMIT %s",
                [text_vector, *values, text_vector, limit],
            ).fetchall()
        return [{"chunk_id": str(row[0]), "content": row[1], "metadata": row[2], "score": float(row[3])} for row in records]

    def close(self) -> None:
        pass
