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
from _runtime import env



ZHIPU_API_KEY = env("ZHIPU_API_KEY")
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_EMBEDDING_MODEL = "embedding-3"

OFFICIAL_SOURCE = "https://docs.langchain.com/oss/python/langchain/knowledge-base"

class KeywordEmbeddings:
    """Small local embedding model for deterministic, readable tutorial output."""

    def __init__(self):
        self.keywords = [
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

    def _embed(self, text: str):
        text = text.lower()
        return [float(text.count(keyword)) for keyword in self.keywords] 
    
    def embed_query(self, text: str):
        return self._embed(text)
    
    def embed_documents(self, texts: list[str]):
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

def compact_documents(docs):
   return [
       {
           "page_content": doc.page_content[:240],
           "metadata": doc.metadata,
       }
       for doc in docs
   ]

def build_embeddings(deps, use_real_embeddings=False):
    if use_real_embeddings:
        return deps["OpenAIEmbeddings"](
            model=ZHIPU_EMBEDDING_MODEL,
            openai_api_key=ZHIPU_API_KEY,
            openai_api_base=ZHIPU_BASE_URL,
        )
    return KeywordEmbeddings()

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

def split_documents(deps,docs):
    splitter = deps["RecursiveCharacterTextSplitter"](
        chunk_size=120,
        chunk_overlap=20,
        add_start_index=True,
    )
    return splitter.split_documents(docs)

def build_vector_store(deps, use_real_embeddings=False):
    embeddings = build_embeddings(deps, use_real_embeddings=use_real_embeddings)
    vector_store = deps["InMemoryVectorStore"](embeddings)
    docs = split_documents(deps, build_documents(deps))
    ids = vector_store.add_documents(docs)
    return {
        "vector_store": vector_store,
        "documents": docs,  
        "ids": ids,
    }      

def similarity_search_demo(deps):
    bundle = build_vector_store(deps)
    vector_store = bundle["vector_store"]
    query = "How many distribution centers does Nike have in the US?"
    docs = vector_store.similarity_search(query, k=2)
    return {
        "official_source": OFFICIAL_SOURCE,
        "query": query,
        "indexed_chunks": len(bundle["documents"]),
        "results": compact_documents(docs),
    }

def retriever_demo(deps):
    chain = deps["chain"]
    bundle =  build_vector_store(deps)
    vector_store = bundle["vector_store"]

    @chain
    def retriever(query: str) -> List[deps["Document"]]:# type: ignore
        return vector_store.similarity_search(query, k=1)
    
    queries = [
        "How many distribution centers does Nike have in the US?",
        "When was Nike incorporated?",
    ]

    return {
        "queries": queries,
        "batch_results": [compact_documents(docs) for docs in retriever.batch(queries)],
    }

def as_retriever_demo(deps):
    bundle = build_vector_store(deps)
    retriever = bundle["vector_store"].as_retriever(
        search_type="similarity",
        search_kwargs={"k": 1},
    )
    queries = [
        "How many distribution centers does Nike have in the US?",
        "When was Nike incorporated?",
    ]
    return {
        "queries": queries,
        "batch_results": [compact_documents(docs) for docs in retriever.batch(queries)],
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

    run("1. documents + embeddings + vector store 语义搜索", similarity_search_demo, deps)
    # run("2. 用 @chain 包装一个 retriever", retriever_demo, deps)
    # run("3. vector_store.as_retriever", as_retriever_demo, deps)

if __name__ == "__main__":
    main()