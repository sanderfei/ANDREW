"""Part 4：只读 SQLite 与业务指标白名单 Tool。

官方 SQL Agent 允许模型生成 SQL；本地适配先采用更窄的业务白名单：
模型只能选择 metric 和 region，不能把任意 SQL 交给数据库。

运行：
    .venv/bin/python 5_langgraph_agentic_rag/part4_readonly_sql_tools.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Literal

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field


PROJECT_DIR = Path(__file__).resolve().parent
OFFICIAL_SOURCE = "https://docs.langchain.com/oss/python/langchain/sql-agent"
MetricName = Literal[
    "completed_order_count",
    "completed_revenue",
    "average_completed_order_value",
]
RegionName = Literal["all", "华东", "华南", "华北"]


class BusinessMetricInput(BaseModel):
    metric: MetricName = Field(description="允许查询的业务指标名称。")
    region: RegionName = Field(
        default="all",
        description="区域过滤；all 表示全部区域。",
    )


METRIC_SQL: dict[str, tuple[str, str]] = {
    "completed_order_count": (
        "SELECT COUNT(*) FROM orders WHERE status = 'completed'",
        "orders",
    ),
    "completed_revenue": (
        "SELECT COALESCE(SUM(amount), 0) FROM orders "
        "WHERE status = 'completed'",
        "CNY",
    ),
    "average_completed_order_value": (
        "SELECT COALESCE(AVG(amount), 0) FROM orders "
        "WHERE status = 'completed'",
        "CNY/order",
    ),
}


def initialize_demo_database(path: Path) -> None:
    """创建不含敏感信息的固定教学数据；已有非空数据库不重复写入。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                region TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        row_count = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if row_count == 0:
            connection.executemany(
                "INSERT INTO orders(id, region, amount, status) VALUES (?, ?, ?, ?)",
                [
                    (1, "华东", 120.5, "completed"),
                    (2, "华北", 80.0, "completed"),
                    (3, "华东", 50.0, "cancelled"),
                    (4, "华南", 200.0, "completed"),
                ],
            )
        connection.commit()
    finally:
        connection.close()


def _readonly_connection(path: Path) -> sqlite3.Connection:
    """数据库 URI 使用 mode=ro，SQLite 层面拒绝写操作。"""

    uri = f"{path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only = ON")
    return connection


def build_business_metric_tool(database_path: Path) -> BaseTool:
    if not database_path.is_file():
        raise FileNotFoundError(f"数据库不存在：{database_path}")

    @tool(args_schema=BusinessMetricInput)
    def query_business_metric(
        metric: MetricName,
        region: RegionName = "all",
    ) -> str:
        """查询白名单内的订单指标；不能执行任意 SQL。"""

        sql, unit = METRIC_SQL[metric]
        parameters: tuple[str, ...] = ()
        if region != "all":
            sql += " AND region = ?"
            parameters = (region,)

        connection = _readonly_connection(database_path)
        try:
            row = connection.execute(sql, parameters).fetchone()
        finally:
            connection.close()
        value = row[0] if row else 0
        if isinstance(value, float):
            value = round(value, 2)
        return json.dumps(
            {
                "metric": metric,
                "region": region,
                "value": value,
                "unit": unit,
                "data_source": "local_readonly_sqlite",
            },
            ensure_ascii=False,
        )

    return query_business_metric


def run_demo(database_path: Path) -> dict[str, object]:
    initialize_demo_database(database_path)
    metric_tool = build_business_metric_tool(database_path)
    all_revenue = json.loads(
        metric_tool.invoke(
            {
                "metric": "completed_revenue",
                "region": "all",
            }
        )
    )
    east_count = json.loads(
        metric_tool.invoke(
            {
                "metric": "completed_order_count",
                "region": "华东",
            }
        )
    )
    return {
        "database": str(database_path),
        "tool_name": metric_tool.name,
        "all_completed_revenue": all_revenue,
        "east_completed_order_count": east_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="演示只读 SQL 白名单 Tool")
    parser.add_argument(
        "--database",
        type=Path,
        default=PROJECT_DIR / "runtime" / "business_demo.db",
    )
    args = parser.parse_args(argv)
    print(
        json.dumps(
            {
                "official_source": OFFICIAL_SOURCE,
                "result": run_demo(args.database),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

