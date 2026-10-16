import psycopg
from psycopg.types.json import Jsonb

from vectorstores.base import VectorChunk


class PgvectorStore:
    def __init__(self, settings, namespace: str):
        self.settings = settings
        self.namespace = namespace

    def _connect(self):
        if not self.settings.pg_password:
            raise ValueError(
                "缺少 PostgreSQL 密码，请先运行 setup_local_databases.py。"
            )
        return psycopg.connect(
            host=self.settings.pg_host,
            port=self.settings.pg_port,
            dbname=self.settings.pg_database,
            user=self.settings.pg_user,
            password=self.settings.pg_password,
            connect_timeout=5,
        )

    def initialize(self) -> None:
        with self._connect() as connection:
            # 在当前数据库中启用 pgvector。然后建表：
            #     embedding vector(384) NOT NULL, 该片段的 384 维向量
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            # dimension 已由配置验证为 384；其余 SQL 值始终参数绑定。
            connection.execute("""CREATE TABLE IF NOT EXISTS private_rag_chunks (
                namespace text NOT NULL, id uuid NOT NULL, document_id text NOT NULL,
                content text NOT NULL, metadata jsonb NOT NULL, embedding vector(384) NOT NULL,
                PRIMARY KEY (namespace, id)
            )""")
            #  按文档定位片段，方便更新、删除
            connection.execute(
                "CREATE INDEX IF NOT EXISTS private_rag_chunks_document_idx ON private_rag_chunks (namespace, document_id)"
            )
            # 为余弦距离近似检索准备向量索引 HNSW 用于近似最近邻搜索，通常通过牺牲部分召回换取速度
            # 搜索可以更快，但可能漏掉少量本来应该找到的结果
            # 预先把向量组织成多层关系图，查询时沿着图寻找接近的位置，减少比较次数，因此通常更快；但可能没走到某个更近的片段。
            connection.execute(
                "CREATE INDEX IF NOT EXISTS private_rag_chunks_vector_idx ON private_rag_chunks USING hnsw (embedding vector_cosine_ops)"
            )

    # 统计当前 namespace 的文档和片段
    def status(self) -> dict:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT to_regclass('public.private_rag_chunks')"
            ).fetchone()[0]
            if exists is None:
                return {
                    "connected": True,
                    "initialized": False,
                    "chunks": 0,
                    "documents": {},
                }
            records = connection.execute(
                "SELECT document_id, count(*) FROM private_rag_chunks WHERE namespace=%s GROUP BY document_id",
                (self.namespace,),
            ).fetchall()
            documents = dict(records)
            return {
                "connected": True,
                "initialized": True,
                "chunks": sum(documents.values()),
                "documents": documents,
            }

    @staticmethod
    def _vector(vector: list[float]) -> str:
        # 把 Python 数字列表转成 pgvector 输入字符串
        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    # 在一个事务里替换某篇文档
    def replace_document(self, document_id: str, chunks: list[VectorChunk]) -> None:

        # 删除和插入共用同一个连接，连接默认关闭自动提交，外层 with 统一决定提交或回滚。
        # 删除和写入在同一事务内，失败时保留原文档数据。
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM private_rag_chunks WHERE namespace=%s AND document_id=%s",
                (self.namespace, document_id),
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO private_rag_chunks (namespace,id,document_id,content,metadata,embedding) VALUES (%s,%s,%s,%s,%s,%s::vector)",
                    [
                        (
                            self.namespace,
                            chunk.id,
                            chunk.document_id,
                            chunk.content,
                            Jsonb(chunk.metadata),
                            self._vector(chunk.vector),
                        )
                        for chunk in chunks
                    ],
                )

    def delete_document(self, document_id: str) -> None:
        self.replace_document(document_id, [])

    # vector 是问题的 Embedding 384 维向量，filters 是 {kubernetes_versions, operating_systems, install_modes} 的可选过滤条件
    # sqldemo: 余弦距离近似检索，过滤条件，按距离升序排序，取前 limit 个
    # BEGIN;
    # SET LOCAL enable_indexscan = off;
    # SELECT
    #     id,
    #     content,
    #     metadata,
    #     1 - (
    #         embedding <=> array_fill(0.1::real, ARRAY[384])::vector
    #     ) AS score
    # FROM private_rag_chunks
    # WHERE namespace = 'private_deployment_demo'
    #   AND (metadata -> 'kubernetes_versions')
    #       ?| ARRAY['1.32.8', 'any']
    #   AND (metadata -> 'install_modes')
    #       ?| ARRAY['offline', 'any']
    # ORDER BY
    #     embedding <=> array_fill(0.1::real, ARRAY[384])::vector
    # LIMIT 5;
    # COMMIT;
    def search(self, vector: list[float], limit: int, filters: dict) -> list[dict]:
        predicates = ["namespace=%s"]
        values = [self.namespace]
        for key, value in filters.items():
            if value:
                predicates.append("(metadata -> %s) ?| %s")
                values.extend([key, [value, "any"]])
        text_vector = self._vector(vector)

        # 计算候选片段与问题向量的余弦距离
        # 余弦相似度 = 1 - (向量1 <=> 向量2)；越接近 1 越相似
        # 余弦距离 = 1 - 余弦相似度；
        # 余弦距离近似检索：embedding <=> %s::vector
        # 余弦距离精确检索：1 - (embedding <=> %s::vector)
        # 过滤条件：metadata -> %s 取 metadata 中指定字段
        with self._connect() as connection:

            # 当前事务里，尽量不要通过索引扫描来查询，采用这种精确检索（筛选符合条件的片段->逐个计算向量距离->排序，取前5条）
            connection.execute("SET LOCAL enable_indexscan = off")
            records = connection.execute(
                "SELECT id, content, metadata, 1 - (embedding <=> %s::vector) AS score "
                "FROM private_rag_chunks WHERE "
                + " AND ".join(predicates)
                + " ORDER BY embedding <=> %s::vector LIMIT %s",
                [text_vector, *values, text_vector, limit],
            ).fetchall()
        return [
            {
                "chunk_id": str(row[0]),
                "content": row[1],
                "metadata": row[2],
                "score": float(row[3]),
            }
            for row in records
        ]

    def close(self) -> None:
        pass
