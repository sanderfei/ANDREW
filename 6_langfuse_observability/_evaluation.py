"""规则评测的公共业务逻辑；固定证据样本，不伪装成真实 RAG 或 LLM 质量评测。"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from uuid import NAMESPACE_URL, uuid5

DEFAULT_DATASET = "andrew-langfuse-contracts-v1"
POLICIES = ("always_answer", "evidence_only")
REFUSAL = "当前资料不足，无法回答。"


def load_cases() -> list[dict]:
    path = Path(__file__).resolve().parent / "data" / "golden_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def answer(input: dict, policy: str) -> dict:
    if policy not in POLICIES:
        raise ValueError("未知回答策略。")
    evidence = input["evidence"]
    if evidence:
        return {
            "answer": "；".join(item["text"] for item in evidence),
            "answerable": True,
            "citations": [item["id"] for item in evidence],
        }
    if policy == "evidence_only":
        return {"answer": REFUSAL, "answerable": False, "citations": []}
    # 故意构造的坏基线：证据不足时仍作答且编造来源，让实验能发现回归。
    return {
        "answer": "根据我的猜测，下周一。",
        "answerable": True,
        "citations": ["invented"],
    }


def score_output(input: dict, output: dict, expected_output: dict) -> dict[str, float]:
    valid_ids = {item["id"] for item in input["evidence"]}
    cited_ids = set(output["citations"])
    citations_valid = (
        bool(cited_ids) and cited_ids <= valid_ids
        if output["answerable"]
        else not cited_ids
    )
    reference_match = (
        all(term in output["answer"] for term in expected_output["required_terms"])
        if expected_output["answerable"]
        else output["answer"] == REFUSAL
    )
    return {
        "answerability": float(output["answerable"] == expected_output["answerable"]),
        "citation_validity": float(citations_valid),
        "reference_match": float(reference_match),
    }


def summarize(rows: list[dict]) -> dict[str, float]:
    if not rows:
        raise ValueError("没有可评测的样本。")
    return {
        name: mean(row["scores"][name] for row in rows) for name in rows[0]["scores"]
    }


def sync_dataset(client, name: str) -> None:
    """写入本课专用数据集；固定 item ID 使重复运行更新同一份样本。"""

    # 创建数据集
    client.create_dataset(
        name=name, description="四条合成样本，仅验证评测流程与拒答/引用合同。"
    )
    for case in load_cases():
        # 按 ID 写入：ID 不存在时创建，已存在时更新
        # ID 唯一标识
        # 等号左边的参数名由 Langfuse SDK 定义，不能随意改名。
        # 此方法只有 dataset_name 必填；下面的 id、input、expected_output、metadata 都可选。
        # case 的键名由本项目设计；当前代码直接取值，所以每条 case 必须有
        # "id"、"input"、"expected_output"。改键名时，也要同步修改读取它们的代码。
        client.create_dataset_item(
            dataset_name=name,  # 固定 SDK 参数名；值来自变量 name
            id=str(uuid5(NAMESPACE_URL, f"andrew-langfuse:{name}:{case['id']}")),
            input=case["input"],  # 左边是 SDK 参数名，右边是自定义的 case 键名
            expected_output=case["expected_output"],  # 两边同名，但属于不同层次
            # metadata 是固定 SDK 参数名；"case_id"、"synthetic" 是自定义的字典键名。
            metadata={"case_id": case["id"], "synthetic": True},
        )
