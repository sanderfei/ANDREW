"""Part 10：对 Graph 的路由轨迹、引用与权限合同做确定性评测。

官方测试教程建议为每个测试创建独立 Graph / checkpointer，并同时验证 Node
和端到端路径。本课不追求“回答文风分数”，而是检查更稳定的工程合同：

- 问题是否进入正确分支；
- 知识回答是否有真实 citation，拒答是否没有 citation；
- SQL 是否返回固定白名单结果；
- 敏感导出是否先 interrupt；
- approve / reject 后是否走正确轨迹。

运行：
    .venv/bin/python 5_langgraph_agentic_rag/part10_evaluate.py
"""

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from local_rag_adapter import (
    LocalKnowledgeRetriever,
    build_tutorial_settings,
)
from part4_readonly_sql_tools import initialize_demo_database
from part8_controlled_multi_tool_graph import (
    ControlledAssistantService,
    build_tutorial_service,
)


OFFICIAL_SOURCE = "https://docs.langchain.com/oss/python/langgraph/test"


@dataclass(frozen=True)
class EvaluationResult:
    name: str
    passed: bool
    checks: dict[str, bool]
    route: str
    trajectory: list[str]
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "checks": self.checks,
            "route": self.route,
            "trajectory": self.trajectory,
            "detail": self.detail,
        }


def _trajectory(result: dict[str, Any]) -> list[str]:
    return [
        str(event.get("node"))
        for event in result.get("audit_log", [])
        if isinstance(event, dict) and event.get("node")
    ]


def _result(
    *,
    name: str,
    response: dict[str, Any],
    checks: dict[str, bool],
    detail: str,
) -> EvaluationResult:
    return EvaluationResult(
        name=name,
        passed=all(checks.values()),
        checks=checks,
        route=str(response["route"]),
        trajectory=_trajectory(response),
        detail=detail,
    )


