"""本地会话、持久化检查点、诊断连接、归档任务与观测的运行时。"""

from contextlib import closing, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
import sqlite3
from threading import Event, Thread

from langgraph.checkpoint.sqlite import SqliteSaver

from config import BusinessSettings, load_business_settings
from services.ingestion import redact
from services.knowledge_business import KnowledgeBusiness
from services.observability import ObservabilityService
from services.remote_diagnostics import RemoteDiagnosticsService


class SessionBusyError(RuntimeError):
    pass


def _safe(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(key): "[REDACTED]" if str(key).lower() in {"password", "secret", "api_key", "private_key"}
                else _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    return value


class SessionStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.locks = self.path.parent / "session-locks"
        self.locks.mkdir(exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS assistant_sessions (thread_id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS assistant_responses (thread_id TEXT NOT NULL, request_id TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(thread_id,request_id))")

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextmanager
    def lock(self, thread_id: str):
        # 跨进程文件锁随进程退出释放；不留下永久 busy 状态。
        import fcntl
        path = self.locks / (sha256(thread_id.encode()).hexdigest() + ".lock")
        with path.open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SessionBusyError("此会话仍有任务执行，请等待完成后继续。") from None
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def get(self, thread_id: str) -> dict | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT data FROM assistant_sessions WHERE thread_id=?", (thread_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, thread_id: str, data: dict, request_id: str | None = None, response: dict | None = None):
        data = _safe({**data, "thread_id": thread_id, "updated_at": datetime.now(timezone.utc).isoformat()})
        with closing(self._connect()) as conn, conn:
            conn.execute("INSERT INTO assistant_sessions VALUES(?,?,?) ON CONFLICT(thread_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at",
                         (thread_id, json.dumps(data, ensure_ascii=False), data["updated_at"]))
            if request_id and response:
                conn.execute("INSERT OR REPLACE INTO assistant_responses VALUES(?,?,?)",
                             (thread_id, request_id, json.dumps(_safe(response), ensure_ascii=False)))

    def cached(self, thread_id: str, request_id: str | None) -> dict | None:
        if not request_id:
            return None
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT response FROM assistant_responses WHERE thread_id=? AND request_id=?", (thread_id, request_id)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT data FROM assistant_sessions ORDER BY updated_at DESC LIMIT 50").fetchall()
        return [json.loads(row[0]) for row in rows]


class BusinessRuntime:
    def __init__(self, settings: BusinessSettings | None = None, *, remote=None, knowledge=None, observability=None,
                 retriever_factory=None):
        self.settings = settings or load_business_settings()
        directory = self.settings.runtime_dir
        directory.mkdir(parents=True, exist_ok=True)
        self.sessions = SessionStore(directory / "assistant.sqlite3")
        self._checkpoint_conn = sqlite3.connect(directory / "checkpoints.sqlite3", check_same_thread=False, timeout=15)
        self.checkpointer = SqliteSaver(self._checkpoint_conn)
        self.remote = remote or RemoteDiagnosticsService(
            ttl_seconds=self.settings.connection_ttl, command_timeout=self.settings.command_timeout,
            max_output_chars=self.settings.max_output_chars, known_hosts_path=self.settings.known_hosts_path)
        self.knowledge = knowledge or KnowledgeBusiness(directory / "assistant.sqlite3", self.settings.source_dir, retriever_factory)
        self.observability = observability or ObservabilityService(
            directory / "assistant.sqlite3", enabled=self.settings.langfuse_enabled,
            base_url=self.settings.langfuse_base_url, public_key=self.settings.langfuse_public_key,
            secret_key=self.settings.langfuse_secret_key,
            environment=self.settings.langfuse_environment)
        self._stop = Event()
        self._wake = Event()
        self._worker = None
        self._closed = False

    def start(self):
        if self.settings.auto_index and self._worker is None:
            self._worker = Thread(target=self._index_loop, name="assistant-index-jobs", daemon=True)
            self._worker.start()

    def _index_loop(self):
        while not self._stop.is_set():
            try:
                self.knowledge.run_index_jobs(limit=3)
            except Exception:
                logging.getLogger(__name__).warning("知识入库任务本轮执行失败，将保留任务并重试。")
            self._wake.wait(self.settings.index_interval)
            self._wake.clear()

    def wake_indexer(self):
        self._wake.set()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._stop.set()
        self._wake.set()
        if self._worker:
            self._worker.join(timeout=5)
        if hasattr(self.remote, "close"):
            self.remote.close()
        self.observability.close()
        self._checkpoint_conn.close()
