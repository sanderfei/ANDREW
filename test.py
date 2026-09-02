"""循环调用 GLM，直到累计输入和输出 token 都严格超过 10M。

这是一个真实的长时间、高消耗请求脚本。API Key 只从项目根目录 ``.env`` 或
系统环境变量 ``ZHIPU_API_KEY`` 读取，不会写入源码或日志。
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from typing import Any

import requests

from learning_runtime import require_env

API_URL = "https://ai-hub.digiwincloud.com.cn/v1/chat/completions"
MODEL = "ep-cl-glm"
TARGET_TOKENS = 10_000_000
REQUEST_INTERVAL_SECONDS = 1
MAX_TOKENS_PER_REQUEST = 2000
REQUEST_TIMEOUT_SECONDS = 300
INPUT_REPEAT_COUNT = 2000

TOPICS = (
    "Kubernetes 集群扩容",
    "Go 微服务性能优化",
    "RAG 检索质量治理",
    "分布式数据库容灾",
    "消息队列积压处理",
    "API 网关限流",
    "云原生可观测性",
    "大模型 Agent 安全",
    "多租户权限隔离",
    "离线安装包交付",
    "向量数据库容量规划",
    "持续交付流水线",
)
TASKS = (
    "设计一套完整技术方案",
    "分析可能出现的故障并给出排查顺序",
    "比较三种可行实现并说明取舍",
    "制定分阶段迁移与回滚计划",
    "给出性能压测方案和验收指标",
    "进行安全威胁建模并提出防护措施",
    "设计监控、告警和事故复盘机制",
    "从成本、可靠性和维护性三个维度评审方案",
)
CONSTRAINTS = (
    "不能中断现有业务",
    "只能使用开源组件",
    "需要支持跨机房部署",
    "团队只有三名工程师",
    "必须具备一键回滚能力",
    "要求所有关键操作可审计",
    "需要兼容离线网络环境",
    "月度资源成本需要可预测",
)
MATERIAL_SENTENCES = (
    "系统包含计算、存储、网络和控制面，需要分析各层依赖。",
    "业务同时存在高峰流量、批处理任务和严格的可用性要求。",
    "现网保留历史组件，新方案必须考虑兼容、迁移与回滚。",
    "多个团队共同维护平台，需要清晰的权限、审计和责任边界。",
    "故障可能跨越应用、容器、节点和外部依赖，需要完整证据链。",
    "容量会持续增长，方案需要量化吞吐、延迟、存储和成本。",
    "部署环境网络受限，依赖、镜像和安装包都需要离线准备。",
    "系统涉及敏感数据，必须覆盖认证、授权、加密和密钥轮换。",
)


def build_question(request_number: int) -> str:
    """根据轮次生成不同主题、任务、约束和规模参数的问题。"""

    index = request_number - 1
    topic = TOPICS[index % len(TOPICS)]
    task = TASKS[(index // len(TOPICS)) % len(TASKS)]
    constraint = CONSTRAINTS[
        (index // (len(TOPICS) * len(TASKS))) % len(CONSTRAINTS)
    ]
    node_count = 20 + (request_number * 17) % 480
    peak_qps = 5_000 + (request_number * 7_919) % 195_000
    availability = "99.99%" if request_number % 2 else "99.95%"
    return (
        f"请求编号 {request_number}：针对{topic}，{task}。"
        f"当前规模为 {node_count} 个节点、峰值 {peak_qps} QPS，"
        f"可用性目标 {availability}，并且{constraint}。"
    )


def build_prompt(request_number: int) -> str:
    """构造较长输入，并要求模型尽量使用本轮输出额度。"""

    question = build_question(request_number)
    material_sentence = MATERIAL_SENTENCES[
        (request_number - 1) % len(MATERIAL_SENTENCES)
    ]
    input_material = material_sentence * INPUT_REPEAT_COUNT
    return (
        f"这是第 {request_number} 次负载测试请求。\n"
        f"本轮问题：{question}\n"
        "请直接围绕本轮问题生成连续编号的简短建议，每条只写一句，"
        "格式为“建议N：内容”。不要进行长篇推理，不要写总结，"
        f"尽量使用完本次 {MAX_TOKENS_PER_REQUEST} 个输出 token。\n"
        f"背景材料：{input_material}"
    )


def extract_usage(response_data: dict[str, Any]) -> tuple[int, int]:
    """兼容 OpenAI 风格的两组 token usage 字段名。"""

    usage = response_data.get("usage")
    if not isinstance(usage, dict):
        raise RuntimeError("模型响应缺少 usage，无法累计 token")

    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        raise RuntimeError(f"模型响应中的 usage 格式不正确：{usage!r}")
    if input_tokens < 0 or output_tokens < 0:
        raise RuntimeError(f"模型响应中的 token 数不能为负数：{usage!r}")
    return input_tokens, output_tokens


def call_model(api_key: str, request_number: int) -> tuple[int, int]:
    """调用一次模型，只返回本次输入和输出 token 数。"""

    print(f"[{request_number}] 问题：{build_question(request_number)}")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "直接回答，不展示思考过程。"},
            {"role": "user", "content": build_prompt(request_number)},
        ],
        "thinking": {"type": "disabled"},
        "max_tokens": MAX_TOKENS_PER_REQUEST,
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    # requests.post(json=payload) 默认会把中文转义成 \uXXXX，导致请求体接近翻倍。
    # 显式使用 UTF-8 JSON，避免大 Prompt 被网关按请求体大小直接断开。
    request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    response = requests.post(
        API_URL,
        headers=headers,
        data=request_body,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return extract_usage(response.json())


def run_loop(api_key: str) -> tuple[int, int, int]:
    """每轮间隔 1 秒，两个累计值都超过目标后结束。"""

    total_input_tokens = 0
    total_output_tokens = 0
    completed_requests = 0

    for request_number in itertools.count(1):
        started_at = time.monotonic()
        try:
            input_tokens, output_tokens = call_model(api_key, request_number)
        except requests.HTTPError as exc:
            elapsed_seconds = time.monotonic() - started_at
            status_code = exc.response.status_code if exc.response is not None else None
            if (
                status_code is not None
                and 400 <= status_code < 500
                and status_code not in {408, 429}
            ):
                raise
            print(
                f"[{request_number}] 请求失败，耗时 {elapsed_seconds:.2f}s，"
                f"本轮不累计：HTTP {status_code}"
            )
        except requests.RequestException as exc:
            elapsed_seconds = time.monotonic() - started_at
            print(
                f"[{request_number}] 请求失败，耗时 {elapsed_seconds:.2f}s，"
                f"本轮不累计：{type(exc).__name__}: {exc}"
            )
        else:
            elapsed_seconds = time.monotonic() - started_at
            completed_requests += 1
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            print(
                f"[{request_number}] 本次 input={input_tokens:,}, output={output_tokens:,}; "
                f"累计 input={total_input_tokens:,}, output={total_output_tokens:,}; "
                f"耗时 {elapsed_seconds:.2f}s"
            )

            if (
                total_input_tokens > TARGET_TOKENS
                and total_output_tokens > TARGET_TOKENS
            ):
                print(
                    "目标完成：累计输入和输出 token 均已严格超过 "
                    f"{TARGET_TOKENS:,}。"
                )
                break

        time.sleep(REQUEST_INTERVAL_SECONDS)

    return completed_requests, total_input_tokens, total_output_tokens


# 启动命令：
#   .venv/bin/python test.py --confirm-10m
# 参数枚举：--confirm-10m（必填确认开关；不传时不会调用模型）。
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="每隔 1 秒调用 ep-cl-glm，直到输入/输出 token 均超过 10M"
    )
    parser.add_argument(
        "--confirm-10m",
        action="store_true",
        help="确认执行至少累计 10M 输入 token 和 10M 输出 token 的真实请求",
    )
    args = parser.parse_args(argv)
    if not args.confirm_10m:
        parser.error("该脚本会产生至少 20M token 用量；确认后请传 --confirm-10m")

    api_key = require_env("ZHIPU_API_KEY")
    try:
        completed, input_tokens, output_tokens = run_loop(api_key)
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，已停止请求。")
        return 130

    print(
        f"成功请求次数={completed:,}, "
        f"累计输入 token={input_tokens:,}, 累计输出 token={output_tokens:,}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
