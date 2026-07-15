import atexit
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_SITE_PACKAGES = (
    PROJECT_ROOT
    / ".venv"
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)
if VENV_SITE_PACKAGES.exists():
    sys.path.insert(0, str(VENV_SITE_PACKAGES))
from _runtime import env



ZHIPU_API_KEY = env("ZHIPU_API_KEY")
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
DOWNLOAD_CHINOOK_DB = True
RUN_LIVE_DEMO = True
STABLE_TEMPERATURE = 0.1

OFFICIAL_SOURCE = "https://docs.langchain.com/oss/python/langchain/sql-agent"
CHINOOK_URL = "https://storage.googleapis.com/benchmarks-artifacts/chinook/Chinook.db"

SQL_AGENT_PROMPT = """
你是一个只读 SQL 数据库 agent。
先查看表，再查看相关表结构，然后生成 SELECT 查询。
不要执行 INSERT、UPDATE、DELETE、DROP、ALTER、CREATE 等写操作。
查询默认限制最多 5 行，除非用户明确要求更多。
如果 SQL 报错，根据错误重写查询再试。
"""


def load_dependencies():
    try:
        import requests
        from langchain.agents import create_agent
        from langchain.tools import tool
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError(
            "加载失败。需要安装 langchain、langchain-openai、pydantic、requests。"
            f"原始错误: {type(exc).__name__}: {exc}"
        ) from exc

    return {
        "BaseModel": BaseModel,
        "ChatOpenAI": ChatOpenAI,
        "Field": Field,
        "create_agent": create_agent,
        "requests": requests,
        "tool": tool,
    }


def build_model(ChatOpenAI, temperature=STABLE_TEMPERATURE, **kwargs):
    if not ZHIPU_API_KEY:
        raise RuntimeError("请先在文件顶部填写 ZHIPU_API_KEY，再运行真实 SQL agent demo。")
    return ChatOpenAI(
        model=ZHIPU_CHAT_MODEL,
        temperature=temperature,
        openai_api_key=ZHIPU_API_KEY,
        openai_api_base=ZHIPU_BASE_URL,
        timeout=60,
        **kwargs,
    )


def model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return {key: model_dump(item) for key, item in value.items()}
    if isinstance(value, list):
        return [model_dump(item) for item in value]
    return value

# @contextmanager 和 yield 配合，是为了把“打开资源 → 使用资源 → 关闭资源”写成 with 语法。
@contextmanager
def database_connection(database_path: Path, *, read_only: bool = False):
    """Open one SQLite connection for the current tool invocation only."""
    if read_only:
        database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(database_uri, uri=True)
    else:
        conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    try:
        # 表示函数先暂停，把 conn 临时交出去；
        # 产出一个值conn给调用方，然后暂停函数，等待下一次继续
        # 当 with 结束时，函数再继续执行 finally，关闭连接。
        yield conn
    finally:
        conn.close()


def create_sample_database() -> Path:
    """Create a temporary file-backed sample database for per-tool connections."""
    file_descriptor, raw_path = tempfile.mkstemp(
        prefix="langchain-l11-sql-agent-",
        suffix=".db",
    )
    os.close(file_descriptor)
    database_path = Path(raw_path)
    # 临时文件清理：登记一个“程序正常退出时执行”的清理函数
    atexit.register(database_path.unlink, missing_ok=True)

    with database_connection(database_path) as conn:
        conn.executescript(
            """
            CREATE TABLE Genre (
                GenreId INTEGER PRIMARY KEY,
                Name TEXT NOT NULL
            );
            CREATE TABLE Track (
                TrackId INTEGER PRIMARY KEY,
                Name TEXT NOT NULL,
                GenreId INTEGER NOT NULL,
                Milliseconds INTEGER NOT NULL,
                FOREIGN KEY (GenreId) REFERENCES Genre(GenreId)
            );
            INSERT INTO Genre VALUES
                (1, 'Rock'),
                (2, 'Jazz'),
                (3, 'Classical');
            INSERT INTO Track VALUES
                (1, 'Short Rock Song', 1, 180000),
                (2, 'Long Rock Song', 1, 420000),
                (3, 'Jazz Improvisation', 2, 540000),
                (4, 'Classical Movement', 3, 900000);
            """
        )
        conn.commit()
    return database_path


# 下载 SQLite 数据库文件到本地，并返回文件路径。
def download_chinook_database(deps, target_path: Path) -> Path:
    response = deps["requests"].get(CHINOOK_URL, timeout=30)
    response.raise_for_status()
    target_path.write_bytes(response.content)
    return target_path


def build_database_path(deps) -> Path:
    if DOWNLOAD_CHINOOK_DB:
        return download_chinook_database(
            deps,
            PROJECT_ROOT / "langchain" / "Chinook.db",
        )
    return create_sample_database()