def evaluate_service(
    service: ControlledAssistantService,
) -> dict[str, Any]:
    results: list[EvaluationResult] = []

    known = service.ask("What does ORBITAL_BEACON use?")
    known_ids = {
        str(citation.get("chunk_id"))
        for citation in known["citations"]
        if isinstance(citation, dict)
    }
    results.append(
        _result(
            name="known_knowledge_is_grounded",
            response=known,
            checks={
                "route": known["route"] == "knowledge_grounded",
                "answerable": known["answerable"] is True,
                "grounded": known["grounded"] is True,
                "citations_present": bool(known["citations"]),
                "citation_ids_present": bool(known_ids),
                "trajectory": _trajectory(known)
                == ["route_request", "retrieve_knowledge"],
            },
            detail="已知知识问题必须经过检索并带真实 chunk_id。",
        )
    )

    unknown = service.ask("What is QUASAR_TIDE_9999?")
    results.append(
        _result(
            name="unknown_knowledge_is_refused",
            response=unknown,
            checks={
                "route": unknown["route"] == "knowledge_refused",
                "not_answerable": unknown["answerable"] is False,
                "not_grounded": unknown["grounded"] is False,
                "no_citations": unknown["citations"] == [],
                "trajectory": _trajectory(unknown)
                == ["route_request", "retrieve_knowledge"],
            },
            detail="未知知识不能凭模型记忆补答案或伪造引用。",
        )
    )

    metric = service.ask("全部区域已完成订单营收是多少？")
    metric_result = metric.get("metric_result") or {}
    results.append(
        _result(
            name="business_metric_uses_readonly_tool",
            response=metric,
            checks={
                "route": metric["route"] == "business_metric",
                "exact_value": metric_result.get("value") == 400.5,
                "unit": metric_result.get("unit") == "CNY",
                "readonly_source": (
                    metric_result.get("data_source")
                    == "local_readonly_sqlite"
                ),
                "trajectory": _trajectory(metric)
                == ["route_request", "query_business_metric"],
            },
            detail="指标问题只能落到 Part 4 的白名单只读 Tool。",
        )
    )

    smalltalk = service.ask("你好")
    results.append(
        _result(
            name="smalltalk_skips_tools",
            response=smalltalk,
            checks={
                "route": smalltalk["route"] == "smalltalk",
                "no_citations": smalltalk["citations"] == [],
                "no_metric": smalltalk["metric_result"] is None,
                "trajectory": _trajectory(smalltalk)
                == ["route_request", "answer_smalltalk"],
            },
            detail="问候不应触发检索或数据库。",
        )
    )

    waiting_approval = service.ask("导出华东已完成订单营收")
    approved = service.resume(
        waiting_approval["thread_id"],
        decision="approve",
        note="evaluation approve",
    )
    approved_metric = approved.get("metric_result") or {}
    results.append(
        _result(
            name="export_requires_approval",
            response=approved,
            checks={
                "paused_first": waiting_approval["status"] == "interrupted",
                "waiting_route": (
                    waiting_approval["route"] == "awaiting_approval"
                ),
                "no_query_before_approval": (
                    waiting_approval["metric_result"] is None
                ),
                "approved_route": approved["route"] == "export_completed",
                "exact_value": approved_metric.get("value") == 120.5,
                "trajectory": _trajectory(approved)
                == [
                    "route_request",
                    "prepare_export",
                    "request_export_approval",
                    "execute_export",
                ],
            },
            detail="批准前不查指标，批准后才执行只读 Tool。",
        )
    )

    waiting_rejection = service.ask("导出华南已完成订单营收")
    rejected = service.resume(
        waiting_rejection["thread_id"],
        decision="reject",
        note="evaluation reject",
    )
    results.append(
        _result(
            name="rejected_export_has_no_query_result",
            response=rejected,
            checks={
                "paused_first": waiting_rejection["status"] == "interrupted",
                "rejected_route": rejected["route"] == "export_rejected",
                "approved_false": rejected["approved"] is False,
                "no_metric_result": rejected["metric_result"] is None,
                "trajectory": _trajectory(rejected)
                == [
                    "route_request",
                    "prepare_export",
                    "request_export_approval",
                    "reject_export",
                ],
            },
            detail="拒绝后不得执行指标查询或伪装成已导出。",
        )
    )

    serialized = [result.to_dict() for result in results]
    passed = sum(1 for result in results if result.passed)
    check_values = [
        value
        for result in results
        for value in result.checks.values()
    ]
    return {
        "summary": {
            "case_count": len(results),
            "passed_cases": passed,
            "case_pass_rate": round(passed / max(1, len(results)), 4),
            "contract_check_count": len(check_values),
            "contract_check_pass_rate": round(
                sum(check_values) / max(1, len(check_values)),
                4,
            ),
        },
        "cases": serialized,
    }


def build_evaluation_service(root: Path) -> ControlledAssistantService:
    source_dir = root / "source"
    source_dir.mkdir(parents=True)
    (source_dir / "runtime.md").write_text(
        "# Runtime\n"
        "Project ORBITAL_BEACON uses local MiniLM embeddings and Chroma.\n",
        encoding="utf-8",
    )
    (source_dir / "citations.md").write_text(
        "# Citations\n"
        "Grounded answers preserve stable chunk_id values for validation.\n",
        encoding="utf-8",
    )
    settings = build_tutorial_settings(
        mode="offline",
        embedding_mode="hash",
        source_dir=source_dir,
        runtime_dir=root / "rag-runtime",
    )
    retriever = LocalKnowledgeRetriever(settings)
    retriever.ensure_index(reset=True)
    database_path = root / "business.db"
    initialize_demo_database(database_path)
    return build_tutorial_service(retriever, database_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="评测目录 5 的受控 Graph 合同")
    parser.add_argument(
        "--output",
        type=Path,
        help="可选：把 JSON 报告写到指定路径。",
    )
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(
        prefix="langgraph-evaluation-"
    ) as temporary:
        service = build_evaluation_service(Path(temporary))
        report = evaluate_service(service)

    document = {
        "official_source": OFFICIAL_SOURCE,
        **report,
    }
    rendered = json.dumps(document, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["summary"]["passed_cases"] == 6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
