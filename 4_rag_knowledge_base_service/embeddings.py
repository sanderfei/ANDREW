"""离线可复现 embedding 与可选的真实 OpenAI embedding。"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Iterable

from langchain_core.embeddings import Embeddings

from config import Settings


ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9_./-]+")
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
    """为中文和英文都提供可解释的离线词项集合。"""

    normalized = text.lower()
    tokens = set(ASCII_TOKEN_PATTERN.findall(normalized))
    for run in CJK_RUN_PATTERN.findall(normalized):
        # 单个汉字（尤其“的”“是”）会造成无答案问题的伪相关，离线 gate
        # 只采用至少两个字的连续片段。
        tokens.update(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


def grounding_tokens(text: str) -> set[str]:
    """用于 answerability gate 的词项，排除高频泛化词。"""

    return lexical_tokens(text).difference(ANSWERABILITY_STOP_TOKENS)


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


def embedding_identity(settings: Settings) -> str:
    if not settings.is_live:
        return StableHashEmbeddings.model_id
    return f"openai:{settings.embedding_model}"


def build_embeddings(settings: Settings) -> Embeddings:
    if not settings.is_live:
        return StableHashEmbeddings()

    from langchain_openai import OpenAIEmbeddings

    kwargs: dict[str, object] = {
        "model": settings.embedding_model,
        "api_key": settings.openai_api_key,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAIEmbeddings(**kwargs)


def build_chat_model(settings: Settings):
    """只在 answerability gate 通过且处于 live 模式时才创建模型。"""

    if not settings.is_live:
        return None

    from langchain_openai import ChatOpenAI

    kwargs: dict[str, object] = {
        "model": settings.chat_model,
        "api_key": settings.openai_api_key,
        "temperature": 0,
        "timeout": settings.timeout_seconds,
        "max_retries": 2,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**kwargs)
