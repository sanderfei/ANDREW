import json
import sqlite3
import sys
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


ZHIPU_API_KEY = "sk-lLKjavEquIsN4nk6eguOXFlhBXbXntGLHo5tOhbQWkBztYbj"
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
DOWNLOAD_CHINOOK_DB = False
RUN_LIVE_DEMO = False
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


def create_sample_database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
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
    return conn


def download_chinook_database(deps, target_path: Path):
    response = deps["requests"].get(CHINOOK_URL, timeout=30)
    response.raise_for_status()
    target_path.write_bytes(response.content)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn


def build_connection(deps):
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


def rows_to_dicts(cursor):
    return [dict(row) for row in cursor.fetchall()]


def define_sql_tools(deps, conn):
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
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return ", ".join(row["name"] for row in cursor.fetchall())

    @tool(args_schema=TableNamesInput)
    def describe_tables(table_names: str) -> str:
        """Show schema for one or more comma-separated table names."""
        parts = [part.strip() for part in table_names.split(",") if part.strip()]
        output = []
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
        conn.execute(f"EXPLAIN QUERY PLAN {query}")
        return "SQL 检查通过，可以执行。"

    @tool(args_schema=SqlInput)
    def run_sql_query(query: str) -> str:
        """Run a read-only SQL query and return result rows."""
        ensure_read_only_sql(query)
        cursor = conn.execute(query)
        rows = rows_to_dicts(cursor)
        return json.dumps(rows[:20], ensure_ascii=False)

    return [list_tables, describe_tables, check_sql_query, run_sql_query]


def build_sql_agent(deps):
    conn = build_connection(deps)
    tools = define_sql_tools(deps, conn)
    agent = deps["create_agent"](
        model=build_model(deps["ChatOpenAI"]),
        tools=tools,
        system_prompt=SQL_AGENT_PROMPT,
    )
    return {
        "agent": agent,
        "connection": conn,
        "tools": tools,
    }


def tool_only_demo(deps):
    conn = build_connection(deps)
    tools = {item.name: item for item in define_sql_tools(deps, conn)}
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
