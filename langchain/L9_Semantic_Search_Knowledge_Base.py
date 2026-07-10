import json
import sys
from pathlib import Path
from typing import List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_SITE_PACKAGES = (
    PROJECT_ROOT
    / ".venv"
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)
if VENV_SITE_PACKAGES.exists():
    sys.path.insert(0, str(VENV_SITE_PACKAGES))

from langchain_core.embeddings import Embeddings


ZHIPU_API_KEY = "sk-lLKjavEquIsN4nk6eguOXFlhBXbXntGLHo5tOhbQWkBztYbj"
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_EMBEDDING_MODEL = "embedding-3"

OFFICIAL_SOURCE = "https://docs.langchain.com/oss/python/langchain/knowledge-base"

KEYWORDS = [
    "dog",
    "cat",
    "nike",
    "distribution",
    "incorporated",
    "oregon",
    "retail",
    "pet",
    "business",
    "center",
]

# 真实 embedding 会生成高维语义向量；这里是为了可解释、稳定、本地可跑模拟小知识库检索
class KeywordEmbeddings:
    """Small local embedding model for deterministic, readable tutorial output."""

    def __init__(self):
        self.keywords = KEYWORDS

# 它必须满足 LangChain Embeddings 接口约定：
# - embed_documents(texts): 文档入库时调用，把多个文档文本转成多个向量
# - embed_query(text): 查询时调用，把用户 query 转成一个向量
    def _embed(self, text: str):
        text = text.lower()
        return [float(text.count(keyword)) for keyword in self.keywords]

    def embed_query(self, text: str):
        return self._embed(text)

    def embed_documents(self, texts: list[str]):
        return [self._embed(text) for text in texts]


class NewKeywordEmbeddings(Embeddings):
    """Formal LangChain Embeddings implementation using local keyword counts."""

    def __init__(self, keywords: list[str] | None = None):
        self.keywords = keywords or KEYWORDS

    def _embed(self, text: str) -> list[float]:
        text = text.lower()
        return [float(text.count(keyword)) for keyword in self.keywords]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]


def load_dependencies():
    try:
        from langchain_core.documents import Document
        from langchain_core.embeddings import DeterministicFakeEmbedding
        from langchain_core.runnables import chain
        from langchain_core.vectorstores import InMemoryVectorStore
        from langchain_openai import OpenAIEmbeddings
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise RuntimeError(
            "加载失败。需要安装 langchain-core、langchain-openai、langchain-text-splitters。"
            f"原始错误: {type(exc).__name__}: {exc}"
        ) from exc

    return {
        "DeterministicFakeEmbedding": DeterministicFakeEmbedding,
        "Document": Document,
        "InMemoryVectorStore": InMemoryVectorStore,
        "OpenAIEmbeddings": OpenAIEmbeddings,
        "RecursiveCharacterTextSplitter": RecursiveCharacterTextSplitter,
        "chain": chain,
    }


def model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return {key: model_dump(item) for key, item in value.items()}
    if isinstance(value, list):
        return [model_dump(item) for item in value]
    return value


# 展示层压缩:这里只是为了打印时不要刷屏。实际检索用的还是完整 page_content。
def compact_documents(docs):
    return [
        {
            "page_content": doc.page_content[:240],
            "metadata": doc.metadata,
        }
        for doc in docs
    ]


# 这个函数不是返回向量，而是创建向量生成器 返回“生成向量的对象”。
def build_embeddings(deps, use_real_embeddings=False):
    if use_real_embeddings:
        if not ZHIPU_API_KEY:
            raise RuntimeError("请先在文件顶部填写 ZHIPU_API_KEY，再运行真实 embedding demo。")
        return deps["OpenAIEmbeddings"](
            model=ZHIPU_EMBEDDING_MODEL,
            openai_api_key=ZHIPU_API_KEY,
            openai_api_base=ZHIPU_BASE_URL,
        )
    return NewKeywordEmbeddings()


