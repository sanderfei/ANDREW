"""Part 4：在同一数据集上运行两种回答策略，比较各项规则评分的平均值。

核心 SDK 接口：
- client.get_dataset(name)：获取平台数据集及样本，返回可运行实验的 DatasetClient。
- dataset.run_experiment(...)：逐条调用 task 生成回答，再调用 evaluators 评分，
  自动记录实验、Trace 和 Score；max_concurrency=2 限制每轮最多并发处理两条样本。
- Evaluation(name=..., value=..., comment=...)：封装一项评分结果，由实验运行器上报。

核心流程：同步数据集 → 依次运行 always_answer、evidence_only → 每条样本计算三个指标
→ 从 result.item_results 提取评分并汇总平均值。两个策略共享 batch，run_name 区分每轮运行。
offline 只在本地回答、评分；langfuse 模式才连接平台并保存实验。本课不调用真实模型。
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from uuid import uuid4

from _evaluation import (
    DEFAULT_DATASET,
    POLICIES,
    answer,
    load_cases,
    score_output,
    summarize,
    sync_dataset,
)
from _runtime import add_mode_argument, open_client


def evaluate_contract(*, input, output, expected_output, **kwargs):
    from langfuse import Evaluation

    return [
        Evaluation(
            name=name, value=value, comment="确定性合同评分；不代表真实模型准确率。"
        )
        for name, value in score_output(input, output, expected_output).items()
    ]


def run_demo(mode: str = "offline", dataset_name: str = DEFAULT_DATASET) -> dict:
    experiments = []
    with open_client(mode) as client:
        dataset = None
        if client:
            sync_dataset(client, dataset_name)
            dataset = client.get_dataset(dataset_name)

        batch = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid4().hex[:8]
        )

        # 测试两种策略
        for policy in POLICIES:
            run_name = f"{policy}-{batch}"
            if dataset is None:
                # 离线只计算同一批规则结果，不伪造平台 experiment ID 或 Trace。
                rows = []
                for case in load_cases():
                    output = answer(case["input"], policy)
                    rows.append(
                        {
                            "scores": score_output(
                                case["input"], output, case["expected_output"]
                            )
                        }
                    )
                url = None
                experiment_id = None
            else:
                # Dataset 模式传入的是 DatasetItem，其业务输入在 item.input。

                # 先定义处理单条样本的函数
                def task(*, item, _policy=policy, **kwargs):
                    return answer(item.input, _policy)

                result = dataset.run_experiment(
                    name="Part 4 回答策略对比",
                    run_name=run_name,
                    task=task,  # 生成回答的函数
                    evaluators=[evaluate_contract],  # 评分函数列表
                    max_concurrency=2,
                    metadata={"policy": policy, "batch": batch, "synthetic": True},
                )
                rows = [
                    {
                        "scores": {
                            evaluation.name: evaluation.value
                            for evaluation in item.evaluations
                        }
                    }
                    for item in result.item_results
                ]
                required = {"answerability", "citation_validity", "reference_match"}
                if not rows or any(set(row["scores"]) != required for row in rows):
                    raise RuntimeError(
                        "部分样本执行或评分失败，请查看平台实验中的错误。"
                    )
                url = result.dataset_run_url
                experiment_id = result.experiment_id
            experiments.append(
                {
                    "policy": policy,
                    "run_name": run_name,
                    "experiment_id": experiment_id,
                    "averages": summarize(rows),
                    "dataset_run_url": url,
                }
            )
    return {
        "mode": mode,
        "dataset_name": dataset_name,
        "experiments": experiments,
        "scope": "仅比较两种确定性策略；后续再换真实模型并加入人工校准的质量评测。",
    }


# 启动命令：.venv/bin/python 6_langfuse_observability/part4_experiment_comparison.py
# 平台模式：同上追加 --mode langfuse
# 参数枚举：--mode offline（默认）/ langfuse；--dataset-name 数据集名（默认 andrew-langfuse-contracts-v1）。
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_mode_argument(parser)
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET)
    args = parser.parse_args(argv)
    try:
        print(
            json.dumps(
                run_demo(args.mode, args.dataset_name), ensure_ascii=False, indent=2
            )
        )
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