def ensure_read_only_sql(query: str):
    stripped = query.strip().lower()
    blocked = ("insert", "update", "delete", "drop", "alter", "create", "replace")
    if not (stripped.startswith("select") or stripped.startswith("with")):
        raise ValueError("只允许 SELECT 或 WITH 查询。")
    if any(word in stripped for word in blocked):
        raise ValueError("检测到写操作关键字，拒绝执行。")


# 讲sql数据带列名的结果集转成字典列表，方便json序列化
# [
#     {"GenreId": 1, "Name": "Rock"},
#     {"GenreId": 2, "Name": "Jazz"},
# ]
def rows_to_dicts(cursor):
    return [dict(row) for row in cursor.fetchall()]


def define_sql_tools(deps, database_path: Path):
    BaseModel = deps["BaseModel"]
    Field = deps["Field"]
    tool = deps["tool"]

    class TableNamesInput(BaseModel):
        table_names: str = Field(description="逗号分隔的表名，例如 Genre, Track")

    class SqlInput(BaseModel):
        query: str = Field(description="只读 SQL 查询，只允许 SELECT 或 WITH")

    @tool
    def list_tables() -> str:
        """List available table names in the SQLite database."""
        with database_connection(database_path, read_only=True) as conn:
            cursor = conn.execute(
                # 默认打开的那个数据库文件里的表
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            return ", ".join(row["name"] for row in cursor.fetchall())

    @tool(args_schema=TableNamesInput)
    def describe_tables(table_names: str) -> str:
        """Show schema for one or more comma-separated table names."""
        # strip() 除字符串开头和结尾的空白字符，包括空格、制表符、换行
        # if bool(part.strip()): if 非空字符串 = true, 空字符串 = false
        parts = [part.strip() for part in table_names.split(",") if part.strip()]
        output = []
        with database_connection(database_path, read_only=True) as conn:
            for table in parts:
                cursor = conn.execute(f"PRAGMA table_info({table})")
                columns = rows_to_dicts(cursor)
                if not columns:
                    output.append(f"{table}: 表不存在或没有字段")
                    continue
                output.append(f"{table}: {json.dumps(columns, ensure_ascii=False)}")
        return "\n".join(output)

    @tool(args_schema=SqlInput)
    def check_sql_query(query: str) -> str:
        """Check whether a SQL query is read-only and syntactically valid."""
        ensure_read_only_sql(query)
        with database_connection(database_path, read_only=True) as conn:
            conn.execute(f"EXPLAIN QUERY PLAN {query}")
        return "SQL 检查通过，可以执行。"

    @tool(args_schema=SqlInput)
    def run_sql_query(query: str) -> str:
        """Run a read-only SQL query and return result rows."""
        ensure_read_only_sql(query)
        with database_connection(database_path, read_only=True) as conn:
            cursor = conn.execute(query)
            rows = rows_to_dicts(cursor)
        return json.dumps(rows[:20], ensure_ascii=False)

    return [list_tables, describe_tables, check_sql_query, run_sql_query]


def build_sql_agent(deps):
    database_path = build_database_path(deps)
    tools = define_sql_tools(deps, database_path)
    agent = deps["create_agent"](
        model=build_model(deps["ChatOpenAI"]),
        tools=tools,
        system_prompt=SQL_AGENT_PROMPT,
    )
    return {
        "agent": agent,
        "database_path": database_path,
        "tools": tools,
    }


def tool_only_demo(deps):
    database_path = build_database_path(deps)
    tools = {item.name: item for item in define_sql_tools(deps, database_path)}
    query = """
    SELECT g.Name AS genre, AVG(t.Milliseconds) AS avg_ms
    FROM Track t
    JOIN Genre g ON g.GenreId = t.GenreId
    GROUP BY g.Name
    ORDER BY avg_ms DESC
    LIMIT 5
    """
    return {
        "official_source": OFFICIAL_SOURCE,
        "tables": tools["list_tables"].invoke({}),
        "schema": tools["describe_tables"].invoke({"table_names": "Genre, Track"}),
        "check": tools["check_sql_query"].invoke({"query": query}),
        "rows": json.loads(tools["run_sql_query"].invoke({"query": query})),
    }


def sql_agent_demo(deps):
    bundle = build_sql_agent(deps)
    question = "Which genre on average has the longest tracks?"
    return bundle["agent"].invoke(
        {"messages": [{"role": "user", "content": question}]},
    )


def run(title, func, deps):
    try:
        print(f"\n===== {title} =====")
        print(json.dumps(model_dump(func(deps)), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"跳过：{type(exc).__name__}: {exc}")


def main():
    try:
        deps = load_dependencies()
    except RuntimeError as exc:
        print(exc)
        return

    run("1. SQL tools: list/schema/check/query", tool_only_demo, deps)
    if RUN_LIVE_DEMO:
        run("2. create_agent SQL 问答", sql_agent_demo, deps)


if __name__ == "__main__":
    main()
