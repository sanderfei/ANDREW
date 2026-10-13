from dataclasses import dataclass
from typing import Protocol


@dataclass
class VectorChunk:
    id: str
    document_id: str
    content: str
    vector: list[float]
    metadata: dict


class VectorStore(Protocol):
    def initialize(self) -> None: ...
    def status(self) -> dict: ...
    def replace_document(self, document_id: str, chunks: list[VectorChunk]) -> None: ...
    def delete_document(self, document_id: str) -> None: ...
    def search(self, vector: list[float], limit: int, filters: dict) -> list[dict]: ...
    def close(self) -> None: ...
