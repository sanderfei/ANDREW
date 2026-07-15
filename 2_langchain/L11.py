
import atexit
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile

from langchain.L11_SQL_Agent import CHINOOK_URL, SQL_AGENT_PROMPT, ensure_read_only_sql, rows_to_dicts, build_database_path, build_model, model_dump


@contextmanager
def database_connection(database_path: Path, * , read_only: bool = False):
    """Open one SQLite connection for the current tool invocation only."""
    if read_only:
        conn = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    try:
        # 表示函数先暂停，把 conn 临时交出去；
        # 当 with 结束时，函数再继续执行 finally，关闭连接。
        yield conn
    finally:
        conn.close()

def create_sample_database()->Path:
    file_descriptor, raw_path = tempfile.mkstemp(
        prefix="langchain-l11-sql-agent-",
        suffix=".db",
    )
    os.close(file_descriptor)
    database_path = Path(raw_path)
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

def download_chinook_database(deps, target_path: Path) -> Path:
    response = deps["requests"].get(CHINOOK_URL, timeout=30)
    response.raise_for_status()
    target_path.write_bytes(response.content)
    return target_path

def define_sql_tools(deps, database_path: Path):
    BaseModel = deps["BaseModel"]
    Field = deps["Field"]
    tool = deps["tool"]

    class TableNameInput(BaseModel):
        table_name: str = Field(
            ...,
            description="逗号分隔的表名，例如 Genre, Track",
        )

    class SqlInput(BaseModel):
        query: str = Field(..., description="只读 SQL 查询，只允许 SELECT 或 WITH")

    @tool
    def list_tables() -> str:
        """List available table names in the SQLite database."""
        with database_connection(database_path, read_only=True) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            )
            table_names = [row["name"] for row in cursor.fetchall()]
        return ", ".join(table_names)
    
    @tool(args_schema=TableNameInput)
    def describe_tables(table_names: str) -> str:
        """Show schema for one or more comma-separated table names."""
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