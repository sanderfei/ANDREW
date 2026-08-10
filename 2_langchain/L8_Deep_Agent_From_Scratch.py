import csv
import io
import json
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
from _runtime import env


LOCAL_SANDBOX_ROOT = Path(__file__).resolve().parent / ".local_l8_sandbox"

ZHIPU_API_KEY = env("ZHIPU_API_KEY")
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
LANGSMITH_API_KEY = env("LANGSMITH_API_KEY")
RUN_LOCAL_SANDBOX_AGENT_DEMO = False
RUN_MINIMAL_AGENT_DEMO = False
RUN_LANGSMITH_SANDBOX_DEMO = False
STABLE_TEMPERATURE = 0.1

OFFICIAL_SOURCE = "https://docs.langchain.com/oss/python/langchain/deep-agent-from-scratch"


def load_dependencies():
    try:
        from langchain.agents import create_agent
        from langchain.tools import tool
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError(
            "加载失败。需要安装 langchain、langchain-openai、pydantic。"
            f"原始错误: {type(exc).__name__}: {exc}"
        ) from exc

    return {
        "BaseModel": BaseModel,
        "ChatOpenAI": ChatOpenAI,
        "Field": Field,
        "create_agent": create_agent,
        "tool": tool,
    }


def build_model(ChatOpenAI, temperature=STABLE_TEMPERATURE, **kwargs):
    if not ZHIPU_API_KEY:
        raise RuntimeError("请先在文件顶部填写 ZHIPU_API_KEY，再运行真实模型 demo。")
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


def sample_sales_csv() -> str:
    rows = [
        ["Date", "Product", "Units", "Revenue"],
        ["2025-08-01", "Widget A", 10, 250],
        ["2025-08-02", "Widget B", 5, 125],
        ["2025-08-03", "Widget A", 7, 175],
        ["2025-08-04", "Widget C", 3, 90],
    ]
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def pandas_skill_file() -> tuple[str, bytes]:
    content = """---
name: pandas-patterns
description: Common pandas and matplotlib patterns for data analysis and visualization
---

## Data loading
Use `pd.read_csv()` for CSV files. Start by checking columns, dtypes, nulls, and summary statistics.

## Analysis
Group by business dimensions before calculating totals, averages, or trends.

## Visualization
Use matplotlib for simple charts. Save final figures as PNG files.

## Reporting
Write a short markdown summary and list any generated artifact paths.
"""
    return "/skills/pandas-patterns/SKILL.md", content.encode()


def write_local_sandbox_files(root: Path):
    root.mkdir(parents=True, exist_ok=True)

    sales_path = root / "sales.csv"
    sales_path.write_text(sample_sales_csv(), encoding="utf-8")

    skill_name, skill_content = pandas_skill_file()
    skill_path = root / skill_name.lstrip("/")
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_bytes(skill_content)

    return {
        "sales_path": sales_path,
        "skill_path": skill_path,
    }


def analyze_sales_csv(sales_path: Path):
    with sales_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    product_summary = {}
    for row in rows:
        product = row["Product"]
        units = int(row["Units"])
        revenue = float(row["Revenue"])
        item = product_summary.setdefault(
            product,
            {
                "product": product,
                "units": 0,
                "revenue": 0.0,
            },
        )
        item["units"] += units
        item["revenue"] += revenue

    products = sorted(
        product_summary.values(),
        key=lambda item: item["revenue"],
        reverse=True,
    )
    total_units = sum(item["units"] for item in products)
    total_revenue = sum(item["revenue"] for item in products)

    return {
        "row_count": len(rows),
        "total_units": total_units,
        "total_revenue": total_revenue,
        "best_product_by_revenue": products[0]["product"] if products else None,
        "product_summary": products,
    }


def build_local_report(analysis):
    lines = [
        "# Local L8 Sandbox Report",
        "",
        f"- Total rows: {analysis['row_count']}",
        f"- Total units: {analysis['total_units']}",
        f"- Total revenue: {analysis['total_revenue']}",
        f"- Best product by revenue: {analysis['best_product_by_revenue']}",
        "",
        "## Product Summary",
        "",
        "| Product | Units | Revenue |",
        "| --- | ---: | ---: |",
    ]
    for item in analysis["product_summary"]:
        lines.append(f"| {item['product']} | {item['units']} | {item['revenue']} |")
    return "\n".join(lines) + "\n"