def build_documents(deps):
    Document = deps["Document"]
    return [
        Document(
            # page_content 文档正文
            page_content=(
                "Dogs are loyal companions. They enjoy walks, training, and working with people."
            ),
            # metadata: 文档来源、章节、标签等附加信息
            metadata={"source": "mammal-pets-doc", "section": "dogs"},
        ),
        Document(
            page_content=(
                "Cats are independent pets. They often prefer quiet spaces and short play sessions."
            ),
            metadata={"source": "mammal-pets-doc", "section": "cats"},
        ),
        Document(
            page_content=(
                "Nike was incorporated in Oregon in 1967. It sells footwear, apparel, "
                "equipment, accessories, and services worldwide."
            ),
            metadata={"source": "sample-10k", "section": "business"},
        ),
        Document(
            page_content=(
                "Nike has significant distribution centers in the United States and operates "
                "retail stores under several brands."
            ),
            metadata={"source": "sample-10k", "section": "properties"},
        ),
    ]


# 文档太长，不适合整体 embedding
# 小块更容易精确检索
# 后续喂给模型也更省 token
def split_documents(deps, docs):
    splitter = deps["RecursiveCharacterTextSplitter"](
        chunk_size=120,
        chunk_overlap=20,#相邻块重叠 20 字符，避免切断上下文
        add_start_index=True, #metadata 里记录块起始位置
    )
    return splitter.split_documents(docs)

# 构建向量库
# docs 里的每个 Document
# -> 用 embeddings 转成 vector
# -> 存入 InMemoryVectorStore
# InMemoryVectorStore 是内存向量库，适合 demo。程序退出后数据不会持久化。
def build_vector_store(deps, use_real_embeddings=False):
    embeddings = build_embeddings(deps, use_real_embeddings=use_real_embeddings)
    vector_store = deps["InMemoryVectorStore"](embeddings)
    docs = split_documents(deps, build_documents(deps))
    ids = vector_store.add_documents(documents=docs)
    return {
        "documents": docs,
        "ids": ids,
        "vector_store": vector_store,
    }


# 直接向量搜索
# query 转成向量
# -> 和库里文档向量比较相似度
# -> 返回最相似的前 2 条
def similarity_search_demo(deps):
    bundle = build_vector_store(deps)
    vector_store = bundle["vector_store"]
    query = "How many distribution centers does Nike have in the US?"
    # 返回最相似的前 2 条文档
    docs = vector_store.similarity_search(query, k=2)
    return {
        "official_source": OFFICIAL_SOURCE,
        "query": query,
        "indexed_chunks": len(bundle["documents"]),
        "results": compact_documents(docs),
    }

# 检索器
# 本质仍然是自己调用 vector_store.similarity_search
# 但外面套了一层 LangChain Runnable 接口
# 支持 invoke / batch 等 Runnable 方法
def retriever_demo(deps):
    chain = deps["chain"]
    bundle = build_vector_store(deps)
    vector_store = bundle["vector_store"]

    #retriever：用 @chain 包装检索器   
    @chain
    def retriever(query: str) -> List[deps["Document"]]: # type: ignore
        return vector_store.similarity_search(query, k=1)

    queries = [
        "How many distribution centers does Nike have in the US?",
        "When was Nike incorporated?",
    ]
    return {
        "queries": queries,
        "batch_results": [compact_documents(docs) for docs in retriever.batch(queries)],
    }

# as_retriever_demo：标准 retriever 接口 这是 LangChain 更标准的方式。
# 把 vector_store 包装成 retriever
# 检索方式是 similarity
# 每次返回 1 条
def as_retriever_demo(deps):
    bundle = build_vector_store(deps)
    retriever = bundle["vector_store"].as_retriever(
        search_type="similarity",
        search_kwargs={"k": 1},
    )
    query = "Which document talks about dogs?"
    return {
        "query": query,
        "result": compact_documents(retriever.invoke(query)),
    }


def run(title, func, deps):
    try:
        print(f"\n===== {title} =====")
        print(json.dumps(model_dump(func(deps)), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"跳过：{type(exc).__name__}: {exc}")


def main():
    try:
        deps = load_dependencies()
    except RuntimeError as exc:
        print(exc)
        return

    # run("1. documents + embeddings + vector store 语义搜索", similarity_search_demo, deps)
    run("2. 用 @chain 包装一个 retriever", retriever_demo, deps)
    run("3. vector_store.as_retriever", as_retriever_demo, deps)


if __name__ == "__main__":
    main()
