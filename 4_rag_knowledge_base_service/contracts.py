"""FastAPI 与 CLI 共用的稳定输入/输出契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


# 返回给调用方的一条引用证据；只有通过可回答性判断的检索结果才会生成 Citation。
class Citation(BaseModel):
    chunk_id: str  # 文档块在向量库中的稳定唯一 ID。
    source: str  # 原始文件相对于 docs 目录的路径，例如 rag_basics.md。
    source_type: str  # 来源文件类型，例如 markdown 或 pdf。
    page: int | None = None  # PDF 页码（从 1 开始）；Markdown 没有页码，因此为 None。
    start_index: int | None = None  # 文档块在原始文档中的起始字符位置。
    quote: str  # 从文档块中截取的、与问题最相关的原文片段。
    relevance_score: float  # 向量相似度与关键词重合度合成后的最终相关性分数。
    vector_score: float  # 由向量距离换算并限制在 0～1 之间的语义相似度分数。
    lexical_overlap: float  # 查询关键词在文档块中的命中比例，取值范围为 0～1。


# 记录一次检索返回的单个候选文档块，包括通过和未通过筛选的候选。
class RetrievalMatch(BaseModel):
    rank: int  # 候选在 Chroma 原始检索结果中的排名，从 1 开始。
    chunk_id: str  # 候选文档块在向量库中的稳定唯一 ID。
    source: str  # 候选文档块所属的原始文件路径。
    page: int | None = None  # PDF 页码（从 1 开始）；非 PDF 文档为 None。
    relevance_score: float  # 向量分数与关键词分数合成后的最终相关性分数。
    vector_score: float  # 由 Chroma 返回的 distance 换算得到的语义相似度分数。
    lexical_overlap: float  # 查询关键词在候选文档块中的命中比例。
    accepted: bool  # 候选是否通过相关性阈值和关键词阈值等可回答性判断。
    content_preview: str  # 对候选正文压缩空白并截断后得到的预览文本。


# 汇总一次问答的完整检索过程，用于观察阈值、候选结果以及筛选情况。
class RetrievalTrace(BaseModel):
    top_k: int  # 本次请求最多要求向量库返回的候选数量。
    min_relevance_score: float  # 候选需要达到的最低综合相关性分数。
    min_lexical_overlap: float  # 候选需要达到的最低关键词命中比例。
    returned_count: int  # Chroma 实际返回的候选文档块数量。
    accepted_count: int  # 通过可回答性判断的候选文档块数量。
    matches: list[RetrievalMatch]  # 所有候选的详细记录，包括被拒绝的候选。


# 定义 POST /v1/ask 接口接收的请求参数。
class AskRequest(BaseModel):
    # 用户提出的自然语言问题；长度必须在 1～2000 个字符之间。
    question: str = Field(min_length=1, max_length=2000)
    # 最多检索多少个候选文档块；默认 4 个，允许范围为 1～8。
    top_k: int = Field(default=4, ge=1, le=8)


# 定义一次问答操作的完整返回结果，供 FastAPI 接口和 CLI 共用。
class AskResponse(BaseModel):
    request_id: str  # 本次请求的唯一追踪 ID，便于关联日志和排查问题。
    answer: str  # 最终答案；也可能是离线摘录或“证据不足”的固定回复。
    answerable: bool  # 检索结果中是否存在通过可回答性判断的候选文档块。
    citations: list[Citation]  # 支撑答案的引用证据；不可回答时为空列表。
    retrieval: RetrievalTrace  # 本次检索及候选筛选过程的完整记录。
    mode: str  # 服务运行模式，例如 offline 或 live。
    embedding_mode: str  # 生成向量所使用的模式，例如 local、hash 或 glm。


# 定义 POST /v1/reindex 接口接收的重建索引参数。
class ReindexRequest(BaseModel):
    # 是否执行完整重建：False 表示增量更新，True 表示清空旧索引后重新写入全部文件。
    reset: bool = Field(
        default=False,
        description="chunk/embedding 配置变化时显式清空并重建整个索引。",
    )


# 返回一次增量更新或完整重建索引后的统计结果。
class ReindexResponse(BaseModel):
    request_id: str  # 本次重建请求的唯一追踪 ID。
    reset: bool  # 本次是否先清空旧索引，再完整重建。
    scanned_files: int  # 本次在 docs 目录中扫描到的受支持文件总数。
    added_files: int  # 相比旧 manifest，本次新增的源文件数量。
    updated_files: int  # 文件名未变但内容哈希发生变化的源文件数量。
    unchanged_files: int  # 文件名和内容哈希均未变化的源文件数量。
    removed_files: int  # 旧 manifest 中存在、当前 docs 目录中已不存在的文件数量。
    indexed_chunks: int  # 本次新增或重新写入向量库的文档块数量。
    deleted_chunks: int  # 本次从向量库中删除的旧文档块数量。
    total_indexed_chunks: int  # 新 manifest 记录的全部文档块数量之和。
    index_fingerprint: str  # 当前切块、嵌入模型和 collection 配置的组合指纹。


# 返回服务健康状态以及当前索引是否已经就绪、配置是否匹配。
class HealthResponse(BaseModel):
    status: str  # 服务状态；当前正常响应时为 ok。
    mode: str  # 服务运行模式，例如 offline 或 live。
    embedding_mode: str  # 嵌入实现模式，例如 local、hash 或 glm。
    embedding_model: str  # 当前嵌入模型或本地嵌入实现的名称。
    collection: str  # 保存文档向量的 Chroma collection 名称。
    index_ready: bool  # manifest 中是否已有源文件，并且索引配置是否匹配。
    index_config_matches: bool  # manifest 中的索引指纹是否与当前配置一致。
    source_document_count: int  # manifest 中记录的源文件数量。
    indexed_chunk_count: int  # manifest 中所有源文件的文档块数量之和。
    index_fingerprint: str | None = None  # 已保存的索引指纹；无索引时为 None。
    request_id: str  # 本次健康检查请求的唯一追踪 ID。
