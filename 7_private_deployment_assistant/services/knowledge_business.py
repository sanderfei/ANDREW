"""功能验证、脱敏案例归档和可恢复的向量入库任务。

SQLite 保存案例版本及 outbox；本地 Markdown 是可阅读的知识来源。
worker 持有案例文件锁后才录入，避免旧版本任务覆盖新版本。
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Callable
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from contracts import DocumentMetadata
from services.ingestion import redact


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value, maximum: int = 8000) -> str:
    """只持久化脱敏后的摘要；不保存完整会话或工具输出。"""
    result = redact(str(value or ""))
    result = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [REDACTED]", result)
    result = re.sub(
        r'''(?ix)(["']?(?:password|passwd|token|secret|api[_-]?key|authorization|密码|口令)["']?\s*[:=：]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;}]+)''',
        r"\1[REDACTED]",
        result,
    )

    def clean_url(match):
        try:
            url = urlsplit(match.group(0))
            host = url.netloc.rsplit("@", 1)[-1]
            return urlunsplit((url.scheme, host, url.path, "", ""))
        except ValueError:
            return "[REDACTED_URL]"

    result = re.sub(r"https?://[^\s<>\"']+", clean_url, result)
    return result.strip()[:maximum]


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@contextmanager
def _file_lock(path: Path, blocking: bool = True):
    """进程退出后由操作系统释放锁，running 任务便可安全恢复。"""
    import fcntl

    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    acquired = False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            acquired = True
        except BlockingIOError:
            pass
        yield acquired
    finally:
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _atomic_write(path: Path, content: str) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class KnowledgeBusiness:
    def __init__(self, db_path: Path, source_dir: Path, retriever_factory: Callable | None = None):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.source_dir = Path(source_dir).expanduser().resolve()
        candidate = self.source_dir / "assistant_cases"
        if candidate.is_symlink():
            raise ValueError("assistant_cases 不得使用符号链接。")
        candidate.mkdir(parents=True, exist_ok=True)
        self.case_dir = candidate.resolve()
        if not self.case_dir.is_relative_to(self.source_dir):
            raise ValueError("案例目录必须位于配置的 source 目录内。")
        self.retriever_factory = retriever_factory
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_cases (
                    case_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE,
                    version INTEGER NOT NULL, digest TEXT NOT NULL,
                    record_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_threads (
                    thread_id TEXT PRIMARY KEY, case_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_case_threads (
                    thread_id TEXT NOT NULL, case_id TEXT NOT NULL,
                    PRIMARY KEY(thread_id, case_id)
                );
                INSERT OR IGNORE INTO knowledge_case_threads SELECT thread_id, case_id FROM knowledge_threads;
                CREATE TABLE IF NOT EXISTS knowledge_index_jobs (
                    job_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, version INTEGER NOT NULL,
                    thread_id TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(case_id, version)
                );
                CREATE INDEX IF NOT EXISTS knowledge_job_status_idx
                    ON knowledge_index_jobs(status, created_at);
                """
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            with connection:
                yield connection
        finally:
            connection.close()

    def verify(self, thread_id: str, proposal: dict, verification: dict) -> dict:
        """命令成功不等于功能恢复；必须显式确认并提供功能复测证据。"""
        if not str(thread_id).strip() or not isinstance(proposal, dict) or not isinstance(verification, dict):
            raise ValueError("验证需要会话、处理方案和验证记录。")
        method = verification.get("method")
        evidence = _text(verification.get("evidence"))
        raw_checks = verification.get("checks", [])
        checks = []
        if isinstance(raw_checks, list):
            for check in raw_checks[:30]:
                if isinstance(check, dict):
                    checks.append({
                        "name": _text(check.get("name") or check.get("tool") or check.get("command"), 500),
                        "exit_code": check.get("exit_code"),
                        "evidence": _text(check.get("evidence") or check.get("summary"), 1500),
                    })
        reason = ""
        if verification.get("confirmed") is not True:
            reason = "尚未明确确认原故障的功能复测通过。"
        elif method not in {"user_confirmation", "remote_check"}:
            reason = "验证方式必须为用户确认或远程功能复测。"
        elif len(evidence) < 8 or evidence.lower() in {"success", "successful", "all passed"}:
            reason = "请提供原故障功能复测的具体证据，不能仅填写成功或命令退出状态。"
        elif method == "remote_check" and (
            not isinstance(raw_checks, list)
            or not raw_checks
            or len(raw_checks) > 30
            or len(checks) != len(raw_checks)
            or any(type(check.get("exit_code")) is not int or check["exit_code"] != 0 for check in checks)
        ):
            reason = "远程复测至少需要一项检查，且所有检查必须成功；仍需独立确认功能恢复。"
        return {
            "verified": not bool(reason),
            "confirmed": verification.get("confirmed") is True,
            "method": method if method in {"user_confirmation", "remote_check"} else None,
            "evidence": evidence,
            "checks": checks,
            "verified_at": _now() if not reason else None,
            "reason": reason,
        }

    def _normalize(self, thread_id: str, record: dict) -> dict:
        if record.get("verified") is not True:
            raise ValueError("只有已确认功能恢复的案例才允许发布。")
        proof = record.get("verification")
        if not isinstance(proof, dict) or proof.get("verified") is not True:
            raise ValueError("案例缺少有效的功能验证证明。")
        checked = self.verify(thread_id, record, {**proof, "confirmed": proof.get("confirmed", proof.get("verified"))})
        if not checked["verified"] or not proof.get("verified_at"):
            raise ValueError(checked["reason"] or "验证证明缺少验证时间。")
        try:
            timestamp = datetime.fromisoformat(str(proof["verified_at"]).replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("验证时间必须是包含时区的 ISO 时间。") from None
        checked["verified_at"] = timestamp.isoformat()
        cause = _text(record.get("root_cause"), 4000)
        if not cause or re.match(r"^(?:未知|待确认|待验证|尚未|无法确定|不确定|疑似|可能|unknown|pending)", cause, re.I):
            raise ValueError("发布案例必须填写已确认的明确根因。")
        summary = _text(record.get("summary") or record.get("question"), 2400)
        if not summary:
            raise ValueError("案例必须包含问题现象摘要。")
        raw_context = record.get("context") or {}
        if not isinstance(raw_context, dict):
            raise ValueError("案例环境必须为字典。")
        context = {key: _text(raw_context.get(key), 200) for key in (
            "kubernetes_version", "operating_system", "install_mode", "component", "component_version"
        ) if raw_context.get(key)}
        if "kubernetes_version" in context:
            context["kubernetes_version"] = context["kubernetes_version"].removeprefix("v")
        if "operating_system" in context:
            context["operating_system"] = {"ubuntu": "Ubuntu", "centos": "CentOS"}.get(
                context["operating_system"].lower(), context["operating_system"]
            )
        for key, allowed in (
            ("kubernetes_version", {"1.23.10", "1.32.8", "any"}),
            ("operating_system", {"Ubuntu", "CentOS", "any"}),
            ("install_mode", {"online", "offline", "any"}),
        ):
            if key in context and context[key] not in allowed:
                raise ValueError(f"{key} 超出当前知识库的元数据合同，不能自动扩大为 any。")
        raw_steps = record.get("steps") or []
        if isinstance(raw_steps, str):
            raw_steps = [raw_steps]
        if not isinstance(raw_steps, list):
            raise ValueError("解决步骤必须为列表。")
        steps = [_text(step.get("description") or step.get("command") if isinstance(step, dict) else step, 2000) for step in raw_steps[:30]]
        steps = [step for step in steps if step]
        answer = _text(record.get("answer"), 8000)
        if not steps and not answer:
            raise ValueError("案例必须包含实际解决步骤。")
        sources = []
        raw_sources = record.get("sources") or []
        if not isinstance(raw_sources, list):
            raise ValueError("案例来源必须为列表。")
        for source in raw_sources[:20]:
            if isinstance(source, dict):
                sources.append({key: _text(source[key], 500) for key in ("title", "source", "location", "chunk_id", "url") if source.get(key)})
            elif isinstance(source, str):
                sources.append({"source": _text(source, 500)})
        return {
            "title": _text(record.get("title") or summary.splitlines()[0], 150),
            "summary": summary, "root_cause": cause, "context": context,
            "root_cause_evidence": _text(record.get("root_cause_evidence") or record.get("evidence"), 4000),
            "steps": steps, "answer": answer, "sources": sources,
            "verification": checked, "verified": True,
            "remaining_issues": _text(record.get("remaining_issues") or "本次原故障复测通过；适用范围以记录环境为准。", 2000),
            "trace_id": _text(record.get("trace_id"), 128),
        }

    def _case_path(self, case_id: str) -> Path:
        if not re.fullmatch(r"AUTO-[a-f0-9]{16,64}", case_id):
            raise ValueError("非法案例编号。")
        return self.case_dir / f"{case_id}.md"

    def publish(self, thread_id: str, record: dict) -> dict:
        clean = self._normalize(thread_id, record)
        identity = {
            "symptom": re.sub(r"\s+", " ", clean["summary"]).lower(),
            "root_cause": re.sub(r"\s+", " ", clean["root_cause"]).lower(),
            "context": clean["context"],
        }
        fingerprint = sha256(_json(identity).encode()).hexdigest()
        digest = sha256(_json(clean).encode()).hexdigest()
        with _file_lock(self.case_dir / ".publish.lock"):
            with self._connect() as connection:
                existing = connection.execute("SELECT * FROM knowledge_cases WHERE fingerprint=?", (fingerprint,)).fetchone()
                if existing is None:
                    previous = connection.execute(
                        "SELECT c.* FROM knowledge_cases c JOIN knowledge_threads t ON c.case_id=t.case_id WHERE t.thread_id=?", (thread_id,)
                    ).fetchone()
                    if previous is not None:
                        old = json.loads(previous["record_json"])
                        same_cause = re.sub(r"\s+", " ", old["root_cause"]).lower() == identity["root_cause"]
                        if same_cause and old["context"] == clean["context"]:
                            existing = previous
                case_id = existing["case_id"] if existing else f"AUTO-{fingerprint[:24]}"
            with _file_lock(self.case_dir / f".{case_id}.lock"):
                stamp = _now()
                with self._connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    version = (existing["version"] + (existing["digest"] != digest)) if existing else 1
                    connection.execute(
                        "INSERT INTO knowledge_cases VALUES (?, ?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT(case_id) DO UPDATE SET fingerprint=excluded.fingerprint, version=excluded.version, "
                        "digest=excluded.digest, record_json=excluded.record_json, updated_at=excluded.updated_at",
                        (case_id, fingerprint, version, digest, _json(clean), existing["created_at"] if existing else stamp, stamp),
                    )
                    connection.execute("INSERT INTO knowledge_threads VALUES (?, ?) ON CONFLICT(thread_id) DO UPDATE SET case_id=excluded.case_id", (thread_id, case_id))
                    connection.execute("INSERT OR IGNORE INTO knowledge_case_threads VALUES (?, ?)", (thread_id, case_id))
                    connection.execute(
                        "UPDATE knowledge_index_jobs SET status='superseded', updated_at=? WHERE case_id=? AND version<? AND status!='completed'",
                        (stamp, case_id, version),
                    )
                    connection.execute(
                        "INSERT OR IGNORE INTO knowledge_index_jobs VALUES (?, ?, ?, ?, 'pending', 0, NULL, ?, ?)",
                        (str(uuid4()), case_id, version, thread_id, stamp, stamp),
                    )
                    job = connection.execute("SELECT * FROM knowledge_index_jobs WHERE case_id=? AND version=?", (case_id, version)).fetchone()
                # outbox 先提交。即使磁盘写入失败或进程退出，worker 也能由 record_json 重建文件。
                self._write_case(case_id, clean)
            self._refresh_index()
        return {
            "case_id": case_id, "path": str(self._case_path(case_id)),
            "verification": clean["verification"], "index_status": job["status"],
            "job_id": job["job_id"], "version": version,
        }

    def _write_case(self, case_id: str, record: dict) -> None:
        context = record["context"]
        metadata = DocumentMetadata(
            title=record["title"], kind="case", verification_status="verified",
            kubernetes_versions=[context.get("kubernetes_version") if context.get("kubernetes_version") in {"1.23.10", "1.32.8"} else "any"],
            operating_systems=[context.get("operating_system") if context.get("operating_system") in {"Ubuntu", "CentOS"} else "any"],
            install_modes=[context.get("install_mode") if context.get("install_mode") in {"online", "offline"} else "any"],
        ).model_dump(exclude_none=True)
        verification = record["verification"]
        environment = "\n".join(f"- {key}：{value}" for key, value in context.items()) or "- 未提供完整环境；本案例不据此声明跨版本兼容。"
        steps = "\n".join(f"{index}. {step}" for index, step in enumerate(record["steps"], 1)) or record["answer"]
        references = "\n".join(f"- {_json(source)}" for source in record["sources"]) or "- 本次已确认的现场检查和功能复测。"
        text = (
            f"# {case_id} {record['title']}\n\n"
            f"记录时间：{verification['verified_at']}\n\n"
            f"## 适用环境与部署方式\n\n{environment}\n\n"
            f"## 问题现象\n\n{record['summary']}\n\n"
            f"## 已确认根因与证据\n\n{record['root_cause']}\n\n"
            f"{record.get('root_cause_evidence') or '根因按本次已确认诊断记录；可复核来源如下。'}\n\n{references}\n\n"
            f"## 解决步骤\n\n{steps}\n\n"
            f"## 功能验证\n\n验证方式：{verification['method']}\n\n{verification['evidence']}\n\n"
            f"## 遗留事项\n\n{record['remaining_issues']}\n\n"
            f"## 追踪引用\n\nTrace ID：{record['trace_id'] or '未启用追踪'}\n"
        )
        path = self._case_path(case_id)
        _atomic_write(path.with_suffix(".md.metadata.json"), json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
        _atomic_write(path, text)

    def _refresh_index(self) -> None:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM knowledge_cases ORDER BY created_at, case_id").fetchall()
        cases = []
        lines = ["# 运维助手验证案例", "", "仅收录经过功能复测确认的脱敏案例。向量入库任务单独跟踪。", ""]
        for row in rows:
            record = json.loads(row["record_json"])
            cases.append({"case_id": row["case_id"], "title": record["title"], "path": f"{row['case_id']}.md", "version": row["version"], "verification_status": "verified", "updated_at": row["updated_at"]})
            title = record["title"].replace("\n", " ").replace("[", "(").replace("]", ")")
            lines.append(f"- [{row['case_id']} {title}]({row['case_id']}.md)")
        _atomic_write(self.case_dir / "case_index.json", json.dumps({"count": len(cases), "cases": cases}, ensure_ascii=False, indent=2) + "\n")
        _atomic_write(self.case_dir / "README.md", "\n".join(lines) + "\n")

    def run_index_jobs(self, limit: int = 5) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("每轮入库任务数量必须为 1～100。")
        with self._connect() as connection:
            pending = connection.execute(
                "SELECT * FROM knowledge_index_jobs WHERE status IN ('pending', 'failed', 'running') "
                "ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'running' THEN 1 ELSE 2 END, updated_at, created_at LIMIT ?", (limit,)
            ).fetchall()
        output = []
        for candidate in pending:
            case_id = candidate["case_id"]
            with _file_lock(self.case_dir / f".{case_id}.lock", blocking=False) as acquired:
                if not acquired:
                    continue
                with self._connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    job = connection.execute("SELECT * FROM knowledge_index_jobs WHERE job_id=?", (candidate["job_id"],)).fetchone()
                    case = connection.execute("SELECT * FROM knowledge_cases WHERE case_id=?", (case_id,)).fetchone()
                    if job["status"] not in {"pending", "failed", "running"}:
                        continue
                    if case["version"] != job["version"]:
                        connection.execute("UPDATE knowledge_index_jobs SET status='superseded', updated_at=? WHERE job_id=?", (_now(), job["job_id"]))
                        continue
                    # 获得文件锁意味着没有存活的 worker 在处理该案例；可恢复崩溃留下的 running。
                    connection.execute("UPDATE knowledge_index_jobs SET status='running', attempts=attempts+1, updated_at=? WHERE job_id=?", (_now(), job["job_id"]))
                error = None
                ingestor = None
                try:
                    self._write_case(case_id, json.loads(case["record_json"]))
                    if self.retriever_factory is None:
                        from services.vector_service import VectorService

                        ingestor = VectorService()
                    else:
                        ingestor = self.retriever_factory()
                    ingestor.ingest(str(self._case_path(case_id)))
                except Exception as exc:
                    error = _text(f"{type(exc).__name__}: {exc}", 1000)
                finally:
                    if ingestor is not None:
                        try:
                            ingestor.close()
                        except Exception as exc:
                            error = error or _text(f"关闭入库客户端失败：{type(exc).__name__}: {exc}", 1000)
                with self._connect() as connection:
                    connection.execute(
                        "UPDATE knowledge_index_jobs SET status=?, last_error=?, updated_at=? WHERE job_id=?",
                        ("failed" if error else "completed", error, _now(), job["job_id"]),
                    )
                    output.append(dict(connection.execute("SELECT * FROM knowledge_index_jobs WHERE job_id=?", (job["job_id"],)).fetchone()))
        if pending:
            with _file_lock(self.case_dir / ".publish.lock"):
                self._refresh_index()
        return output

    def list_jobs(self, thread_id: str | None = None) -> list[dict]:
        with self._connect() as connection:
            if thread_id is None:
                rows = connection.execute("SELECT * FROM knowledge_index_jobs ORDER BY created_at DESC").fetchall()
            else:
                rows = connection.execute(
                    "SELECT j.* FROM knowledge_index_jobs j JOIN knowledge_case_threads t ON j.case_id=t.case_id WHERE t.thread_id=? ORDER BY j.created_at DESC", (thread_id,)
                ).fetchall()
        return [dict(row) for row in rows]
