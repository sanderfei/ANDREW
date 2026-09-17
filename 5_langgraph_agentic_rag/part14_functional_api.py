"""Part 14：用 @entrypoint 与 @task 编写可持久化的普通 Python 工作流。

Graph API 适合显式 State/Node/Edge；Functional API 保留 if、for、函数调用等
普通 Python 控制流，同时增加 task、checkpoint、retry、interrupt 和 streaming。
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import Command, RetryPolicy, interrupt


def approval_workflow_demo(
    decision: Literal["approve", "reject"],
) -> dict[str, Any]:
    checkpointer = InMemorySaver()
    task_attempts = {"prepare_report": 0}

    @task(
        retry_policy=RetryPolicy(
            max_attempts=2,
            initial_interval=0.01,
            backoff_factor=1.0,
            jitter=False,
            retry_on=ConnectionError,
        )
    )
    def prepare_report(report_name: str) -> dict[str, str]:
        task_attempts["prepare_report"] += 1
        if task_attempts["prepare_report"] == 1:
            raise ConnectionError("模拟第一次准备报告失败")
        return {
            "report_name": report_name,
            "preview": f"{report_name} 的确定性预览",
        }

    @entrypoint(checkpointer=checkpointer)
    def approval_workflow(request: dict[str, str]) -> dict[str, Any]:
        # @task 调用返回 future；result() 取得任务返回值。
        prepared = prepare_report(request["report_name"]).result()
        human_decision = interrupt(
            {
                "question": "是否发布报告？",
                "allowed_decisions": ["approve", "reject"],
                "preview": prepared["preview"],
            }
        )
        return {
            "status": (
                "published"
                if human_decision["decision"] == "approve"
                else "rejected"
            ),
            "report": prepared,
            "decision": human_decision,
        }

    config = {"configurable": {"thread_id": f"functional-hitl-{decision}"}}
    interrupted = approval_workflow.invoke(
        {"report_name": "functional-api-report.md"},
        config=config,
    )
    attempts_before_resume = task_attempts["prepare_report"]
    resumed = approval_workflow.invoke(
        Command(resume={"decision": decision}),
        config=config,
    )
    attempts_after_resume = task_attempts["prepare_report"]

    assert attempts_before_resume == 2
    # 恢复时 entrypoint 从函数开头重放，但已完成 task 的结果来自 checkpoint。
    assert attempts_after_resume == attempts_before_resume
    return {
        "interrupt": interrupted["__interrupt__"][0].value,
        "result": resumed,
        "task_attempts_before_resume": attempts_before_resume,
        "task_attempts_after_resume": attempts_after_resume,
        "task_reexecuted_on_resume": attempts_after_resume > attempts_before_resume,
    }


def previous_state_demo() -> dict[str, Any]:
    @entrypoint(checkpointer=InMemorySaver())
    def accumulate(
        amount: int,
        *,
        previous: int | None = None,
    ) -> entrypoint.final[dict[str, int], int]:
        old_value = previous or 0
        new_value = old_value + amount
        # value 返回调用方；save 才是下一轮 previous 收到的值。
        return entrypoint.final(
            value={"previous": old_value, "amount": amount, "current": new_value},
            save=new_value,
        )

    config = {"configurable": {"thread_id": "functional-previous"}}
    first = accumulate.invoke(2, config=config)
    second = accumulate.invoke(5, config=config)
    assert first["current"] == 2
    assert second == {"previous": 2, "amount": 5, "current": 7}
    return {"first": first, "second": second}


def parallel_tasks_demo() -> dict[str, Any]:
    @task
    def inspect_section(section: str) -> dict[str, Any]:
        started = time.perf_counter()
        time.sleep(0.03)
        finished = time.perf_counter()
        return {
            "section": section,
            "finding": f"{section} 已检查",
            "started": started,
            "finished": finished,
        }

    @entrypoint()
    def inspect_sections(sections: list[str]) -> list[dict[str, Any]]:
        # 先创建所有 future，再逐个 result；tasks 可以并发执行。
        futures = [inspect_section(section) for section in sections]
        return [future.result() for future in futures]

    results = inspect_sections.invoke(["runtime", "memory", "streaming"])
    overlap = any(
        max(left["started"], right["started"])
        < min(left["finished"], right["finished"])
        for index, left in enumerate(results)
        for right in results[index + 1 :]
    )
    assert overlap is True
    return {"overlap_observed": overlap, "results": results}


def run_demo(
    decision: Literal["approve", "reject"] = "approve",
) -> dict[str, Any]:
    return {
        "approval_workflow": approval_workflow_demo(decision),
        "previous_and_final": previous_state_demo(),
        "parallel_tasks": parallel_tasks_demo(),
        "comparison": {
            "graph_api": "显式 State、Reducer、Node、Edge，适合可视化复杂拓扑。",
            "functional_api": "普通 Python 控制流加 @entrypoint/@task，底层仍运行在 LangGraph Runtime。",
        },
    }


# 启动命令：
#   .venv/bin/python 5_langgraph_agentic_rag/part14_functional_api.py
#   .venv/bin/python 5_langgraph_agentic_rag/part14_functional_api.py --decision reject
# 参数枚举：--decision approve（默认）/ reject。
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LangGraph Functional API 教学")
    parser.add_argument(
        "--decision",
        choices=("approve", "reject"),
        default="approve",
        help="Functional API interrupt 的恢复决策",
    )
    args = parser.parse_args(argv)
    print(json.dumps(run_demo(args.decision), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
