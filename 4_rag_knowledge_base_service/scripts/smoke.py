"""FastAPI 端到端冒烟：索引、问答、拒答、更新与删除。"""

from __future__ import annotations

import sys
import tempfile
import warnings
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# FastAPI 0.139 的 TestClient 仍可正常执行，但会对其内部 httpx 适配层发出
# 第三方弃用提示；本项目的普通 assert 冒烟不需要把该提示当作失败信号。
from starlette.exceptions import StarletteDeprecationWarning

warnings.filterwarnings(
    "ignore",
    message=r"Using `httpx` with `starlette\.testclient` is deprecated.*",
    category=StarletteDeprecationWarning,
)

from fastapi.testclient import TestClient

from app import create_app
from config import Settings


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="rag-kb-smoke-") as temporary:
        root = Path(temporary)
        source_dir = root / "source"
        source_dir.mkdir()
        (source_dir / "space.md").write_text(
            "# Space facts\nProject ORBITAL_BEACON is a deterministic smoke-test marker.\n",
            encoding="utf-8",
        )
        (source_dir / "policy.md").write_text(
            "# Policy\nAPI requests preserve X-Request-ID in the response header.\n",
            encoding="utf-8",
        )
        settings = Settings.from_env(
            mode="offline",
            embedding_mode="hash",
            source_dir=source_dir,
            runtime_dir=root / "runtime",
        )
        with TestClient(create_app(settings)) as client:
            initial_health = client.get("/health", headers={"X-Request-ID": "smoke-0"})
            assert initial_health.status_code == 200
            assert initial_health.json()["index_ready"] is False
            assert initial_health.json()["embedding_mode"] == "hash"
            assert initial_health.headers["X-Request-ID"] == "smoke-0"

            indexed = client.post("/v1/reindex", json={})
            assert indexed.status_code == 200, indexed.text
            assert indexed.json()["added_files"] == 2
            assert indexed.json()["indexed_chunks"] >= 2

            answer = client.post(
                "/v1/ask",
                headers={"X-Request-ID": "smoke-answer"},
                json={"question": "What is ORBITAL_BEACON?", "top_k": 3},
            )
            assert answer.status_code == 200, answer.text
            answer_payload = answer.json()
            assert answer.headers["X-Request-ID"] == "smoke-answer"
            assert answer_payload["request_id"] == "smoke-answer"
            assert answer_payload["answerable"] is True
            assert answer_payload["citations"]

            unknown = client.post(
                "/v1/ask",
                json={"question": "QUASAR_TIDE_9999?", "top_k": 3},
            )
            assert unknown.status_code == 200
            assert unknown.json()["answerable"] is False
            assert unknown.json()["citations"] == []

            unchanged = client.post("/v1/reindex", json={})
            assert unchanged.status_code == 200
            assert unchanged.json()["unchanged_files"] == 2

            policy = source_dir / "policy.md"
            policy.write_text(
                "# Policy\nAPI requests preserve X-Request-ID and use policy_version=two.\n",
                encoding="utf-8",
            )
            updated = client.post("/v1/reindex", json={})
            assert updated.status_code == 200
            assert updated.json()["updated_files"] == 1

            (source_dir / "space.md").unlink()
            removed = client.post("/v1/reindex", json={})
            assert removed.status_code == 200
            assert removed.json()["removed_files"] == 1

    print("Smoke test passed: health, reindex, ask, refusal, update, delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
