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



ZHIPU_API_KEY = env("ZHIPU_API_KEY")
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
LANGSMITH_API_KEY = env("LANGSMITH_API_KEY")
RUN_LIVE_DEMO = False
STABLE_TEMPERATURE = 0.1

OFFICIAL_SOURCE = "https://docs.langchain.com/oss/python/langchain/deep-agent-from-scratch"


def load_dependencies():
    try:
        from langchain.agents import create_agent
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError(
            "加载失败。需要安装 langchain、langchain-openai。"
            f"原始错误: {type(exc).__name__}: {exc}"
        ) from exc

    return {
        "ChatOpenAI": ChatOpenAI,
        "create_agent": create_agent,
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


def build_langsmith_sandbox_agent(deps, use_summarization=True, use_skills=True, use_visualizer=True):
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


def main():
    try:
        deps = load_dependencies()
    except RuntimeError as exc:
        print(exc)
        return

    print(json.dumps(describe_official_stack(), ensure_ascii=False, indent=2))
    if RUN_LIVE_DEMO:
        print(json.dumps(model_dump(minimal_agent_demo(deps)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