def safe_sandbox_path(path: str) -> Path:
    relative = path.lstrip("/")
    candidate = (LOCAL_SANDBOX_ROOT / relative).resolve()
    root = LOCAL_SANDBOX_ROOT.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"路径越界，不允许访问 sandbox 外部文件: {path}")
    return candidate


def define_local_sandbox_tools(deps):
    BaseModel = deps["BaseModel"]
    Field = deps["Field"]
    tool = deps["tool"]

    class SandboxPathInput(BaseModel):
        path: str = Field(description="sandbox 内文件路径，例如 /sales.csv")

    class ReportInput(BaseModel):
        report_path: str = Field(description="报告写入路径，例如 /analysis_report.md")
        title: str = Field(description="报告标题")
        summary: str = Field(description="模型根据分析结果写出的中文总结")

    @tool
    def list_sandbox_files() -> str:
        """列出本地模拟 sandbox 里的文件。"""
        write_local_sandbox_files(LOCAL_SANDBOX_ROOT)
        files = [
            "/" + str(path.relative_to(LOCAL_SANDBOX_ROOT))
            for path in LOCAL_SANDBOX_ROOT.rglob("*")
            if path.is_file()
        ]
        return "\n".join(sorted(files))

    @tool(args_schema=SandboxPathInput)
    def read_sandbox_file(path: str) -> str:
        """读取本地模拟 sandbox 中的文本文件。"""
        target = safe_sandbox_path(path)
        return target.read_text(encoding="utf-8")

    @tool(args_schema=SandboxPathInput)
    def analyze_sales_file(path: str) -> str:
        """读取 sales CSV 并返回按产品汇总的 JSON 分析结果。"""
        target = safe_sandbox_path(path)
        analysis = analyze_sales_csv(target)
        return json.dumps(analysis, ensure_ascii=False)

    @tool(args_schema=ReportInput)
    def write_analysis_report(report_path: str, title: str, summary: str) -> str:
        """把模型总结写入 sandbox 内的 Markdown 报告文件。"""
        target = safe_sandbox_path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        content = f"# {title}\n\n{summary.strip()}\n"
        target.write_text(content, encoding="utf-8")
        return f"报告已写入: /{target.relative_to(LOCAL_SANDBOX_ROOT)}"

    return [
        list_sandbox_files,
        read_sandbox_file,
        analyze_sales_file,
        write_analysis_report,
    ]


def build_local_sandbox_agent(deps):
    write_local_sandbox_files(LOCAL_SANDBOX_ROOT)
    return deps["create_agent"](
        model=build_model(deps["ChatOpenAI"]),
        tools=define_local_sandbox_tools(deps),
        system_prompt=(
            "你是一个本地 sandbox 数据分析 agent。"
            "你不能直接访问真实文件系统，只能通过工具访问 sandbox。"
            "先列出文件，再读取 /sales.csv，然后调用 analyze_sales_file，"
            "最后用 write_analysis_report 写出 /agent_analysis_report.md。"
            "最终回答要包含关键数字和报告路径。"
        ),
    )


def local_sandbox_agent_demo(deps):
    agent = build_local_sandbox_agent(deps)
    return agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "请分析 sandbox 里的销售 CSV，找出总销量、总营收、"
                        "营收最高的产品，并写一份 Markdown 报告。"
                    ),
                }
            ]
        }
    )


def describe_official_stack():
    return {
        "official_source": OFFICIAL_SOURCE,
        "idea": "从 create_agent 开始，逐步加 sandbox、filesystem、summarization、skills、subagent。",
        "steps": [
            {
                "name": "minimal_agent",
                "adds": "只有模型和 agent loop，没有文件系统，也不能执行代码。",
            },
            {
                "name": "filesystem_sandbox",
                "adds": "把 LangSmith sandbox 通过 FilesystemMiddleware 暴露成 read/write/execute 等工具。",
            },
            {
                "name": "summarization",
                "adds": "长会话时压缩旧消息，避免工具输出把上下文撑满。",
            },
            {
                "name": "skills",
                "adds": "把 pandas 等领域经验按需加载，而不是一开始全塞进 system prompt。",
            },
            {
                "name": "visualizer_subagent",
                "adds": "把图表生成交给隔离上下文的子 agent，主 agent 只看最终结果。",
            },
        ],
    }


