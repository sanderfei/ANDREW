"""本地 MiniLM、教学 Hash 与可选 GLM embedding/聊天模型。"""

from __future__ import annotations

import hashlib
import math
import os
import re
import warnings
from collections import Counter
from typing import Any

from langchain_core.embeddings import Embeddings

from config import Settings

# 匹配连续的：小写英文字母、数字、
ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9_./-]+")
# 匹配一个或多个连续的常用汉字。
CJK_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")

# 这些二字词在教学知识库几乎处处出现，不能单独构成“有答案”的证据。
ANSWERABILITY_STOP_TOKENS = frozenset(
    {
        "项目",
        "知识",
        "识库",
        "文档",
        "档的",
        "问题",
        "什么",
        "如何",
        "哪些",
        "这个",
        "当前",
        "采用",
        "数据",
        "服务",
        "系统",
        "需要",
        "返回",
        "调用",
    }
)


def lexical_tokens(text: str) -> set[str]:
    """为中文和英文都提供可解释的离线词项集合。相邻两个汉字滑动提取"""

    normalized = text.lower()
    tokens = set(ASCII_TOKEN_PATTERN.findall(normalized))
    for run in CJK_RUN_PATTERN.findall(normalized):
        # 单个汉字（尤其“的”“是”）会造成无答案问题的伪相关，离线 gate
        # 只采用至少两个字的连续片段。
        tokens.update(run[index : index + 2] for index in range(len(run) - 1))
    return tokens

# 除去影响答案的高频词汇
def grounding_tokens(text: str) -> set[str]:
    """用于 answerability gate 的词项，排除高频泛化词。"""

    # difference 保留 left 中存在、但 right 中不存在的元素。
    return lexical_tokens(text).difference(ANSWERABILITY_STOP_TOKENS)


# 从文本中提取 API 名、字段名、路径和英文技术术语，用来防止引用到“语义相似但技术对象不同”的文档
def technical_tokens(text: str) -> set[str]:
    """识别问题中的 API 名、字段名和英文术语，用于避免错误引用。"""

    return {
        token
        for token in ASCII_TOKEN_PATTERN.findall(text.lower())
        if len(token) >= 3 and any(character.isalnum() for character in token)
    }


class StableHashEmbeddings(Embeddings):
    """无需模型下载或密钥的固定维度 embedding。

    它只用于学习、离线评测和本地 smoke；真实产品应在 live 模式换用正式
    embedding provider。哈希槽位与归一化确保跨进程与跨机器结果稳定。
    """

    dimension = 384
    model_id = "offline-stable-hash-v2"

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

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class LocalMiniLMEmbeddings(Embeddings):
    """复用目录 3 已验证的 FastEmbed + ONNX Runtime 本地模型。"""

    dimension = 384

    def __init__(self, settings: Settings) -> None:
        self.model_id = settings.local_embedding_model
        self.cache_dir = settings.local_embedding_cache
        self.model_path = settings.local_embedding_path
        self._model: Any | None = None

    def _load_model(self):
        if self._model is not None:
            return self._model

        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise RuntimeError(
                "本地 embedding 需要 fastembed。请先安装本目录 requirements.txt。"
            ) from exc

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=(
                    r"The model sentence-transformers/"
                    r"paraphrase-multilingual-MiniLM-L12-v2 now uses mean pooling.*"
                ),
                category=UserWarning,
            )
            model_kwargs: dict[str, Any] = {}
            # setup-new-machine.md 会为 ModelScope 的 AVX2 量化模型创建这个软链接。
            # 传入具体目录后 FastEmbed 不访问 Hugging Face，直接加载本地 ONNX。
            if (self.model_path / "model_optimized.onnx").is_file():
                model_kwargs["specific_model_path"] = str(self.model_path)
            self._model = TextEmbedding(
                model_name=self.model_id,
                cache_dir=str(self.cache_dir),
                threads=min(4, os.cpu_count() or 1),
                **model_kwargs,
            )
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load_model().passage_embed(texts)
        return [[float(value) for value in vector] for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        vector = next(iter(self._load_model().query_embed(text)))
        return [float(value) for value in vector]


def embedding_identity(settings: Settings) -> str:
    if settings.embedding_mode == "local":
        local_variant = (
            "specific-model-path"
            if (settings.local_embedding_path / "model_optimized.onnx").is_file()
            else "fastembed-managed-cache"
        )
        return f"fastembed:{settings.local_embedding_model}:{local_variant}"
    if settings.embedding_mode == "hash":
        return StableHashEmbeddings.model_id
    return f"openai-compatible:{settings.zhipu_base_url}:{settings.embedding_model}"


def embedding_display_name(settings: Settings) -> str:
    if settings.embedding_mode == "local":
        return settings.local_embedding_model
    if settings.embedding_mode == "hash":
        return StableHashEmbeddings.model_id
    return settings.embedding_model


def build_embeddings(settings: Settings) -> Embeddings:
    if settings.embedding_mode == "local":
        return LocalMiniLMEmbeddings(settings)
    if settings.embedding_mode == "hash":
        return StableHashEmbeddings()

    from langchain_openai import OpenAIEmbeddings

    kwargs: dict[str, object] = {
        "model": settings.embedding_model,
        "api_key": settings.zhipu_api_key,
        "base_url": settings.zhipu_base_url,
        # GLM 是 OpenAI-compatible provider，不使用 OpenAI tokenizer 预切输入。
        "check_embedding_ctx_length": False,
        "timeout": settings.timeout_seconds,
        "max_retries": 2,
    }
    return OpenAIEmbeddings(**kwargs)


def build_chat_model(settings: Settings):
    """只在 answerability gate 通过且处于 live 模式时才创建模型。"""

    if not settings.is_live:
        return None

    from langchain_openai import ChatOpenAI

    kwargs: dict[str, object] = {
        "model": settings.chat_model,
        "api_key": settings.zhipu_api_key,
        "base_url": settings.zhipu_base_url,
        "temperature": 0.1,
        "timeout": settings.timeout_seconds,
        "max_retries": 0,
    }
    return ChatOpenAI(**kwargs)
