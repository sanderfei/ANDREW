"""在同一 Qdrant 片段快照上比较本地检索策略，不调用聊天模型或写入数据库。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import random
import re
import shlex
from statistics import mean
import sys
from time import perf_counter
import unicodedata
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from services.embedding import get_embedding
from services.ingestion import redact
from services.vector_service import VectorService


VARIANTS = (
    "dense_top5", "dense20_dedup5", "bm25_top5", "bm25_dedup5",
    "hybrid_rrf_top5", "hybrid_rrf_dedup5",
)
METRICS = ("hit_at1", "hit_at3", "hit_at5", "mrr_at5", "recall_at5")


def milliseconds(start: float) -> float:
    return (perf_counter() - start) * 1000


def timing(values: list[float]) -> dict:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None}
    # nearest-rank，不把小样本的 P95 当稳定线上 SLA。
    return {"count": len(ordered), "mean_ms": mean(ordered),
            "p50_ms": ordered[max(0, math.ceil(len(ordered) * .50) - 1)],
            "p95_ms": ordered[max(0, math.ceil(len(ordered) * .95) - 1)]}


def terms(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    output = []
    # 先保留 ImagePullBackOff、域名、路径、版本等标识符，再补其拆分词。
    for identifier in re.findall(r"[a-z0-9_]+(?:[./:\-][a-z0-9_]+)*", normalized):
        output.append(identifier)
        pieces = re.findall(r"[a-z0-9_]+", identifier)
        if len(pieces) > 1:
            output.extend(pieces)
    for run in re.findall(r"[\u3400-\u9fff]+", normalized):
        output.extend(run)
        output.extend(run[index:index + 2] for index in range(len(run) - 1))
    return output


def selected_filters(case: dict) -> dict:
    aliases = {"kubernetes_version": "kubernetes_versions", "operating_system": "operating_systems",
               "install_mode": "install_modes"}
    output = {aliases.get(key, key): value for key, value in case.get("filters", {}).items() if value}
    if set(output) - {"kubernetes_versions", "operating_systems", "install_modes"}:
        raise ValueError("样本包含不支持的环境过滤字段。")
    return output


def matches_filters(item: dict, filters: dict) -> bool:
    return all(value in item["metadata"].get(key, []) or "any" in item["metadata"].get(key, [])
               for key, value in filters.items())


class LocalBM25:
    """仅索引同一批已入库正文；不额外加入标题或未入库的完整文档。"""

    def __init__(self, chunks: list[dict], k1: float = 1.2, b: float = .75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.counts = [Counter(terms(item["content"])) for item in chunks]
        self.lengths = [sum(count.values()) for count in self.counts]
        self.average = mean(self.lengths) if self.lengths else 1
        self.postings = defaultdict(list)
        for index, counts in enumerate(self.counts):
            for word, frequency in counts.items():
                self.postings[word].append((index, frequency))
        self.idf = {word: math.log(1 + (len(chunks) - len(postings) + .5) / (len(postings) + .5))
                    for word, postings in self.postings.items()}

    def search(self, query: str, limit: int, filters: dict) -> list[dict]:
        scores = defaultdict(float)
        for word in set(terms(query)):
            for index, frequency in self.postings.get(word, []):
                denominator = frequency + self.k1 * (1 - self.b + self.b * self.lengths[index] / self.average)
                scores[index] += self.idf[word] * frequency * (self.k1 + 1) / denominator
        ranked = sorted(((index, score) for index, score in scores.items() if score > 0
                         and matches_filters(self.chunks[index], filters)),
                        key=lambda pair: (-pair[1], self.chunks[pair[0]]["chunk_id"]))
        return [{**self.chunks[index], "score": score} for index, score in ranked[:limit]]


def deduplicate(items: list[dict], limit: int = 5) -> list[dict]:
    output, seen = [], set()
    for item in items:
        source = item["metadata"]["source"]
        if source not in seen:
            output.append(item)
            seen.add(source)
        if len(output) == limit:
            break
    return output


def fuse(dense: list[dict], lexical: list[dict]) -> list[dict]:
    combined, scores = {}, defaultdict(float)
    for ranking in (dense, lexical):
        for rank, item in enumerate(ranking, 1):
            key = item["chunk_id"]
            combined.setdefault(key, item)
            scores[key] += 1 / (60 + rank)
    keys = sorted(scores, key=lambda key: (-scores[key], key))
    return [{**combined[key], "score": scores[key]} for key in keys]


def evaluate(items: list[dict], expected: list[str]) -> dict:
    relevant = set(expected)
    sources = [item["metadata"]["source"] for item in items[:5]]
    if any(not source for source in sources):
        raise ValueError("检索结果缺少稳定来源字段。")
    return {**{f"hit_at{k}": float(bool(set(sources[:k]) & relevant)) for k in (1, 3, 5)},
            "mrr_at5": next((1 / rank for rank, source in enumerate(sources, 1) if source in relevant), 0),
            "recall_at5": len(set(sources) & relevant) / len(relevant) if relevant else None,
            "context_chars": sum(len(item["content"]) for item in items[:5])}


def public_results(items: list[dict]) -> list[dict]:
    # 结果文件不保存文档正文或完整日志。
    return [{"chunk_id": item["chunk_id"], "source": item["metadata"]["source"],
             "score": item["score"], "context_chars": len(item["content"])} for item in items[:5]]


def snapshot(service: VectorService) -> list[dict]:
    output, offset = [], None
    while True:
        points, offset = service.store.client.scroll(service.store.namespace, limit=256,
            offset=offset, with_payload=True, with_vectors=False)
        for point in points:
            payload = point.payload or {}
            item = {"chunk_id": str(point.id), "content": payload.get("content", ""),
                    "metadata": payload.get("metadata", {})}
            if not item["metadata"].get("source") or not isinstance(item["content"], str):
                raise ValueError("数据库片段缺少来源或正文。")
            output.append(item)
        if offset is None:
            break
    if not output:
        raise ValueError("Qdrant 集合为空；请先通过录入接口导入文档。")
    return sorted(output, key=lambda item: item["chunk_id"])


def api_search(opener, base_url: str, case: dict) -> tuple[list[dict], float]:
    aliases = {"kubernetes_versions": "kubernetes_version", "operating_systems": "operating_system",
               "install_modes": "install_mode"}
    body = {"query": case["query"], "top_k": 5,
            **{aliases[key]: value for key, value in selected_filters(case).items()}}
    request = Request(base_url + "/api/vector/search", data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    started = perf_counter()
    with opener.open(request, timeout=120) as response:
        result = json.load(response)
    elapsed = milliseconds(started)
    if result.get("backend") != "qdrant" or not isinstance(result.get("items"), list):
        raise ValueError("检索接口未返回预期 Qdrant 结果。")
    items = result["items"]
    if not items or any(not item.get("metadata", {}).get("source") for item in items):
        raise ValueError("检索接口未返回带来源的片段。")
    return items, elapsed


def local_search(embedder, service, lexical, case, candidate_k):
    filters = selected_filters(case)
    started = perf_counter()
    vector = embedder.query(case["query"])
    embedding_ms = milliseconds(started)
    started = perf_counter()
    dense = service.store.search(vector, candidate_k, filters)
    qdrant_ms = milliseconds(started)
    started = perf_counter()
    sparse = lexical.search(case["query"], candidate_k, filters)
    lexical_ms = milliseconds(started)
    started = perf_counter()
    hybrid = fuse(dense, sparse)
    fusion_ms = milliseconds(started)
    candidates = {"dense_top5": dense[:5], "dense20_dedup5": deduplicate(dense),
                  "bm25_top5": sparse[:5], "bm25_dedup5": deduplicate(sparse),
                  "hybrid_rrf_top5": hybrid[:5], "hybrid_rrf_dedup5": deduplicate(hybrid)}
    latency = {name: (embedding_ms + qdrant_ms if name.startswith("dense") else lexical_ms
                     if name.startswith("bm25") else embedding_ms + qdrant_ms + lexical_ms + fusion_ms)
               for name in VARIANTS}
    return candidates, latency, {"embedding_ms": embedding_ms, "qdrant_ms": qdrant_ms,
                                 "lexical_ms": lexical_ms, "fusion_ms": fusion_ms}


def summarize(rows: list[dict]) -> dict:
    return {**{metric: mean(row["metrics"][metric] for row in rows) for metric in METRICS},
            "context_chars_mean": mean(row["metrics"]["context_chars"] for row in rows),
            "latency": timing([row["latency_ms"] for row in rows])}


def breakdown(rows: list[dict], field: str) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[row[field]].append(row)
    return {name: {"unique_queries": len({row["id"] for row in group}), **summarize(group)}
            for name, group in sorted(groups.items())}


def run(args) -> dict:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    data = json.loads(args.questions.read_text())
    cases, negatives = data["cases"], data.get("unanswerable", [])
    if not cases or any(not case.get("expected_sources") for case in cases):
        raise ValueError("正例样本必须包含问题和相关来源标签。")
    service = VectorService()
    try:
        if service.settings.backend != "qdrant":
            raise ValueError("此实验只支持当前配置的 Qdrant，不自动切换配置。")
        if not (service.settings.model_path / "model_optimized.onnx").is_file():
            raise ValueError("本地 Embedding 模型不存在；实验不会下载模型。")
        for name in ("tokenizer.json", "tokenizer_config.json", "config.json", "special_tokens_map.json"):
            if not (service.settings.model_path / name).is_file():
                raise ValueError("本地 Embedding 模型配置不完整；实验不会下载模型。")
        started = perf_counter()
        chunks = snapshot(service)
        scroll_ms = milliseconds(started)
        sources = {item["metadata"]["source"] for item in chunks}
        missing = {source for case in cases for source in case["expected_sources"]} - sources
        if missing:
            raise ValueError("样本标签尚未全部入库：" + ", ".join(sorted(missing)))
        for case in cases:
            eligible = {item["metadata"]["source"] for item in chunks
                        if matches_filters(item, selected_filters(case))}
            if not set(case["expected_sources"]) <= eligible:
                raise ValueError(f"样本 {case['id']} 的参考来源不满足自身环境过滤标签。")
        fingerprint = sha256(json.dumps([(item["chunk_id"], sha256(item["content"].encode()).hexdigest(),
                                         item["metadata"]) for item in chunks],
                                        ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        started = perf_counter()
        lexical = LocalBM25(chunks)
        lexical_build_ms = milliseconds(started)
        started = perf_counter()
        embedder = get_embedding(service.settings)
        embedding_init_ms = milliseconds(started)
        opener = build_opener(ProxyHandler({}))
        api_warmup, process_warmup = [], []
        for case in cases[:3]:
            _, elapsed = api_search(opener, args.base_url, case)
            api_warmup.append({"id": case["id"], "latency_ms": elapsed})
            _, _, stages = local_search(embedder, service, lexical, case, args.candidate_k)
            process_warmup.append({"id": case["id"], **stages})
        api_rows, per_query = [], {}
        for index, case in enumerate(cases):
            results, elapsed = api_search(opener, args.base_url, case)
            attributes = {"id": case["id"], "category": case.get("category", "unknown"),
                          "query_style": case.get("query_style", "unknown"),
                          "cohort": case.get("cohort", "unspecified"),
                          "subset": "filtered" if selected_filters(case) else "unfiltered"}
            row = {**attributes, "metrics": evaluate(results, case["expected_sources"]), "latency_ms": elapsed,
                   "results": public_results(results)}
            api_rows.append(row)
            per_query[case["id"]] = {"id": case["id"], "query": redact(case["query"]),
                **attributes, "filters": selected_filters(case), "expected_sources": case["expected_sources"],
                "api_baseline": row, "variants": {name: [] for name in VARIANTS}}
            if (index + 1) % 5 == 0:
                print(json.dumps({"phase": "api_baseline", "completed": index + 1, "total": len(cases)}), flush=True)
        variant_rows = {name: [] for name in VARIANTS}
        stage_samples = defaultdict(list)
        rng = random.Random(20261028)
        for repeat in range(args.repeats):
            order = list(cases)
            rng.shuffle(order)
            for case in order:
                candidates, latencies, stages = local_search(embedder, service, lexical, case, args.candidate_k)
                for name, value in stages.items():
                    stage_samples[name].append(value)
                for name in VARIANTS:
                    row = {"id": case["id"], "category": case.get("category", "unknown"),
                           "query_style": case.get("query_style", "unknown"),
                           "cohort": case.get("cohort", "unspecified"),
                           "subset": "filtered" if selected_filters(case) else "unfiltered",
                           "repeat": repeat + 1, "metrics": evaluate(candidates[name], case["expected_sources"]),
                           "latency_ms": latencies[name], "results": public_results(candidates[name])}
                    variant_rows[name].append(row)
                    per_query[case["id"]]["variants"][name].append(row)
            print(json.dumps({"phase": "local_variants", "repeat": repeat + 1, "total": args.repeats}), flush=True)
        negative_rows = []
        for case in negatives:
            api_result, api_elapsed = api_search(opener, args.base_url, case)
            candidates, latencies, _ = local_search(embedder, service, lexical, case, args.candidate_k)
            negative_rows.append({"id": case["id"], "query": redact(case["query"]),
                "included_in_quality_denominator": False,
                "api_baseline": {"latency_ms": api_elapsed, "results": public_results(api_result)},
                "variants": {name: {"latency_ms": latencies[name], "results": public_results(candidates[name])}
                             for name in VARIANTS}})
        # 固定向量，比较搜索前两种检查方式；Embedding、HTTP与算法质量都不混入该消融。
        vector = embedder.query(cases[0]["query"])
        full_times, light_times, expected_ids = [], [], None
        for repeat in range(5):
            modes = ("full", "light") if repeat % 2 == 0 else ("light", "full")
            for mode in modes:
                started = perf_counter()
                if mode == "full":
                    assert service.store.status()["initialized"]
                else:
                    assert service.store.client.collection_exists(service.store.namespace)
                result = service.store.search(vector, 5, {})
                elapsed = milliseconds(started)
                ids = [item["chunk_id"] for item in result]
                if expected_ids is None:
                    expected_ids = ids
                assert ids == expected_ids, "检查方式消融的查询结果发生变化。"
                (full_times if mode == "full" else light_times).append(elapsed)
        summary = {"schema_version": 1, "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "chat_model_calls": 0, "database_writes": 0,
            "corpus": {"namespace": service.store.namespace, "chunks": len(chunks), "documents": len(sources),
                       "snapshot_sha256": fingerprint, "embedding_model": service.settings.model},
            "dataset": {"cases": len(cases), "negative_cases": len(negatives),
                        "sha256": sha256(args.questions.read_bytes()).hexdigest(),
                        "unique_query_texts": len({case["query"] for case in cases}),
                        "labeled_sources": len({source for case in cases for source in case["expected_sources"]}),
                        "filtered_cases": sum(bool(selected_filters(case)) for case in cases),
                        "category_counts": dict(Counter(case.get("category", "unknown") for case in cases)),
                        "query_style_counts": dict(Counter(case.get("query_style", "unknown") for case in cases)),
                        "single_label_all_cases": all(len(set(case["expected_sources"])) == 1 for case in cases)},
            "parameters": {"candidate_k": args.candidate_k, "final_k": 5, "rrf_k": 60,
                           "bm25_k1": 1.2, "bm25_b": .75, "repeats": args.repeats,
                           "bm25_index_text": "stored chunk content only", "shuffle_seed": 20261028},
            "setup": {"snapshot_scroll_ms": scroll_ms, "lexical_index_build_ms": lexical_build_ms,
                      "process_embedding_initialization_ms": embedding_init_ms,
                      "api_warmup": api_warmup, "process_warmup": process_warmup},
            "api_baseline": summarize(api_rows),
            "variants": {name: summarize(rows) for name, rows in variant_rows.items()},
            "api_breakdowns": {field: breakdown(api_rows, field) for field in ("category", "query_style", "subset", "cohort")},
            "variant_breakdowns": {name: {field: breakdown(rows, field)
                for field in ("category", "query_style", "subset", "cohort")}
                for name, rows in variant_rows.items()},
            "request_counts": {"api_warmup": len(api_warmup), "api_positive": len(cases),
                "api_negative": len(negatives),
                "local_candidate_queries": len(process_warmup) + len(cases) * args.repeats + len(negatives),
                "status_ablation_queries": 10},
            "process_stages": {name: timing(values) for name, values in stage_samples.items()},
            "status_check_ablation": {"full_status_then_query": timing(full_times),
                "collection_exists_then_query": timing(light_times), "identical_result_ids": True},
            "limitations": data.get("limitations", []) + [
                "同一片段快照的受控本地模拟；尚未接入业务检索接口。",
                "六方案共享同一次 candidate_k 的向量/词法候选；dense_top5为该候选池截断，不是单独limit=5计时。",
                "进程内方案延迟为各阶段串行时间之和，未含HTTP和客户端构造；不能直接声称比API加速。",
                "文档级匹配但结果槽位仍按片段计数，重复来源消耗Top-K槽位；去重方案每来源保留最高位片段。",
                "只保存来源、分数和字符数；context_chars不是模型Token。",
                "冷启动、暖查询、索引构建和全量统计开销分别报告；小样本P95不代表线上SLA。",
                "负例只观察返回结果，尚未标定拒答阈值；近邻非空不代表可回答。"]}
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        (args.output_dir / "per_query.json").write_text(json.dumps({"cases": list(per_query.values()),
            "unanswerable": negative_rows}, ensure_ascii=False, indent=2) + "\n")
        write_report(args, summary)
        return summary
    finally:
        service.close()


def write_report(args, summary):
    lines = ["# 本地文档检索对比", "", f"生成时间：{summary['created_at']}（Asia/Shanghai）。", "",
        "仅调用本地 Embedding 与检索接口，不调用聊天模型、不写数据库。", "",
        f"语料：{summary['corpus']['documents']} 个文档、{summary['corpus']['chunks']} 个片段；"
        f"正例 {summary['dataset']['cases']}，负例 {summary['dataset']['negative_cases']}，重复 {args.repeats} 次。", "",
        "## 同层质量与延迟", "", "| 方案 | Hit@1 | Hit@3 | Hit@5 | MRR@5 | Recall@5 | 平均上下文字符 | P50 ms | P95 ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, values in summary["variants"].items():
        lines.append(f"| {name} | " + " | ".join(f"{values[metric]:.4f}" for metric in METRICS)
                     + f" | {values['context_chars_mean']:.0f} | {values['latency']['p50_ms']:.2f} | {values['latency']['p95_ms']:.2f} |")
    api = summary["api_baseline"]
    lines += ["", "## 原API基线（单独计量）", "", f"实际 HTTP top_k=5：Hit@5={api['hit_at5']:.4f}，"
        f"MRR@5={api['mrr_at5']:.4f}，P50={api['latency']['p50_ms']:.2f} ms，P95={api['latency']['p95_ms']:.2f} ms。",
        "", "前三题作为 API 与进程内暖身另记在 summary.json；不计入上述延迟样本。", "",
        "## 样本覆盖", "",
        f"去重问题文本 {summary['dataset']['unique_query_texts']} 条，参考文档 {summary['dataset']['labeled_sources']} 份，"
        f"环境过滤题 {summary['dataset']['filtered_cases']} 条。三次重复用于计时与稳定性，不算成三倍独立样本。", "",
        "| 问法 | 问题数 | Dense Hit@5 | BM25 Hit@5 | 混合去重 Hit@5 |",
        "| --- | ---: | ---: | ---: | ---: |"]
    for style, values in summary["variant_breakdowns"]["dense_top5"]["query_style"].items():
        lines.append(f"| {style} | {values['unique_queries']} | {values['hit_at5']:.4f} | "
            f"{summary['variant_breakdowns']['bm25_top5']['query_style'][style]['hit_at5']:.4f} | "
            f"{summary['variant_breakdowns']['hybrid_rrf_dedup5']['query_style'][style]['hit_at5']:.4f} |")
    lines += ["", "## 全量统计开销消融", ""]
    for name in ("full_status_then_query", "collection_exists_then_query"):
        value = summary["status_check_ablation"][name]
        lines.append(f"- {name}: P50 {value['p50_ms']:.2f} ms，P95 {value['p95_ms']:.2f} ms。")
    lines += ["- 两种检查方式的查询结果ID完全一致；这项只衡量延迟，不代表质量或聊天Token改善。", "",
              "## 限制与复现", ""]
    if summary["dataset"]["single_label_all_cases"]:
        lines.append("每题只有一个已标注来源，因而 Recall@5 与 Hit@5 相同；标签未穷尽所有相关文档。")
    lines.extend("- " + item for item in summary["limitations"])
    command = [".venv/bin/python", "7_private_deployment_assistant/evaluations/retrieval_benchmark.py",
               "--questions", str(args.questions), "--output-dir", str(args.output_dir), "--base-url", args.base_url,
               "--repeats", str(args.repeats), "--candidate-k", str(args.candidate_k)]
    lines += ["", "```bash", shlex.join(command), "```", "", "语料指纹：`" + summary["corpus"]["snapshot_sha256"] + "`。"]
    (args.output_dir / "report.md").write_text("\n".join(lines) + "\n")


# 启动：.venv/bin/python 7_private_deployment_assistant/evaluations/retrieval_benchmark.py --output-dir 7_private_deployment_assistant/reports/retrieval
# 参数：--questions JSON样本文件（默认evaluations/data/retrieval_cases.json）；--output-dir 结果目录（必填）；--base-url 本机API地址（默认http://127.0.0.1:8070）；
# --repeats 正例重复次数（默认3）；--candidate-k 每路候选数（默认20，至少5）；不下载模型、不调用聊天LLM、不写数据库。
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=PROJECT_DIR / "evaluations/data/retrieval_cases.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8070")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--candidate-k", type=int, default=20)
    args = parser.parse_args(argv)
    args.base_url = args.base_url.rstrip("/")
    parsed = urlsplit(args.base_url)
    if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        parser.error("base-url只接受不含凭据的本机HTTP(S)地址。")
    if args.repeats < 1 or args.candidate_k < 5:
        parser.error("repeats至少1，candidate-k至少5。")
    try:
        summary = run(args)
    except Exception as exc:
        print(json.dumps({"error": redact(str(exc)), "type": type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"output_dir": str(args.output_dir), "cases": summary["dataset"]["cases"],
                      "variants": summary["variants"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
