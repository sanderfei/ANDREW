"""Part 14：用 @entrypoint 与 @task 编写可持久化的普通 Python 工作流。

Graph API 适合显式 State/Node/Edge；Functional API 保留 if、for、函数调用等
普通 Python 控制流，同时增加 task、checkpoint、retry、interrupt 和 streaming。

本文件不配置或调用模型，prepare_report() 只生成固定预览。
@entrypoint 的设计目的是让普通函数接入 LangGraph 运行时，由运行时管理任务、
检查点、暂停与恢复；模型只是工作流中可选的一步，可按需在 @task 内调用。
例如模型负责生成报告内容，工作流负责保存进度并等待人工审批。

本节核心知识点：
1. @entrypoint 把普通函数接入运行时，变成可用 invoke() 调用的工作流；@task 调用返回 Future，
   通过 .result() 取结果，并可用 RetryPolicy 配置失败重试。
2. checkpointer 按 thread_id 保存进度；interrupt() 暂停后，用同一 thread_id
   和 Command(resume=...) 恢复。恢复会从入口重放，已完成的 task 结果可复用。
3. previous 是 LangGraph 注入的上轮保存值；entrypoint.final 的 value 返回调用方，
   save 供同一线程的下一轮读取。一次 save 可保存包含多个字段的字典。
4. 先创建多个 task Future，再逐个调用 .result()，任务便有机会并发执行。
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import Command, RetryPolicy, interrupt


# invoke(Command(resume={"decision": "approve"}))
#   → LangGraph 读取同一 thread 的检查点和恢复值
#   → 从头执行 approval_workflow()
#   → 再次走到 prepare_report(...).result()
#       → 直接取得之前保存的报告结果，任务体不执行
#   → 再次走到 interrupt()
#       → 返回 {"decision": "approve"}
#   → human_decision 得到这个字典
#   → 返回 status="published"
def approval_workflow_demo(
    decision: Literal["approve", "reject"],
) -> dict[str, Any]:
    checkpointer = InMemorySaver()
    task_attempts = {"prepare_report": 0}

    # 把一次工作交给 Runtime 调度，调用后拿到 Future，再用 .result() 获取结果
    @task(
        retry_policy=RetryPolicy(
            max_attempts=2,
            initial_interval=0.01,
            backoff_factor=1.0,  # 等待间隔不增长
            jitter=False,  # 不加随机抖动
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

    # 把函数变成 LangGraph 工作流入口，用 .invoke() 启动或恢复
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
                "published" if human_decision["decision"] == "approve" else "rejected"
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


# previous 是 LangGraph 约定的注入参数名
# 每轮 entrypoint.final 只有一个 save 参数。
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
        # entrypoint.final[dict[str, int], int]
        return entrypoint.final(
            value={"previous": old_value, "amount": amount, "current": new_value},
            # 保存到检查点，成为同一线程下一次调用的 previous
            save=new_value,
        )

    config = {"configurable": {"thread_id": "functional-previous"}}
    first = accumulate.invoke(2, config=config)
    second = accumulate.invoke(5, config=config)
    assert first["current"] == 2
    assert second == {"previous": 2, "amount": 5, "current": 7}
    return {"first": first, "second": second}

# 要留多个数据，就把它们组成一个字典等结构保存；下一轮的 previous 会收到整个结构
def multiple_previous_fields_demo() -> dict[str, Any]:
    @entrypoint(checkpointer=InMemorySaver())
    def accumulate_with_count(
        amount: int,
        *,
        previous: dict[str, int] | None = None,
    ) -> entrypoint.final[dict[str, Any], dict[str, int]]:
        old_state = previous or {"total": 0, "count": 0}
        new_state = {
            "total": old_state["total"] + amount,
            "count": old_state["count"] + 1,
        }
        # 一次 save 保存整个字典；下一轮的 previous 收到这两个字段。
        return entrypoint.final(
            value={"previous": old_state, "amount": amount, "current": new_state},
            save=new_state,
        )

    config = {"configurable": {"thread_id": "functional-previous-fields"}}
    first = accumulate_with_count.invoke(2, config=config)
    second = accumulate_with_count.invoke(5, config=config)
    assert first["current"] == {"total": 2, "count": 1}
    assert second == {
        "previous": {"total": 2, "count": 1},
        "amount": 5,
        "current": {"total": 7, "count": 2},
    }
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

    # 虽然 .result() 按顺序调用，三个任务已经可以同时运行。因此，等待第一个结果期间，其他任务也在执行。最终结果列表仍按输入顺序排列
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
        "multiple_previous_fields": multiple_previous_fields_demo(),
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
