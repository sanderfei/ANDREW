"""RAG 黄金集评测与文档更新回归；默认本地 MiniLM 检索、在线模型回答。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path
from uuid import uuid4


PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from config import Settings
from kb_service import KnowledgeBaseService


def _load_cases(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("golden_cases.json 必须是 JSON 数组。")
    return payload


def _evaluate_cases(
    service: KnowledgeBaseService,
    cases: list[dict[str, object]],
    *,
    mode: str,
) -> tuple[list[dict[str, object]], list[str]]:
    results: list[dict[str, object]] = []
    failures: list[str] = []
    for case in cases:
        case_id = str(case["id"])
        response = service.ask(
            question=str(case["question"]),
            top_k=4,
            request_id=uuid4().hex,
        )
        citations = [citation.source for citation in response.citations]
        expected_answerable = bool(case["expected_answerable"])
        passed = response.answerable == expected_answerable
        reasons: list[str] = []
        warnings: list[str] = []
        if not passed:
            reasons.append(
                f"answerable={response.answerable}，期望 {expected_answerable}"
            )
        if expected_answerable and not response.answer.strip():
            passed = False
            reasons.append("可回答问题返回了空 answer")

        expected_sources = set(case.get("expected_sources", []))
        if expected_sources and not expected_sources.issubset(citations):
            passed = False
            reasons.append(f"citations={citations} 未包含 {sorted(expected_sources)}")
        if not expected_answerable and response.citations:
            passed = False
            reasons.append("拒答问题不应携带 citations")

        forbidden_sources = set(case.get("forbidden_sources", []))
        overlap = forbidden_sources.intersection(citations)
        if overlap:
            passed = False
            reasons.append(f"出现禁止引用来源 {sorted(overlap)}")

        citation_text = "\n".join(citation.quote for citation in response.citations)
        expected_text = response.answer if mode == "offline" else citation_text
        expected_text_name = "answer" if mode == "offline" else "citation 证据"
        for term in case.get("expected_terms", []):
            normalized_term = str(term)
            if normalized_term not in expected_text:
                passed = False
                reasons.append(f"{expected_text_name}未包含关键术语 {term!r}")
            elif mode == "live" and normalized_term not in response.answer:
                warnings.append(f"live answer 未逐字包含关键术语 {term!r}")

        result = {
            "id": case_id,
            "category": case.get("category", "unknown"),
            "passed": passed,
            "answerable": response.answerable,
            "answer": response.answer,
            "citations": citations,
            "reasons": reasons,
            "warnings": warnings,
        }
        results.append(result)
        if not passed:
            failures.append(f"{case_id}: {'；'.join(reasons)}")
    return results, failures


def _run_update_regression(service: KnowledgeBaseService, source_dir: Path) -> dict[str, object]:
    """验证更新源文件会删除旧 chunk IDs 并写入新内容。"""

    target = source_dir / "service_operations.md"
    original = target.read_text(encoding="utf-8")
    updated = original + "\n\n更新回归标记：release_channel=canary。\n"
    target.write_text(updated, encoding="utf-8")
    update_stats = service.reindex()
    update_answer = service.ask(
        question="release_channel 当前是什么？",
        # Hash 基线可能因槽位碰撞把新增片段排到第 4；这里验证的是“更新后的
        # chunk 已可检索”，用 5 覆盖当前全部来源，避免把召回质量混入增量测试。
        top_k=5,
        request_id=uuid4().hex,
    )

    target.unlink()
    delete_stats = service.reindex()
    manifest_sources = service.indexer.read_manifest()["sources"]

    failures: list[str] = []
    if update_stats.updated_files != 1 or update_stats.indexed_chunks < 1:
        failures.append("文档更新没有触发预期的增量写入")
    update_evidence = "\n".join(
        citation.quote for citation in update_answer.citations
    )
    if not update_answer.answerable or "release_channel=canary" not in update_evidence:
        failures.append("更新后的资料没有被检索到")
    if delete_stats.removed_files != 1 or "service_operations.md" in manifest_sources:
        failures.append("删除源文件后 manifest 没有同步清理")
    return {
        "passed": not failures,
        "update": update_stats.to_dict(),
        "delete": delete_stats.to_dict(),
        "failures": failures,
    }


def run(
    output: Path,
    *,
    embedding_mode: str = "local",
    mode: str = "live",
) -> int:
    cases = _load_cases(PROJECT_DIR / "data" / "eval" / "golden_cases.json")
    with tempfile.TemporaryDirectory(prefix="rag-kb-eval-") as temporary:
        temporary_root = Path(temporary)
        source_dir = temporary_root / "source"
        shutil.copytree(PROJECT_DIR / "data" / "source", source_dir)
        settings = Settings.from_env(
            mode=mode,
            embedding_mode=embedding_mode,
            source_dir=source_dir,
            runtime_dir=temporary_root / "runtime",
        )
        service = KnowledgeBaseService(settings)
        initial_index = service.reindex()
        results, failures = _evaluate_cases(service, cases, mode=mode)
        update_regression = _run_update_regression(service, source_dir)
        failures.extend(update_regression["failures"])

    warnings = [
        f"{result['id']}: {warning}"
        for result in results
        for warning in result["warnings"]
    ]
    category_totals = Counter(str(result["category"]) for result in results)
    category_passed = Counter(
        str(result["category"]) for result in results if result["passed"]
    )
    report = {
        "status": "passed" if not failures else "failed",
        "mode": mode,
        "embedding_mode": embedding_mode,
        "total": len(results),
        "passed": sum(bool(result["passed"]) for result in results),
        "failed": len(failures),
        "warning_count": len(warnings),
        "by_category": {
            category: {
                "total": category_totals[category],
                "passed": category_passed[category],
            }
            for category in sorted(category_totals)
        },
        "initial_index": initial_index.to_dict(),
        "update_regression": update_regression,
        "results": results,
        "failures": failures,
        "warnings": warnings,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "status",
                    "mode",
                    "embedding_mode",
                    "total",
                    "passed",
                    "failed",
                    "warning_count",
                )
            },
            ensure_ascii=False,
        )
    )
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"WARN: {warning}", file=sys.stderr)
    return 0


# 在仓库根目录运行完整评估（mode=live，embedding_mode=local）：
# .venv/bin/python 4_rag_knowledge_base_service/evaluate.py --mode live --embedding local
#
# 增量同步来源文件到索引：
# .venv/bin/python 4_rag_knowledge_base_service/cli.py --mode live --embedding local reindex
#
# 删除旧索引并完整重建（切块或 Embedding 配置改变后使用）：
# .venv/bin/python 4_rag_knowledge_base_service/cli.py --mode live --embedding local reindex --reset
#
# 查看当前索引状态：
# .venv/bin/python 4_rag_knowledge_base_service/cli.py --mode live --embedding local health
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行 RAG 黄金集与更新回归")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_DIR / "reports" / "evaluation.json",
        help="评测报告 JSON 输出位置。",
    )
    parser.add_argument(
        "--embedding",
        choices=("local", "hash"),
        default="local",
        help="默认使用本机 MiniLM；CI 可选择 hash 做确定性检索回归。",
    )
    parser.add_argument(
        "--mode",
        choices=("offline", "live"),
        default="live",
        help="默认 live 调用聊天模型生成答案；CI 使用 offline 返回确定性摘录。",
    )
    args = parser.parse_args(argv)
    return run(args.output, embedding_mode=args.embedding, mode=args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
