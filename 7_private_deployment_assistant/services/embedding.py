"""本地 MiniLM 语义向量；不使用付费接口或教学 Hash 向量。"""

from functools import lru_cache
from pathlib import Path
import threading
import warnings


# 本地文件先被读取为文本、切成片段，再由 LocalEmbedding 调用模型，把每个片段转换成一组浮点数，也就是 Embedding 向量
class LocalEmbedding:
    def __init__(self, model: str, model_path: str, cache_dir: str):
        from fastembed import TextEmbedding

        options = {}
        if (Path(model_path) / "model_optimized.onnx").is_file():
            options["specific_model_path"] = model_path
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=".*paraphrase-multilingual-MiniLM-L12-v2 now uses mean pooling.*",
            )
            # Python 程序创建 TextEmbedding 对象
            # 加载本地模型文件到内存

            self.model = TextEmbedding(
                model_name=model, cache_dir=cache_dir, threads=2, **options
            )
        self.lock = threading.Lock()

    def documents(self, texts: list[str]) -> list[list[float]]:
        with self.lock:
            # 在本地执行模型计算 返回 384 维向量
            return [
                [float(value) for value in vector]
                for vector in self.model.passage_embed(texts)
            ]

    def query(self, text: str) -> list[float]:
        with self.lock:
            return [float(value) for value in next(self.model.query_embed(text))]


@lru_cache(maxsize=2)
def _cached_embedding(model: str, model_path: str, cache_dir: str) -> LocalEmbedding:
    return LocalEmbedding(model, model_path, cache_dir)


def get_embedding(settings) -> LocalEmbedding:
    return _cached_embedding(
        settings.model, str(settings.model_path), str(settings.cache_dir)
    )
