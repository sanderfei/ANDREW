"""Part 6：业务分支、Node 重试与失败补偿。

同一个文件对比三类情况：

1. 业务条件不满足：走普通条件边，不应抛异常或重试。
2. 暂时性依赖错误：RetryPolicy 只重跑失败 Node。
3. 重试耗尽：error_handler 接收 NodeError，更新状态后转入补偿分支。

它把“业务不满足”“暂时性技术失败”“重试后仍失败”分成三套机制处理，而不是全部依赖异常。
空请求
  → 条件边
  → business_fallback
  → finalize

有效请求 + 前两次临时失败
  → call_dependency 最多执行 3 次
  → 第三次成功
  → finalize

有效请求 + 三次都失败
  → error_handler(NodeError)
  → Command(update=补偿状态, goto="finalize")
  → finalize

运行：
    .venv/bin/python 5_langgraph_agentic_rag/part6_fault_tolerance.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, TypedDict

from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy

OFFICIAL_SOURCE = "https://docs.langchain.com/oss/python/langgraph/fault-tolerance"


# ConnectionError 是 Python 内置异常类；这里仅定义新的异常类型，不会抛异常。
# 真正抛出异常的是 DemoGateway.call() 中的 raise。
class TransientDependencyError(ConnectionError):
    """允许 RetryPolicy 重试的暂时性错误。"""


class FaultState(TypedDict, total=False):
    request: str
    valid: bool
    route: str
    dependency_result: str
    attempt_count: int
    status: str
    final_message: str


# DemoGateway.call()
#   → raise TransientDependencyError
#   → call_dependency 没有返回 partial update
#   → LangGraph 捕获异常
@dataclass
class DemoGateway:
    """先失败若干次再成功的确定性外部依赖替身。"""

    failures_before_success: int
    attempts: int = 0

    def call(self, request: str) -> str:
        self.attempts += 1
        if self.attempts <= self.failures_before_success:
            # 立即中断 DemoGateway.call() 并向上传导；
            # 调用方 call_dependency() 也没有 try/except，
            # 异常继续传给 LangGraph 的 Node 执行器
            raise TransientDependencyError(
                f"temporary failure on attempt {self.attempts}"
            )
        return f"dependency accepted: {request}"


def build_fault_tolerant_graph(gateway: DemoGateway):
    def validate_request(state: FaultState) -> FaultState:
        request = state.get("request", "").strip()
        if not request:
            return {
                "valid": False,
                "route": "business_fallback",
                "status": "invalid_request",
            }
        return {"request": request, "valid": True, "route": "call_dependency"}

    def choose_after_validation(
        state: FaultState,
    ) -> Literal["call_dependency", "business_fallback"]:
        return "call_dependency" if state["valid"] else "business_fallback"

    def call_dependency(state: FaultState) -> FaultState:
        result = gateway.call(state["request"])
        return {
            "dependency_result": result,
            "attempt_count": gateway.attempts,
            "status": "dependency_succeeded",
        }

    # error handler :第一个参数接收当前完整 State。
    # 第二个参数 参数名需要是 error，类型注解需要是 NodeError，LangGraph 才会自动注入错误对象
    # 返回值可以是FaultState，由于要跳转到 finalize，返回值也可以是 Command（update用来更新state）。
    def dependency_error_handler(
        _state: FaultState,
        error: NodeError,
    ) -> Command:
        return Command(
            update={
                "attempt_count": gateway.attempts,
                "route": "compensation",
                "status": "dependency_compensated",
                "dependency_result": (
                    f"{error.node} failed after retries: "
                    f"{type(error.error).__name__}"
                ),
            },
            goto="finalize",
        )

    def business_fallback(_state: FaultState) -> FaultState:
        return {
            "attempt_count": 0,
            "status": "business_fallback",
            "dependency_result": "请求为空，没有调用外部依赖。",
        }

    def finalize(state: FaultState) -> FaultState:
        return {
            "final_message": (
                f"status={state['status']}; "
                f"attempts={state.get('attempt_count', 0)}"
            )
        }

    # max_attempts=3 不是三次重试
    # = 第一次调用 + 最多两次重试
    retry_policy = RetryPolicy(
        # 第一次重试前等待 0.01 秒
        initial_interval=0.01,
        # 等待时间不递增
        backoff_factor=1.0,
        # 最长等待 0.01 秒
        max_interval=0.01,
        # 包含第一次调用，最多调用三次
        max_attempts=3,
        # 不增加随机抖动
        jitter=False,
        # 只有该异常触发重试
        retry_on=TransientDependencyError,
    )

    workflow = StateGraph(FaultState)
    workflow.add_node("validate_request", validate_request)
    # 注册 RetryPolicy 后，LangGraph 检查 retry_on 是否匹配；
    # 如果 call_dependency 报错，并且抛出 TransientDependencyError，就一直重试 call_dependency，直到重试次数耗尽，就调用 error_handler
    # 如果是其他异常就直接执行 error_handler

    workflow.add_node(
        "call_dependency",
        call_dependency,
        retry_policy=retry_policy,
        error_handler=dependency_error_handler,
        destinations=("finalize",),
    )
    workflow.add_node("business_fallback", business_fallback)
    workflow.add_node("finalize", finalize)
    workflow.add_edge(START, "validate_request")
    workflow.add_conditional_edges(
        "validate_request",
        choose_after_validation,
        {
            "call_dependency": "call_dependency",
            "business_fallback": "business_fallback",
        },
    )
    workflow.add_edge("call_dependency", "finalize")
    workflow.add_edge("business_fallback", "finalize")
    workflow.add_edge("finalize", END)
    return workflow.compile()


def run_demo() -> dict[str, FaultState]:
    eventually_available = DemoGateway(failures_before_success=2)
    success = build_fault_tolerant_graph(eventually_available).invoke(
        {"request": "学习 LangGraph 的容错边界"}
    )

    always_unavailable = DemoGateway(failures_before_success=99)
    compensated = build_fault_tolerant_graph(always_unavailable).invoke(
        {"request": "调用暂时不可用的依赖"}
    )

    unused_gateway = DemoGateway(failures_before_success=0)
    business_fallback = build_fault_tolerant_graph(unused_gateway).invoke(
        {"request": ""}
    )

    return {
        "retry_then_success": success,
        "retry_exhausted_then_compensated": compensated,
        "business_fallback_without_retry": business_fallback,
    }


# 启动命令：.venv/bin/python 5_langgraph_agentic_rag/part6_fault_tolerance.py
# 参数枚举：无命令行参数。
def main() -> int:
    print(
        json.dumps(
            {
                "official_source": OFFICIAL_SOURCE,
                "result": run_demo(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
