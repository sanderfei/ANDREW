"""目录 5 的确定性端到端冒烟，不调用外部模型或网络。"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from agentic_rag import (  # noqa: E402
    build_agentic_rag_graph,
    initial_state,
    public_result,
)
from local_rag_adapter import (  # noqa: E402
    LocalKnowledgeRetriever,
    build_tutorial_settings,
)
from part3_persistence_hitl import run_approval_demo  # noqa: E402
from part4_readonly_sql_tools import (  # noqa: E402
    _readonly_connection,
    build_business_metric_tool,
    initialize_demo_database,
)


def _assert_readonly_database(database_path: Path) -> None:
    connection = _readonly_connection(database_path)
    try:
        try:
            connection.execute(
                "INSERT INTO orders(id, region, amount, status) "
                "VALUES (99, '华东', 1, 'completed')"
            )
        except sqlite3.OperationalError as exc:
            assert "readonly" in str(exc).lower()
        else:
            raise AssertionError("mode=ro 数据库连接不应允许 INSERT。")
    finally:
        connection.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="langgraph-rag-smoke-") as temporary:
        root = Path(temporary)
        source_dir = root / "source"
        source_dir.mkdir()
        (source_dir / "runtime.md").write_text(
            "# Runtime\n"
            "Project ORBITAL_BEACON uses local MiniLM embeddings and Chroma.\n",
            encoding="utf-8",
        )
        (source_dir / "citations.md").write_text(
            "# Citations\n"
            "Every grounded answer keeps a stable chunk_id for source validation.\n",
            encoding="utf-8",
        )
        settings = build_tutorial_settings(
            mode="offline",
            embedding_mode="hash",
            source_dir=source_dir,
            runtime_dir=root / "rag-runtime",
        )
        retriever = LocalKnowledgeRetriever(settings)
        index_stats = retriever.ensure_index(reset=True)
        assert index_stats.added_files == 2

        graph = build_agentic_rag_graph(
            retriever,
            model=None,
            top_k=3,
            max_context_chars=2000,
        )

        known = public_result(
            graph.invoke(
                initial_state(
                    "What does ORBITAL_BEACON use?",
                    max_rewrites=1,
                )
            )
        )
        assert known["route"] == "grounded_answer"
        assert known["answerable"] is True
        assert known["grounded"] is True
        assert known["citations"]
        citation_ids = {
            citation["chunk_id"] for citation in known["citations"]
        }
        assert citation_ids.issubset(set(known["used_evidence_ids"]))

        unknown = public_result(
            graph.invoke(
                initial_state("What is QUASAR_TIDE_9999?", max_rewrites=1)
            )
        )
        assert unknown["route"] == "refused"
        assert unknown["answerable"] is False
        assert unknown["citations"] == []
        assert unknown["retrieval_attempts"] == 2
        assert unknown["rewrite_count"] == 1

        smalltalk = public_result(
            graph.invoke(initial_state("你好", max_rewrites=1))
        )
        assert smalltalk["route"] == "direct"
        assert smalltalk["retrieval_attempts"] == 0
        assert smalltalk["citations"] == []

        approved = run_approval_demo(
            "approve",
            thread_id="smoke-approval",
        )
        rejected = run_approval_demo(
            "reject",
            thread_id="smoke-rejection",
        )
        assert approved["approved"] is True
        assert rejected["approved"] is False

        database_path = root / "business.db"
        initialize_demo_database(database_path)
        metric_tool = build_business_metric_tool(database_path)
        revenue = json.loads(
            metric_tool.invoke(
                {
                    "metric": "completed_revenue",
                    "region": "all",
                }
            )
        )
        east_count = json.loads(
            metric_tool.invoke(
                {
                    "metric": "completed_order_count",
                    "region": "华东",
                }
            )
        )
        assert revenue["value"] == 400.5
        assert east_count["value"] == 1
        _assert_readonly_database(database_path)

        invalid_metric_rejected = False
        try:
            metric_tool.invoke(
                {
                    "metric": "delete_all_orders",
                    "region": "all",
                }
            )
        except Exception:
            invalid_metric_rejected = True
        assert invalid_metric_rejected

        summary = {
            "index_files": index_stats.scanned_files,
            "known_route": known["route"],
            "known_citations": len(known["citations"]),
            "unknown_route": unknown["route"],
            "unknown_retrieval_attempts": unknown["retrieval_attempts"],
            "smalltalk_route": smalltalk["route"],
            "hitl_approve_and_reject": True,
            "readonly_sql_revenue": revenue["value"],
            "invalid_metric_rejected": invalid_metric_rejected,
        }

    print(
        "Smoke test passed: "
        + json.dumps(summary, ensure_ascii=False, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
