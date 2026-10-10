"""Part 3：Dataset、规则评分与 Trace 关联；不调用模型或 LLM 裁判。

- Dataset 保存 input 和 expected_output；本例预期输出是可回答标记和必需关键词。
- 一个 case 是包含 id、input、expected_output 的样本字典；scores 是执行后计算出的指标字典。
- 样本来自本地 golden_cases.json；平台模式同步四条样本，固定 UUID 便于重复更新。

- 平台模式每条样本创建一条 Trace，通过 create_score(trace_id=...) 关联三个数值分数。
  scores.items() 逐项取出指标 name 和分数 value，三次提交都关联当前样本的同一 Trace。
- case.id 标识样本，observation.name 标识执行，Score.name 标识评分指标，三者用途不同。

Langfuse 数据如何保存（本地部署）：
- Python 程序通过 SDK 向 LANGFUSE_BASE_URL 指定的服务发送 HTTP 请求，
  本地部署地址示例为 http://localhost:3000；SDK 不直接把这些记录写成项目目录中的文件。
- create_dataset / create_dataset_item：Dataset 和 Item 由服务端保存到 PostgreSQL。
- start_as_current_observation：生成追踪记录；Trace、Observation 由服务端保存到 ClickHouse。
- create_score：把本地计算的分数上报给服务端，Score 保存到 ClickHouse。
- 原始上报事件和图片、音频等附件使用对象存储；本地 Compose 部署使用 MinIO。
- 本地 Compose 为存储服务挂载 Docker 数据卷，数据库和对象存储最终将数据持久化到本机磁盘。
- 追踪记录先在 SDK 中缓冲再上报，退出时 open_client 调用 flush、shutdown；
  服务端异步处理也需要时间，所以发送完成后页面可能稍后才显示记录。
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
    mode: str = "langfuse",
    policy: str = "evidence_only",
    dataset_name: str = DEFAULT_DATASET,
) -> dict:
    rows = []
    with open_client(mode) as client:
        if client is not None:
            sync_dataset(client, dataset_name)
        for case in load_cases():
            # 一个case对应一个 Trace
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
                # 分数由本地规则计算，三个指标打分
                scores = score_output(case["input"], output, case["expected_output"])
                if span is not None:
                    span.update(output=output)
                    # Trace 关联三条 Score
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
