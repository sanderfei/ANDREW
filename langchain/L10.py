import json
import sys
from pathlib import Path
from langchain_core.embeddings import Embeddings

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


ZHIPU_API_KEY = "sk-lLKjavEquIsN4nk6eguOXFlhBXbXntGLHo5tOhbQWkBztYbj"
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
ZHIPU_EMBEDDING_MODEL = "embedding-3"
LOAD_LIVE_WEB_PAGE = False
RUN_LIVE_DEMO = False
STABLE_TEMPERATURE = 0.1

OFFICIAL_SOURCE = "https://docs.langchain.com/oss/python/langchain/rag"
SOURCE_URL = "https://lilianweng.github.io/posts/2023-06-23-agent/"

RAG_SYSTEM_PROMPT = """
你可以使用 retrieve_context 工具从资料库检索上下文。
回答必须基于检索结果；如果资料库没有答案，就说不知道。
把检索
"""

class KeywordEmbeddings(Embeddings):
    """Small local embedding model for deterministic, readable tutorial output."""

    def __init__(self):
        self.keywords = [
            "task",
            "decomposition",
            "planner",
            "rag",
            "retrieval",
            "generation",
            "context",
            "question",
            "answer",
            "agent",
        ]

    def _embed(self, text: str) -> list[float]:
        text = text.lower()
        return [ float(text.count(keyword)) for keyword in self.keywords]
    
    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
    
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]
    

def load_dependencies():
    try:
        import bs4
        import requests
        from langchain.agents import create_agent
        from langchain.tools import tool
        from langchain_core.documents import Document
        from langchain_core.embeddings import DeterministicFakeEmbedding
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.runnables import RunnablePassthrough
        from langchain_core.vectorstores import InMemoryVectorStore
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise RuntimeError(
            "加载失败。需要安装 langchain、langchain-core、langchain-openai、"
            "langchain-text-splitters、bs4、requests。"
            f"原始错误: {type(exc).__name__}: {exc}"
        ) from exc

    return {
        # 解析网页 HTML，只提取博客正文、标题、头部这些区域
        "BeautifulSoup": bs4.BeautifulSoup,
        "ChatOpenAI": ChatOpenAI,
        "ChatPromptTemplate": ChatPromptTemplate,
        "DeterministicFakeEmbedding": DeterministicFakeEmbedding,
        "Document": Document,
        # 内存向量库类。负责保存文档向量，并支持相似度搜索。
        "InMemoryVectorStore": InMemoryVectorStore,
        # 真实 embedding 客户端类。用于调用 embedding API 把文本转成语义向量。
        "OpenAIEmbeddings": OpenAIEmbeddings,
        # 文档切块器。把长文本按字符递归切成较小 chunk，适合做向量入库。
        "RecursiveCharacterTextSplitter": RecursiveCharacterTextSplitter,
        # LCEL 组件，表示“原样传递输入”。常用于 RAG chain 里保留原始问题：
        "RunnablePassthrough": RunnablePassthrough,
        # BeautifulSoup 的过滤器。解析网页时只保留指定区域，比如标题、正文，减少无关 HTML。
        "SoupStrainer": bs4.SoupStrainer,
        "StrOutputParser": StrOutputParser,
        "create_agent": create_agent,
        # HTTP 请求库模块。用于请求网页 URL，获取 HTML 内容。
        "requests": requests,
        # LangChain 的工具装饰器。把普通 Python 函数包装成 agent 可调用的 tool。
        "tool": tool,
    }

def build_model(ChatOpenAI, temperature=STABLE_TEMPERATURE, **kwargs):
    if not ZHIPU_API_KEY:
        raise RuntimeError("请先在文件顶部填写 ZHIPU_API_KEY，再运行真实 RAG 生成 demo。")
    return ChatOpenAI(
        model=ZHIPU_CHAT_MODEL,
        temperature=temperature,
        openai_api_key=ZHIPU_API_KEY,
        openai_api_base=ZHIPU_BASE_URL,
        timeout=60,
        **kwargs,
    )

def build_embeddings(deps, use_real_embeddings=False):
    if use_real_embeddings:
        if not ZHIPU_API_KEY:
            raise RuntimeError("请先在文件顶部填写 ZHIPU_API_KEY，再运行真实 embedding demo。")
        return deps["OpenAIEmbeddings"](
            model=ZHIPU_EMBEDDING_MODEL,
            openai_api_key=ZHIPU_API_KEY,
            openai_api_base=ZHIPU_BASE_URL,
        )
    return KeywordEmbeddings()

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
            "page_content": doc.page_content[:300],
            "metadata": doc.metadata,
        }
        for doc in docs
    ]

def load_web_page(deps, url: str):
    response = deps["requests"].get(url, timeout=20)
    soup = deps["BeautifulSoup"](
        response.text,
        "html.parser",
        parse_only=deps["SoupStrainer"](
            class_ = ("post-content", "post-title", "post-header")
        ),
    )