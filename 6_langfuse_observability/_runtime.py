"""本目录共享的最小配置：默认离线，仅显式启用时连接 Langfuse。"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from learning_runtime import env, require_env


def add_mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        choices=("offline", "langfuse"),
        default="offline",
        help="offline 不上报；langfuse 向配置的平台发送本课合成数据。",
    )


@contextmanager
def open_client(mode: str):
    """只负责生命周期；各课直接展示 Langfuse 的原生 API。"""
    if mode not in {"offline", "langfuse"}:
        raise ValueError("mode 必须为 offline 或 langfuse。")
    # 根 .env 可能为旧课件启用了 LangSmith，本目录仅使用所选择的 Langfuse 模式。
    # 只修改当前教程进程，不改用户的 .env 文件。
    env("LANGFUSE_BASE_URL")
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    if mode == "offline":
        yield None
        return

    public_key = require_env("LANGFUSE_PUBLIC_KEY")
    secret_key = require_env("LANGFUSE_SECRET_KEY")
    base_url = env("LANGFUSE_BASE_URL", "http://localhost:3000").rstrip("/")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("LANGFUSE_BASE_URL 必须是无内嵌凭据的 HTTP(S) 平台地址。")
    try:
        from langfuse import Langfuse
    except ImportError as exc:
        raise RuntimeError(
            "请先安装 6_langfuse_observability/requirements.txt。"
        ) from exc

    client = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=base_url,
        tracing_enabled=True,  # 启用追踪
        environment="andrew-tutorial",  # 给记录添加环境标识
        timeout=5,
    )
    try:
        # 仅教学 CLI 在启动时检查，避免错误地址/Key 被误认为上报成功。
        try:
            authenticated = client.auth_check()
        except Exception:
            raise RuntimeError(
                "Langfuse 连接或认证失败，请检查服务地址及项目 API Keys。"
            ) from None
        if not authenticated:
            raise RuntimeError("Langfuse 项目认证失败。")
        yield client
    finally:
        # SDK 使用后台批量上报；短生命周期脚本退出前必须等待发送并释放线程。
        client.flush()  # 强制刷新缓冲区里的 Span、Score 等待发送数据，并等待刷新完成
        client.shutdown()  # 刷新剩余数据，关闭后台发送线程等资源


# open_client 调用逻辑
# 进入 with
#   → 执行 open_client 中 yield 之前的代码
#   → yield 的值赋给 client
#   → 暂停 open_client，执行调用方的 with 块
# 退出 with
#   → 恢复 open_client，执行退出逻辑

# yield 是交接位置：把客户端交给调用方使用，并暂停函数；调用方退出 with 后，再回来执行清理。