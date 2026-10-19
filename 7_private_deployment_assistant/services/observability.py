"""本地执行记录、真实 Token 用量和可选 Langfuse 追踪。

禁用 Langfuse 时仍保留 SQLite 记录；观测上报失败不会中断排障流程。
费用只记录提供方明确返回的值，不根据 Token 数量猜测价格。
"""

from contextlib import ExitStack, closing, contextmanager
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from threading import RLock
from time import perf_counter
from typing import Any
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler

from services.ingestion import redact


_PRIVATE_KEY = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|private[_-]?key|密码|口令)"
)


def _safe(value: Any) -> Any:
    """递归脱敏，不通过任意对象的 repr 暴露连接信息。"""
    if isinstance(value, str):
        text = redact(value)
        # 日志经常含 JSON/YAML 引号，补充处理 password": "..." 这类形式。
        text = re.sub(
            r'''(?i)(["']?(?:password|passwd|secret|token|api[_-]?key|authorization|密码|口令)["']?\s*[:：=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;}]+)''',
            r'\1"[REDACTED]"', text,
        )
        return text if len(text) <= 24000 else text[:24000] + "\n[内容截断]"
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _PRIVATE_KEY.search(str(key)) else _safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return f"<{type(value).__name__}>"


def _json(value: Any) -> str:
    return json.dumps(_safe(value), ensure_ascii=False, allow_nan=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _SpanHandle:
    def __init__(self):
        self.output = None

    def update(self, *, output=None, **kwargs):
        self.output = _safe(output)


class TraceHandle:
    """一次用户请求对应一条 Trace，模型回调作为它的子观测。"""

    def __init__(self, service, trace_id: str, metadata: dict | None = None):
        self._service = service
        self.trace_id = trace_id
        self.callbacks: list = [_UsageCallback(self)]
        self._metadata = _safe(metadata or {})
        self._root = None

    def update(self, output=None, status=None, metadata=None):
        if metadata:
            self._metadata.update(_safe(metadata))
        fields = {"metadata": _json(self._metadata)}
        if output is not None:
            fields["output"] = _json(output)
        if status is not None:
            fields["status"] = str(_safe(status))
        self._service._update_trace(self.trace_id, fields)
        if self._root is not None:
            try:
                options = {"metadata": self._metadata}
                if output is not None:
                    options["output"] = _safe(output)
                if status is not None:
                    options["status_message"] = str(_safe(status))
                    if status == "error":
                        options["level"] = "ERROR"
                self._root.update(**options)
            except Exception as error:
                self._service._report_error(self.trace_id, "trace.update", error)

    @contextmanager
    def span(self, name, input=None):
        span_id = uuid4().hex
        started = perf_counter()
        handle = _SpanHandle()
        stack = ExitStack()
        remote = None
        status = "completed"
        error_text = None
        if self._root is not None:
            try:
                remote = stack.enter_context(
                    self._service._client.start_as_current_observation(
                        name=str(_safe(name)), input=_safe(input), as_type="span"
                    )
                )
            except Exception as error:
                self._service._report_error(self.trace_id, "span.start", error)
        try:
            yield handle
        except BaseException as error:
            status = "error"
            error_text = _safe(str(error))
            raise
        finally:
            if remote is not None:
                try:
                    remote.update(
                        output=handle.output,
                        level="ERROR" if status == "error" else "DEFAULT",
                        status_message=error_text,
                    )
                except Exception as error:
                    self._service._report_error(self.trace_id, "span.update", error)
            try:
                stack.close()
            except Exception as error:
                self._service._report_error(self.trace_id, "span.end", error)
            self._service._execute(
                "INSERT INTO obs_spans "
                "(id, trace_id, name, input, output, status, error, duration_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (span_id, self.trace_id, str(_safe(name)), _json(input),
                 _json(handle.output), status, error_text,
                 (perf_counter() - started) * 1000),
            )

    def record_usage(self, stage, model, input_tokens, output_tokens,
                     total_tokens=None, cost=None, *, run_id=None):
        counts = [input_tokens, output_tokens]
        if total_tokens is not None:
            counts.append(total_tokens)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
               for value in counts):
            raise ValueError("Token 用量必须是非负整数。")
        if cost is not None and (not math.isfinite(float(cost)) or float(cost) < 0):
            raise ValueError("费用必须是非负有限数值。")
        total = total_tokens if total_tokens is not None else input_tokens + output_tokens
        identity = str(run_id or uuid4().hex)
        with self._service._connection() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO obs_usage "
                "(id, trace_id, run_id, stage, model, input_tokens, output_tokens, "
                "total_tokens, cost, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (uuid4().hex, self.trace_id, identity,
                 str(_safe(stage)), str(_safe(model)), input_tokens, output_tokens,
                 total, float(cost) if cost is not None else None, _now()),
            )
            self._service._record_model_call(
                self.trace_id, identity, stage, model, "completed", connection=connection,
            )


