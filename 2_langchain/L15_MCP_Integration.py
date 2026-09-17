"""L15：通过 stdio MCP Server 动态发现工具并交给 LangChain Agent。

MCP（Model Context Protocol）是 Agent 应用与能力提供方之间的标准协议。
Server 可以发布可执行的 Tool、可读取的 Resource 和可加载的 Prompt
Client 按协议发现并使用它们。它本身不是模型，也不负责 Agent 的决策。

本课不调用网络模型：Client 会启动同目录的 ``mcp_demo_server.py`` 子进程，
先验证 MCP Tool 可以直接调用，再验证 ``create_agent`` 能执行同一个远程工具。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.prompts import load_mcp_prompt
from langchain_mcp_adapters.resources import load_mcp_resources

from _offline_chat_model import ToolCallingFakeChatModel

SERVER_PATH = Path(__file__).with_name("mcp_demo_server.py").resolve()


# 只创建 Client 并保存启动配置 可以理解为写好一张说明：“将来用当前 Python 运行 mcp_demo_server.py。”
def build_client() -> MultiServerMCPClient:
    """配置 stdio transport；MCP Server 与 Client 是两个独立进程。"""

    return MultiServerMCPClient(
        {
            "course": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(SERVER_PATH)],
                "cwd": str(SERVER_PATH.parent),
            }
        }
    )


def _schema_dict(schema: Any) -> dict[str, Any]:
    if isinstance(schema, dict):
        return schema
    return schema.model_json_schema()


def _content_text(value: Any) -> str:
    """MCP Adapter 可能返回标准 content blocks，而不是裸字符串。"""

    if isinstance(value, list):
        return "".join(
            str(block.get("text", ""))
            for block in value
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(value)


# 本地 MCP Server 发布课程查询工具
# → Client 通过 stdio 发现工具
# → LangChain Adapter 将其转为 Agent 可用的 Tool
# → Agent 发出 Tool Call
# → Server 执行工具并返回结果
async def run_demo() -> dict[str, Any]:
    client = build_client()

    # Client 按配置启动这个独立的 Python 子进程，问它“你提供哪些工具？”
    # Server 在 mcp_demo_server.py:53)执行 mcp.run(transport="stdio")，通过标准输入和标准输出回复工具列表。
    # 直接运行当前文件，执行到 client.get_tools() 时，会按 build_client() 中的配置自动启动 mcp_demo_server.py 子进程，然后从它获取 course_lookup 和 add_numbers。
    tools = await client.get_tools(server_name="course")

    tools_by_name = {tool.name: tool for tool in tools}
    if set(tools_by_name) != {"course_lookup", "add_numbers"}:
        raise AssertionError(f"MCP Tool 列表与预期不一致: {sorted(tools_by_name)}")

    # 调用已经发现的 Tool，.ainvoke() 会处理连接
    direct_lookup = await tools_by_name["course_lookup"].ainvoke({"topic": "MCP"})
    direct_sum = await tools_by_name["add_numbers"].ainvoke({"a": 7, "b": 5})

    # 后两项需要显式的 session，所以用 async with
    # 进入代码块时建立会话，离开时关闭
    async with client.session("course") as session:
        # 两个 await 按顺序执行。这里 "course" 是 Server 名，"MCP" 是传给函数的主题
        resources = await load_mcp_resources(session, uris="course://MCP")
        prompt_messages = await load_mcp_prompt(
            session,
            "explain_topic",
            arguments={"topic": "MCP"},
        )

    model = ToolCallingFakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "course_lookup",
                        "args": {"topic": "LangGraph"},
                        "id": "mcp-course-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Agent 已经消费 MCP Server 返回的 LangGraph 摘要。"),
        ]
    )
    agent = create_agent(model=model, tools=tools)
    agent_result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "查询 LangGraph 课程摘要"}]}
    )
    tool_messages = [
        str(message.content)
        for message in agent_result["messages"]
        if isinstance(message, ToolMessage)
    ]

    result = {
        "transport": "stdio",
        "server_process": str(SERVER_PATH),
        "discovered_tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "args_schema": _schema_dict(tool.args_schema),
            }
            for tool in tools
        ],
        "direct_calls": {
            "course_lookup": {
                "raw": direct_lookup,
                "text": _content_text(direct_lookup),
            },
            "add_numbers": {
                "raw": direct_sum,
                "text": _content_text(direct_sum),
            },
        },
        "agent_tool_messages": tool_messages,
        "resource": {
            "mimetype": resources[0].mimetype,
            "text": resources[0].as_string(),
        },
        "prompt_messages": [
            {"type": message.type, "content": str(message.content)}
            for message in prompt_messages
        ],
        "boundaries": [
            "MCP Server 声明并执行工具；LangChain Adapter 把它们转换为 BaseTool。",
            "stdio 只是一种 transport，不等于允许 Agent 访问全部文件或命令。",
            "工具权限、超时、认证和审计仍由 Server、Client interceptor 与运行环境负责。",
        ],
    }
    assert "LangGraph" in tool_messages[0]
    assert _content_text(direct_sum) == "12"
    assert resources[0].as_string().startswith("# MCP")
    assert "MCP" in str(prompt_messages[0].content)
    return result


# 启动命令：
#   .venv/bin/python 2_langchain/L15_MCP_Integration.py
# 参数枚举：无；示例固定使用本地 stdio MCP Server。
def main() -> int:
    print(json.dumps(asyncio.run(run_demo()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
