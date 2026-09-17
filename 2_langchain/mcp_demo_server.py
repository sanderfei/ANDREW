"""L15 配套的本地 stdio MCP Server，只暴露两个确定性教学工具。"""

""" 
@mcp.resource 和 @mcp.prompt 是 FastMCP 提供的注册装饰器
你想让 Server 提供课程资料，就注册 Resource；
想提供消息模板，就注册 Prompt。

load_mcp_resources、load_mcp_prompt 则是 Client 侧的 LangChain 适配器函数
它们通过 MCP 协议请求 Server，不会直接调用 Server 文件里的 Python 函数。
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "andrew-course-tools",
    instructions="提供课程摘要和整数加法；不访问网络与宿主文件。",
    log_level="ERROR",
)


@mcp.tool()
def course_lookup(topic: str) -> dict[str, str]:
    """查询一个 Agent 学习主题的本地课程摘要。"""

    summaries = {
        "MCP": "MCP 把工具提供方与 Agent 运行进程解耦。",
        "LangGraph": "LangGraph 用 State、Node 和 Edge 表达可持久化工作流。",
    }
    return {
        "topic": topic,
        "summary": summaries.get(topic, "当前本地 MCP Server 没有这个主题。"),
    }


@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """返回两个整数之和。"""

    return a + b


# 注册一个可按 URI 读取的资源模板；
# course:// 是本示例自定义的 URI 格式，不表示访问网站。
# URI 中的变量。Client 请求 course://MCP 时，Server 解析出 topic="MCP"。
# L15中：Client: load_mcp_resources(session, uris="course://MCP")
#   → MCP 请求：resources/read，uri="course://MCP"
#   → Server 匹配已注册的 "course://{topic}"
#   → 得到 topic="MCP"
#   → 执行 course_material(topic="MCP")
#   → 返回 "# MCP\n\n这是由本地 MCP Server 提供的只读课程资料。"
#   → LangChain 适配器把结果转换成 Blob
@mcp.resource(
    "course://{topic}",
    # 资源模板的名称，供展示和发现
    name="course_material",
    # 告诉 Client 这份资源是什么
    description="读取某个主题的 Markdown 课程资料。",
    # 声明返回内容是 Markdown 文本
    mime_type="text/markdown",
)

# 真正生成资料的 Python 函数；收到读取请求时才执行。
def course_material(topic: str) -> str:
    """返回 MCP Resource；Resource 是可读取资料，不是可执行 Tool。"""

    return f"# {topic}\n\n这是由本地 MCP Server 提供的只读课程资料。\n"


# L15中：Client: load_mcp_prompt(session, "explain_topic", arguments={"topic": "MCP"})
#   → MCP 请求：prompts/get，name="explain_topic"，arguments={"topic": "MCP"}
#   → Server 找到 @mcp.prompt(name="explain_topic") 注册的函数
#   → 执行 explain_topic(topic="MCP")
#   → 返回“请用 State、Context、Store 三个层次解释 MCP。”
#   → LangChain 适配器转换成 HumanMessage
@mcp.prompt(name="explain_topic", description="生成解释课程主题的消息模板。")
def explain_topic(topic: str) -> str:
    """返回 MCP Prompt 模板。"""

    return f"请用 State、Context、Store 三个层次解释 {topic}。"


# 启动命令：
#   .venv/bin/python 2_langchain/mcp_demo_server.py
# 参数枚举：无；使用 stdio transport，由 MCP Client 启动并通信。
def main() -> int:
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