class _UsageCallback(BaseCallbackHandler):
    """优先使用提供方聚合用量，否则读取 AIMessage.usage_metadata。"""

    raise_error = False

    def __init__(self, trace: TraceHandle):
        self.trace = trace
        self._runs = {}
        self._chains = {}
        self._lock = RLock()

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None,
                       metadata=None, **kwargs):
        details = metadata or {}
        with self._lock:
            parent = self._chains.get(str(parent_run_id), "model")
            self._chains[str(run_id)] = (
                details.get("langgraph_node") or details.get("stage")
                or kwargs.get("name") or parent
            )

    def _start(self, serialized, run_id, parent_run_id, metadata, kwargs):
        details = metadata or {}
        invocation = kwargs.get("invocation_params") or {}
        serialized = serialized or {}
        with self._lock:
            self._runs[str(run_id)] = {
                "stage": details.get("langgraph_node") or details.get("stage")
                or self._chains.get(str(parent_run_id)) or kwargs.get("name") or "model",
                "model": details.get("ls_model_name") or invocation.get("model")
                or invocation.get("model_name") or serialized.get("name") or "unknown",
            }
            details = self._runs[str(run_id)]
        self.trace._service._record_model_call(
            self.trace.trace_id, run_id, details["stage"], details["model"], "running",
        )

    def on_chat_model_start(self, serialized, messages, *, run_id,
                            parent_run_id=None, metadata=None, **kwargs):
        self._start(serialized, run_id, parent_run_id, metadata, kwargs)

    def on_llm_start(self, serialized, prompts, *, run_id,
                     parent_run_id=None, metadata=None, **kwargs):
        self._start(serialized, run_id, parent_run_id, metadata, kwargs)

    @staticmethod
    def _counts(usage):
        if not isinstance(usage, dict):
            return None
        input_count = usage.get("input_tokens", usage.get("prompt_tokens"))
        output_count = usage.get("output_tokens", usage.get("completion_tokens"))
        # 缺任意一侧都不能当成完整用量，更不能以 0 伪造缺失部分。
        if input_count is None or output_count is None:
            return None
        input_count, output_count = int(input_count or 0), int(output_count or 0)
        raw_total = usage.get("total_tokens")
        total = int(raw_total) if raw_total is not None else input_count + output_count
        return input_count, output_count, total

    def on_llm_end(self, response, *, run_id, **kwargs):
        details = self._runs.get(str(run_id), {"stage": "model", "model": "unknown"})
        model = details["model"]
        try:
            llm_output = getattr(response, "llm_output", None) or {}
            model = llm_output.get("model_name") or llm_output.get("model") or model
            usage = llm_output.get("token_usage") or llm_output.get("usage")
            counts = self._counts(usage)
            if counts is None:
                usages = []
                seen = set()
                for group in getattr(response, "generations", []) or []:
                    for generation in group:
                        message = getattr(generation, "message", None)
                        identity = getattr(message, "id", None) or id(message)
                        if message is None or identity in seen:
                            continue
                        seen.add(identity)
                        message_usage = getattr(message, "usage_metadata", None)
                        if not message_usage:
                            extra = getattr(message, "response_metadata", None) or {}
                            message_usage = extra.get("token_usage") or extra.get("usage")
                        result = self._counts(message_usage)
                        if result is not None:
                            usages.append(result)
                if not usages:
                    return
                counts = tuple(sum(item[index] for item in usages) for index in range(3))
            raw_cost = llm_output.get("total_cost")
            self.trace.record_usage(
                details["stage"], model,
                *counts, cost=raw_cost, run_id=run_id,
            )
        except Exception as error:
            self.trace._service._report_error(self.trace.trace_id, "usage.callback", error)
        finally:
            # 即使供应商没有返回 usage，或解析用量失败，也保留这次真实调用。
            self.trace._service._record_model_call(
                self.trace.trace_id, run_id, details["stage"], model, "completed",
            )

    def on_llm_error(self, error, *, run_id, **kwargs):
        response = kwargs.get("response")
        if response is not None:
            self.on_llm_end(response, run_id=run_id)
        details = self._runs.get(str(run_id), {"stage": "model", "model": "unknown"})
        self.trace._service._record_model_call(
            self.trace.trace_id, run_id, details["stage"], details["model"], "error",
        )
        self.trace._service._report_error(self.trace.trace_id, "model.call", error)


