"""Part 5～10 的确定性高级冒烟，不调用模型或外部网络。"""

from __future__ import annotations

import json
import sys
import tempfile
import warnings
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from starlette.exceptions import StarletteDeprecationWarning

warnings.filterwarnings(
    "ignore",
    message=r"Using `httpx` with `starlette\.testclient` is deprecated.*",
    category=StarletteDeprecationWarning,
)

from fastapi.testclient import TestClient  # noqa: E402

from part10_evaluate import (  # noqa: E402
    build_evaluation_service,
    evaluate_service,
)
from part5_state_reducers_streaming import run_demo as run_stream_demo  # noqa: E402
from part6_fault_tolerance import run_demo as run_fault_demo  # noqa: E402
from part7_sqlite_persistence_time_travel import (  # noqa: E402
    run_demo as run_persistence_demo,
)
from part9_fastapi_runtime import create_app  # noqa: E402


def main() -> int:
    stream_result = run_stream_demo()
    assert stream_result["steps"] == [
        "collect_topic",
        "write_draft",
        "polish_answer",
    ]
    assert stream_result["same_id_message_count"] == 1
    assert stream_result["event_counts"]["updates"] == 3
    assert stream_result["event_counts"]["custom"] == 2
    assert "polish_answer" in stream_result["mermaid"]

    fault_result = run_fault_demo()
    retry_success = fault_result["retry_then_success"]
    compensated = fault_result["retry_exhausted_then_compensated"]
    business_fallback = fault_result["business_fallback_without_retry"]
    assert retry_success["attempt_count"] == 3
    assert retry_success["status"] == "dependency_succeeded"
    assert compensated["attempt_count"] == 3
    assert compensated["status"] == "dependency_compensated"
    assert business_fallback["attempt_count"] == 0

    with tempfile.TemporaryDirectory(
        prefix="langgraph-advanced-smoke-"
    ) as temporary:
        root = Path(temporary)
        persistence = run_persistence_demo(
            root / "checkpoints.sqlite",
            thread_id="advanced-smoke-persistence",
        )
        assert persistence["first"]["value"] == 2
        assert persistence["second"]["value"] == 5
        assert persistence["recovered_after_graph_rebuild"]["value"] == 5
        assert persistence["third"]["value"] == 6
        assert persistence["replayed_from_old_checkpoint"]["value"] == 5
        assert persistence["forked_with_amount_10"]["value"] == 12
        assert (
            persistence["history_count_after_fork"]
            > persistence["history_count_before_fork"]
        )

        service = build_evaluation_service(root / "assistant")
        evaluation = evaluate_service(service)
        assert evaluation["summary"]["passed_cases"] == 6
        assert evaluation["summary"]["contract_check_pass_rate"] == 1.0

        with TestClient(create_app(service)) as client:
            health = client.get(
                "/health",
                headers={"X-Request-ID": "advanced-smoke"},
            )
            assert health.status_code == 200
            assert health.headers["X-Request-ID"] == "advanced-smoke"

            knowledge = client.post(
                "/v1/invoke",
                json={"question": "What does ORBITAL_BEACON use?"},
            )
            assert knowledge.status_code == 200, knowledge.text
            assert knowledge.json()["route"] == "knowledge_grounded"
            assert knowledge.json()["citations"]

            first_turn = client.post(
                "/v1/invoke",
                json={
                    "question": "What does ORBITAL_BEACON use?",
                    "thread_id": "advanced-smoke-multi-turn",
                },
            ).json()
            second_turn = client.post(
                "/v1/invoke",
                json={
                    "question": "你好",
                    "thread_id": "advanced-smoke-multi-turn",
                },
            ).json()
            assert first_turn["turn_count"] == 1
            assert second_turn["turn_count"] == 2
            assert (
                second_turn["previous_question"]
                == "What does ORBITAL_BEACON use?"
            )
            assert second_turn["citations"] == []

            paused = client.post(
                "/v1/invoke",
                json={"question": "导出华东已完成订单营收"},
            )
            assert paused.status_code == 200, paused.text
            paused_payload = paused.json()
            assert paused_payload["status"] == "interrupted"

            resumed = client.post(
                (
                    f"/v1/threads/{paused_payload['thread_id']}"
                    "/resume"
                ),
                json={"decision": "approve", "note": "advanced smoke"},
            )
            assert resumed.status_code == 200, resumed.text
            assert resumed.json()["route"] == "export_completed"

            duplicate_resume = client.post(
                (
                    f"/v1/threads/{paused_payload['thread_id']}"
                    "/resume"
                ),
                json={"decision": "approve"},
            )
            assert duplicate_resume.status_code == 409

            with client.stream(
                "POST",
                "/v1/stream",
                json={
                    "question": "全部区域已完成订单数是多少？",
                    "thread_id": "advanced-smoke-stream",
                },
            ) as response:
                stream_body = "".join(response.iter_text())
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            assert "event: metadata" in stream_body
            assert "event: updates" in stream_body
            assert "event: result" in stream_body
            assert "business_metric" in stream_body

    summary = {
        "part5_reducer_streaming": True,
        "part6_retry_and_compensation": True,
        "part7_sqlite_history_replay_fork": True,
        "part8_routes_and_hitl": True,
        "part9_fastapi_and_sse": True,
        "part10_cases_passed": 6,
        "part10_contract_checks": 31,
    }
    print(
        "Advanced smoke test passed: "
        + json.dumps(summary, ensure_ascii=False, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
