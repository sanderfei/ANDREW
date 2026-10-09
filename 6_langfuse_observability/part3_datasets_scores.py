"""Part 3：Dataset、规则评分与 Trace 关联；不调用模型或 LLM 裁判。

- Dataset 保存 input 和 expected_output；本例预期输出是可回答标记和必需关键词。
- 一个 case 是包含 id、input、expected_output 的样本字典；scores 是执行后计算出的指标字典。
- 样本来自本地 golden_cases.json；平台模式同步四条样本，固定 UUID 便于重复更新。
- answer 是本地规则函数：有证据时拼接文本；无证据时 evidence_only 拒答，always_answer 猜测。
- score_output 返回三个 0.0／1.0 分数：回答标记是否符合预期、引用是否合法、关键词／拒答文本是否匹配。
- 平台模式每条样本创建一条 Trace，通过 create_score(trace_id=...) 关联三个数值分数。
  scores.items() 逐项取出指标 name 和分数 value，三次提交都关联当前样本的同一 Trace。
- case.id 标识样本，observation.name 标识执行，Score.name 标识评分指标，三者用途不同。
- 上传 Dataset 不会自动建立实验关联；本课没有 Dataset Run，metadata.case_id 仅标识样本。
- summarize 在本地计算各项平均分；本例 evidence_only 为 1.0，always_answer 为 0.5。
- offline 只运行本地逻辑；langfuse 保存 Dataset、Trace、Score，退出时 flush、shutdown。
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import json

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


# 流程：同步数据集（平台模式）→ 逐条生成回答并评分 → 上报记录 → 汇总平均分。
def run_demo(
    mode: str = "offline",
    policy: str = "evidence_only",
    dataset_name: str = DEFAULT_DATASET,
) -> dict:
    rows = []
    with open_client(mode) as client:
        if client is not None:
            sync_dataset(client, dataset_name)
        # 评测始终读取本地样本，不从平台下载 Dataset。
        for case in load_cases():
            # 每条样本独立记录；离线模式使用空上下文，span 为 None。
            context = (
                client.start_as_current_observation(
                    name="part3-evaluate-case",
                    input=case["input"],
                    metadata={"case_id": case["id"], "policy": policy},
                )
                if client
                else nullcontext()
            )
            with context as span:
                output = answer(case["input"], policy)
                # 分数由本地规则计算，Langfuse 负责保存和展示。
                scores = score_output(case["input"], output, case["expected_output"])
                if span is not None:
                    span.update(output=output)
                    for name, value in scores.items():
                        # 每个指标创建一条 Score；name 区分指标，trace_id 关联当前样本的调用。
                        client.create_score(
                            trace_id=client.get_current_trace_id(),
                            name=name,
                            value=value,  # 本地算分 → 把分数交给 Langfuse 上报
                            data_type="NUMERIC",
                            comment="本地规则评分，不是 LLM 评分。",
                        )
                rows.append({"id": case["id"], "output": output, "scores": scores})
    return {
        "mode": mode,
        "policy": policy,
        "dataset_name": dataset_name,
        "averages": summarize(rows),
        "items": rows,
    }


# 启动命令：.venv/bin/python 6_langfuse_observability/part3_datasets_scores.py
# 平台模式：同上追加 --mode langfuse；坏基线：追加 --policy always_answer
# 参数枚举：--mode offline（默认）/ langfuse；--policy evidence_only（默认）/ always_answer；
# --dataset-name 数据集名（默认 andrew-langfuse-contracts-v1，平台模式会创建/更新该数据集）。
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_mode_argument(parser)
    parser.add_argument("--policy", choices=POLICIES, default="evidence_only")
    parser.add_argument("--dataset-name", default=DEFAULT_DATASET)
    args = parser.parse_args(argv)
    try:
        result = run_demo(args.mode, args.policy, args.dataset_name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