def build_minimal_agent(deps):
    return deps["create_agent"](
        model=build_model(deps["ChatOpenAI"]),
        tools=[],
        system_prompt=(
            "你是一个数据分析教学 agent。回答时说明自己还没有 sandbox，"
            "因此只能基于用户粘贴的数据做推理。"
        ),
    )


def build_langsmith_sandbox_agent(
    deps,
    use_summarization=True,
    use_skills=True,
    use_visualizer=True,
):
    try:
        from deepagents import SubAgent
        from deepagents.backends.langsmith import LangSmithSandbox
        from deepagents.middleware import (
            FilesystemMiddleware,
            SkillsMiddleware,
            SubAgentMiddleware,
            SummarizationMiddleware,
        )
        from langchain.agents.middleware import TodoListMiddleware
        from langsmith.sandbox import SandboxClient
    except ImportError as exc:
        raise RuntimeError(
            "运行 sandbox 版 deep agent 需要安装 deepagents、langsmith。"
            f"原始错误: {type(exc).__name__}: {exc}"
        ) from exc

    if not LANGSMITH_API_KEY:
        raise RuntimeError("sandbox 版需要在文件顶部填写 LANGSMITH_API_KEY。")

    model = build_model(deps["ChatOpenAI"])
    client = SandboxClient(api_key=LANGSMITH_API_KEY)
    sandbox = client.create_sandbox(name="andrew-langchain-deep-agent")
    backend = LangSmithSandbox(sandbox=sandbox)
    backend.upload_files([("/sales.csv", sample_sales_csv().encode())])

    middleware = [FilesystemMiddleware(backend=backend)]
    if use_summarization:
        middleware.append(SummarizationMiddleware(model=model, backend=backend))
    if use_skills:
        backend.upload_files([pandas_skill_file()])
        middleware.append(SkillsMiddleware(backend=backend, sources=["/skills/"]))
    if use_visualizer:
        visualizer: SubAgent = {
            "name": "visualizer",
            "description": "Generate charts and visualizations from sandbox data files.",
            "system_prompt": (
                "你是数据可视化子 agent。使用 Python 生成图表，"
                "把图片保存成 PNG，并返回文件路径和简短说明。"
            ),
            "tools": [],
            "model": model,
        }
        middleware.append(TodoListMiddleware())
        middleware.append(SubAgentMiddleware(backend=backend, subagents=[visualizer]))

    agent = deps["create_agent"](
        model=model,
        tools=[],
        middleware=middleware,
        system_prompt="你是一个可以在 sandbox 中读写文件和分析 CSV 的数据分析 agent。",
    )
    return {
        "agent": agent,
        "backend": backend,
        "sandbox": sandbox,
    }


def minimal_agent_demo(deps):
    agent = build_minimal_agent(deps)
    return agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "请说明你现在为什么还不能直接读取 /sales.csv。",
                }
            ]
        }
    )


def langsmith_sandbox_agent_demo(deps):
    bundle = build_langsmith_sandbox_agent(deps)
    agent = bundle["agent"]
    return agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "请读取 /sales.csv，分析总销量、总营收、营收最高的产品，"
                        "如果需要可以使用 skills 和子 agent，最后生成 Markdown 报告并保存。"
                    ),
                }
            ]
        }
    )


# 启动命令：.venv/bin/python 2_langchain/L8_Deep_Agent_From_Scratch.py
# 参数枚举：无命令行参数；通过文件顶部的三个 RUN_* 开关选择本地、最小或远端 Demo。
def main():
    try:
        deps = load_dependencies()
    except RuntimeError as exc:
        print(exc)
        return

    print(json.dumps(describe_official_stack(), ensure_ascii=False, indent=2))
    if RUN_LOCAL_SANDBOX_AGENT_DEMO:
        print(
            json.dumps(
                model_dump(local_sandbox_agent_demo(deps)),
                ensure_ascii=False,
                indent=2,
            )
        )
    if RUN_MINIMAL_AGENT_DEMO:
        print(json.dumps(model_dump(minimal_agent_demo(deps)), ensure_ascii=False, indent=2))
    if RUN_LANGSMITH_SANDBOX_DEMO:
        print(
            json.dumps(
                model_dump(langsmith_sandbox_agent_demo(deps)),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
