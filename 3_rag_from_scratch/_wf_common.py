from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

VENV_SITE_PACKAGES = (
    PROJECT_ROOT
    / ".venv"
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)
if VENV_SITE_PACKAGES.exists() and str(VENV_SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(VENV_SITE_PACKAGES))


ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9_./-]+")
CJK_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
WEB_SOURCE_URL = "https://lilianweng.github.io/posts/2023-06-23-agent/"


def lexical_tokens(text: str) -> set[str]:
    """提取可解释的中英文词项，供离线 embedding 与实验指标复用。"""

    normalized = text.lower()
    tokens = set(ASCII_TOKEN_PATTERN.findall(normalized))
    for run in CJK_RUN_PATTERN.findall(normalized):
        tokens.update(run[index : index + 2] for index in range(len(run) - 1))
    if not tokens and normalized.strip():
        tokens.add(normalized.strip())
    return tokens


class HashEmbeddings(Embeddings):
    """embedding 本地diemo"""

    dimension = 384
    model_id = "offline-stable-hash-v1"

    @classmethod
    def _embed(cls, text: str) -> list[float]:
        counts = Counter(lexical_tokens(text))
        vector = [0.0] * cls.dimension
        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:8], byteorder="big") % cls.dimension
            vector[slot] += float(count)
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude:
            return [value / magnitude for value in vector]
        return vector

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


@dataclass(frozen=True)
class RuntimeOptions:
    """启动命令开关"""

    use_web_source: bool
    use_live: bool
    embedding_mode: str


def parse_runtime_options(
    description: str,
    argv: Sequence[str] | None = None,
) -> RuntimeOptions:
    """解析每个 Part 一致的命令行参数，避免重复参数代码。"""

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--web-source",
        action="store_true",
        help=("使用原教程的 Lilian Weng 博客作为文档来源；默认使用仓库内置的离线样例。"),
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "回答生成或查询改写使用在线聊天模型；embedding 由 --embedding 独立选择。"
            "需要先设置 ZHIPU_API_KEY。"
        ),
    )
    parser.add_argument(
        "--embedding",
        choices=("local", "hash", "glm"),
        default="local",
        help=(
            "向量模型：local=本地多语言 MiniLM（默认），"
            "hash=离线教学哈希，glm=远程 embedding-3。"
        ),
    )
    args = parser.parse_args(argv)
    return RuntimeOptions(
        use_web_source=args.web_source,
        use_live=args.live,
        embedding_mode=args.embedding,
    )


LOCAL_DOCUMENTS = (
    Document(
        page_content=(
            "Task decomposition breaks a complex task into smaller, manageable steps. "
            "An agent can plan those steps before choosing tools or generating an answer."
        ),
        metadata={"source": "local-rag-notes", "topic": "task decomposition"},
    ),
    Document(
        page_content=(
            "Retrieval-augmented generation, or RAG, first retrieves relevant documents "
            "and then gives their context to a language model for grounded generation."
        ),
        metadata={"source": "local-rag-notes", "topic": "rag"},
    ),
    Document(
        page_content=(
            "Indexing normally loads source documents, splits long text into chunks, embeds "
            "the chunks, and stores the vectors in a vector store."
        ),
        metadata={"source": "local-rag-notes", "topic": "indexing"},
    ),
    Document(
        page_content=(
            "A retriever receives an unstructured question and returns the most relevant "
            "Document objects. In two-step RAG, retrieval always runs before generation."
        ),
        metadata={"source": "local-rag-notes", "topic": "retrieval"},
    ),
)


def load_source_documents(use_web_source: bool) -> list[Document]:
    """加载原教程网页，或返回默认的离线知识库。"""
    if not use_web_source:
        return list(LOCAL_DOCUMENTS)
    os.environ.setdefault("USER_AGENT", "rag-from-scratch-learning-demo/1.0")

    try:
        import bs4
        from langchain_community.document_loaders import WebBaseLoader
    except ImportError as exc:
        raise RuntimeError(
            "--web-source 需要 beautifulsoup4 和 langchain-community。"
            "请在 .venv 中安装后重试。"
        ) from exc

    loader = WebBaseLoader(
        web_paths=(WEB_SOURCE_URL,),
        bs_kwargs={
            "parse_only": bs4.SoupStrainer(
                class_=("post-content", "post-title", "post-header")
            )
        },
    )
    return loader.load()


def split_documents(
    documents: Iterable[Document],
    *,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    return splitter.split_documents(list(documents))