class ObservabilityService:
    """SQLite 为本地观测事实来源，Langfuse 为可选的远端分析服务。"""

    def __init__(self, db_path: Path, enabled=False, base_url=None,
                 public_key=None, secret_key=None, client=None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.enabled = bool(enabled)
        self._client = None
        self._public_key = public_key
        self._injected_client = client is not None
        self._startup_error = None
        self._last_trace_id = None
        self._closed = False
        with self._connection() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS obs_traces (
                    trace_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL,
                    question TEXT NOT NULL, output TEXT,
                    status TEXT NOT NULL, metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL, finished_at TEXT,
                    duration_ms REAL, report_errors TEXT NOT NULL DEFAULT '[]'
                );
                CREATE INDEX IF NOT EXISTS obs_traces_thread ON obs_traces(thread_id);
                CREATE TABLE IF NOT EXISTS obs_usage (
                    id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, run_id TEXT NOT NULL,
                    stage TEXT NOT NULL, model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL, cost REAL, created_at TEXT NOT NULL,
                    UNIQUE(trace_id, run_id)
                );
                CREATE TABLE IF NOT EXISTS obs_spans (
                    id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, name TEXT NOT NULL,
                    input TEXT, output TEXT, status TEXT NOT NULL, error TEXT,
                    duration_ms REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS obs_model_calls (
                    trace_id TEXT NOT NULL, run_id TEXT NOT NULL,
                    stage TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL,
                    usage_known INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(trace_id, run_id)
                );
                INSERT OR IGNORE INTO obs_model_calls
                    (trace_id, run_id, stage, model, status, usage_known, created_at, updated_at)
                    SELECT trace_id, run_id, stage, model, 'completed', 1, created_at, created_at
                    FROM obs_usage;
                CREATE TABLE IF NOT EXISTS obs_feedback (
                    id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, score REAL NOT NULL,
                    comment TEXT NOT NULL, created_at TEXT NOT NULL
                );
            """)
        if self.enabled:
            if client is not None:
                self._client = client
            elif not (base_url and public_key and secret_key):
                self._startup_error = "Langfuse 已启用，但地址或凭据尚未配置。"
            else:
                try:
                    from langfuse import Langfuse

                    self._client = Langfuse(
                        base_url=base_url, public_key=public_key, secret_key=secret_key,
                        mask=lambda *, data, **kwargs: _safe(data), timeout=5,
                    )
                except Exception as error:
                    self._startup_error = str(_safe(str(error)))

    @contextmanager
    def _connection(self):
        with closing(sqlite3.connect(self.db_path, timeout=10)) as connection:
            connection.row_factory = sqlite3.Row
            with connection:
                yield connection

    def _execute(self, statement, values=()):
        with self._connection() as connection:
            connection.execute(statement, values)

    def _update_trace(self, trace_id, fields):
        # 字段名仅来自本模块的固定集合，值始终参数化。
        allowed = {"output", "status", "metadata", "finished_at", "duration_ms"}
        if not fields or not set(fields).issubset(allowed):
            raise ValueError("无效的观测字段。")
        self._execute(
            "UPDATE obs_traces SET " + ", ".join(f"{key}=?" for key in fields)
            + " WHERE trace_id=?", (*fields.values(), trace_id),
        )

    def _record_model_call(self, trace_id, run_id, stage, model, status, *, connection=None):
        statement = (
            "INSERT INTO obs_model_calls "
            "(trace_id, run_id, stage, model, status, usage_known, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, EXISTS(SELECT 1 FROM obs_usage WHERE trace_id=? AND run_id=?), ?, ?) "
            "ON CONFLICT(trace_id,run_id) DO UPDATE SET "
            "stage=CASE WHEN excluded.stage='model' THEN obs_model_calls.stage ELSE excluded.stage END, "
            "model=CASE WHEN excluded.model='unknown' THEN obs_model_calls.model ELSE excluded.model END, "
            "status=CASE WHEN excluded.status='running' AND obs_model_calls.status!='running' "
            "THEN obs_model_calls.status WHEN obs_model_calls.status='error' THEN 'error' ELSE excluded.status END, "
            "usage_known=excluded.usage_known, updated_at=excluded.updated_at"
        )
        stamp = _now()
        values = (trace_id, str(run_id), str(_safe(stage)), str(_safe(model)), status,
                  trace_id, str(run_id), stamp, stamp)
        if connection is not None:
            connection.execute(statement, values)
        else:
            self._execute(statement, values)

    def _report_error(self, trace_id, stage, error):
        # 上报错误保存在本地；不输出异常堆栈、客户端 repr 或连接凭据。
        with self._connection() as connection:
            row = connection.execute(
                "SELECT report_errors FROM obs_traces WHERE trace_id=?", (trace_id,)
            ).fetchone()
            if row:
                records = json.loads(row[0])
                records.append({"stage": stage, "message": _safe(str(error))})
                connection.execute(
                    "UPDATE obs_traces SET report_errors=? WHERE trace_id=?",
                    (_json(records[-30:]), trace_id),
                )

    @contextmanager
    def trace(self, thread_id, question, metadata=None):
        trace_id = uuid4().hex
        self._last_trace_id = trace_id
        started = perf_counter()
        handle = TraceHandle(self, trace_id, metadata)
        self._execute(
            "INSERT INTO obs_traces "
            "(trace_id, thread_id, question, status, metadata, created_at) "
            "VALUES (?, ?, ?, 'running', ?, ?)",
            (trace_id, str(_safe(thread_id)), str(_safe(question)),
             _json(handle._metadata), _now()),
        )
        stack = ExitStack()
        if self._startup_error:
            self._report_error(trace_id, "langfuse.configure", self._startup_error)
        if self._client is not None:
            try:
                from langfuse import propagate_attributes

                stack.enter_context(propagate_attributes(session_id=str(thread_id)))
                handle._root = stack.enter_context(
                    self._client.start_as_current_observation(
                        name="deployment-assistant", as_type="agent",
                        trace_context={"trace_id": trace_id},
                        input={"question": _safe(question)}, metadata=handle._metadata,
                    )
                )
                if not self._injected_client:
                    from langfuse.langchain import CallbackHandler

                    context = {"trace_id": trace_id}
                    parent_id = getattr(handle._root, "id", None)
                    if parent_id:
                        context["parent_span_id"] = parent_id
                    handle.callbacks.append(CallbackHandler(
                        public_key=self._public_key, trace_context=context,
                    ))
            except Exception as error:
                self._report_error(trace_id, "langfuse.trace.start", error)
        try:
            yield handle
        except BaseException as error:
            handle.update(status="error", metadata={"error": _safe(str(error))})
            raise
        finally:
            with self._connection() as connection:
                connection.execute(
                    "UPDATE obs_traces SET status=CASE WHEN status='running' "
                    "THEN 'completed' ELSE status END, finished_at=?, duration_ms=? "
                    "WHERE trace_id=?", (_now(), (perf_counter() - started) * 1000, trace_id),
                )
            try:
                stack.close()
            except Exception as error:
                self._report_error(trace_id, "langfuse.trace.end", error)

    def record_feedback(self, trace_id, score: float, comment: str = "") -> dict:
        if not math.isfinite(float(score)) or not 0 <= float(score) <= 1:
            raise ValueError("反馈分数必须在 0 到 1 之间。")
        identity = uuid4().hex
        with self._connection() as connection:
            if not connection.execute(
                "SELECT 1 FROM obs_traces WHERE trace_id=?", (trace_id,)
            ).fetchone():
                raise ValueError("找不到对应的 Trace。")
            connection.execute(
                "INSERT INTO obs_feedback VALUES (?, ?, ?, ?, ?)",
                (identity, trace_id, float(score), str(_safe(comment)), _now()),
            )
        forwarded = False
        if self._client is not None:
            try:
                self._client.create_score(
                    score_id=identity, trace_id=trace_id, name="user_feedback",
                    value=float(score), data_type="NUMERIC", comment=_safe(comment),
                )
                forwarded = True
            except Exception as error:
                self._report_error(trace_id, "langfuse.feedback", error)
        return {"id": identity, "trace_id": trace_id, "score": float(score),
                "saved": True, "langfuse_submitted": forwarded}

    def finalize_recovered(self, trace_id: str, output, status: str) -> dict:
        """完成检查点已成功、但业务响应尚未落盘的原本地 Trace。

        不创建新 Trace、模型调用或用量；不宣称已同步远端 Langfuse。
        """
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM obs_traces WHERE trace_id=?", (trace_id,),
            ).fetchone()
            if row is None:
                raise ValueError("找不到待恢复的本地 Trace。")
            connection.execute(
                "UPDATE obs_traces SET output=?, status=?, "
                "finished_at=COALESCE(finished_at, ?) WHERE trace_id=?",
                (_json(output), str(_safe(status)), _now(), trace_id),
            )
        return {"trace_id": trace_id, "saved": True, "langfuse_submitted": False}

    @staticmethod
    def _aggregate(rows):
        known = [row["cost"] for row in rows if row["cost"] is not None]
        usage_rows = [row for row in rows if row["usage_known"]]
        missing = len(rows) - len(usage_rows)
        counts = {key: sum(row[key] for row in usage_rows)
                  for key in ("input_tokens", "output_tokens", "total_tokens")}
        return {
            "call_count": len(rows),
            "model_call_count": len(rows),
            "missing_usage_count": missing,
            **{key: value if not missing else None for key, value in counts.items()},
            **{f"known_{key}": value for key, value in counts.items()},
            "cost": sum(known) if rows and len(known) == len(rows) else None,
            "known_cost": sum(known) if known else None,
            "missing_cost_count": len(rows) - len(known),
        }

    def metrics(self, thread_id=None) -> dict:
        clause = " WHERE t.thread_id=?" if thread_id is not None else ""
        params = (thread_id,) if thread_id is not None else ()
        with self._connection() as connection:
            count = connection.execute(
                "SELECT count(*) FROM obs_traces t" + clause, params,
            ).fetchone()[0]
            rows = [dict(row) for row in connection.execute(
                "SELECT c.*, u.input_tokens, u.output_tokens, u.total_tokens, u.cost "
                "FROM obs_model_calls c JOIN obs_traces t ON t.trace_id=c.trace_id "
                "LEFT JOIN obs_usage u ON u.trace_id=c.trace_id AND u.run_id=c.run_id"
                + clause, params,
            )]
        result = {"trace_count": count, **self._aggregate(rows),
                  "by_model": {}, "by_stage": {}}
        for field, key in (("model", "by_model"), ("stage", "by_stage")):
            for name in sorted({row[field] for row in rows}):
                result[key][name] = self._aggregate([row for row in rows if row[field] == name])
        return result

    def list_traces(self, limit=50) -> list[dict]:
        if not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("记录数量必须为 1 到 500。")
        with self._connection() as connection:
            rows = [dict(row) for row in connection.execute(
                "SELECT * FROM obs_traces ORDER BY created_at DESC LIMIT ?", (limit,),
            )]
        for row in rows:
            for key in ("metadata", "report_errors", "output"):
                row[key] = json.loads(row[key]) if row[key] is not None else None
        return rows

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._client is not None:
            try:
                self._client.flush()
            except Exception as error:
                # 已结束 Trace 不再创建新的追踪；在最后一条本地记录保存上报错误。
                if self._last_trace_id:
                    self._report_error(self._last_trace_id, "langfuse.flush", error)
            finally:
                # 注入客户端的生命周期由调用方管理；内部创建的客户端释放后台线程。
                if not self._injected_client:
                    try:
                        self._client.shutdown()
                    except Exception as error:
                        if self._last_trace_id:
                            self._report_error(self._last_trace_id, "langfuse.shutdown", error)
