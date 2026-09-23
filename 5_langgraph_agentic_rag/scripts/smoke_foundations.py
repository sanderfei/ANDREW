"""L13～L15 与 Part 11～14 的离线基础补充冒烟。"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LANGCHAIN_DIR = REPOSITORY_ROOT / "2_langchain"
LANGGRAPH_DIR = REPOSITORY_ROOT / "5_langgraph_agentic_rag"
for directory in (LANGCHAIN_DIR, LANGGRAPH_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from L13_Runtime_Context_Store import run_demo as run_runtime_store  # noqa: E402
from L14_Agent_Middleware import hitl_demo, run_demo as run_middleware  # noqa: E402
from L15_MCP_Integration import run_demo as run_mcp  # noqa: E402
from part11_parallel_send import run_demo as run_parallel_send  # noqa: E402
from part12_subgraphs import run_demo as run_subgraphs  # noqa: E402
from part13_async_streaming import run_demo as run_async_streaming  # noqa: E402
from part14_functional_api import run_demo as run_functional_api  # noqa: E402


# 启动命令：
#   .venv/bin/python 5_langgraph_agentic_rag/scripts/smoke_foundations.py
# 参数枚举：无；全程使用本地 Fake Model、本地 stdio MCP 和内存存储。
def main() -> int:
    runtime_store = run_runtime_store()
    assert runtime_store["state"]["tool_command_update"] == "default_city"
    assert runtime_store["store"]["search_result_count"] == 1

    middleware = run_middleware("approve")
    rejected = hitl_demo("reject")
    assert middleware["lifecycle"]["tool_attempts"] == 2
    assert middleware["lifecycle"]["dynamic_request"]["selected_tools"] == [
        "flaky_course_lookup"
    ]
    assert middleware["model_retry"]["attempts"] == 2
    assert all(
        "[REDACTED_EMAIL]" in message["content"]
        for message in middleware["pii"]["input_and_output_messages"]
    )
    assert middleware["human_in_the_loop"]["published_reports"]
    assert rejected["published_reports"] == []

    mcp = asyncio.run(run_mcp())
    assert {item["name"] for item in mcp["discovered_tools"]} == {
        "course_lookup",
        "add_numbers",
    }
    assert mcp["direct_calls"]["add_numbers"]["text"] == "12"

    parallel = run_parallel_send(max_concurrency=2)
    assert parallel["dynamic_send"]["task_count"] == 3
    assert parallel["conflict_without_reducer"]["error_type"] == "InvalidUpdateError"

    subgraphs = run_subgraphs()
    assert subgraphs["second_run"]["child_turn_seen"] == 2
    assert subgraphs["command_parent"]["status"] == "handled:escalated"

    async_streaming = asyncio.run(run_async_streaming(max_concurrency=2))
    assert async_streaming["stream"]["joined_tokens"] == "异步资料汇总完成"
    assert async_streaming["timeout_control"]["error_type"] == "NodeTimeoutError"

    functional = run_functional_api("approve")
    assert functional["approval_workflow"]["task_reexecuted_on_resume"] is False
    assert functional["previous_and_final"]["second"]["current"] == 7

    summary = {
        "l13_runtime_context_store": True,
        "l14_middleware": True,
        "l15_mcp_tools_resources_prompts": True,
        "part11_parallel_send": True,
        "part12_subgraphs": True,
        "part13_async_full_streaming": True,
        "part14_functional_api": True,
    }
    print(
        "Foundation supplement smoke passed: "
        + json.dumps(summary, ensure_ascii=False, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
