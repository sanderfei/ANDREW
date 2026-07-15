"""让 `2_langchain` 的单文件课件直接复用根目录环境变量工具。"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from learning_runtime import env, require_env

__all__ = ["env", "require_env"]
