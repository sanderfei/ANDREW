"""供可直接运行的学习脚本共享的最小环境变量加载器。

它刻意只依赖标准库：旧课件即使不安装额外配置包，也可以从项目根目录的
`.env`（不提交）或已导出的系统环境读取凭据。这里不保存任何真实凭据。
"""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
_loaded = False


def _load_project_dotenv() -> None:
    """一次性读取根目录 `.env`，且永不覆盖已导出的环境变量。"""

    global _loaded
    if _loaded:
        return
    _loaded = True

    dotenv_path = PROJECT_ROOT / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def env(name: str, default: str = "") -> str:
    """返回环境变量；首次调用时会尝试读取根目录 `.env`。"""

    _load_project_dotenv()
    return os.getenv(name, default)


def require_env(name: str) -> str:
    """在真正需要联网调用时给出可操作的缺失凭据错误。"""

    value = env(name)
    if value:
        return value
    raise RuntimeError(
        f"缺少 {name}。请复制 .env.example 为 .env 并填写，"
        "或先把该变量导出到当前 shell。"
    )
