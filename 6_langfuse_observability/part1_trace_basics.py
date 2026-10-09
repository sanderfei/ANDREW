"""Part 1：Trace、嵌套 Span、输入输出与异常；没有模型调用。

- Trace 表示一次完整调用；Span 是其中一个处理步骤，也是 observation 的一种类型。
- 本例根 Span 为 part1-text-workflow，两个子 Span 为 normalize 和 format-report；
  三者共享 trace_id，各自有独立的 Span ID，子 Span 通过父 Span ID 关联根 Span。
- start_as_current_observation 在进入 with 时开始记录并设置当前 Span，退出时结束；
  嵌套的 with 自动建立父子关系，两个子 Span 在本例中顺序执行。
- input 记录输入，update(output=...) 记录输出；这些操作不执行文本处理逻辑。
- 空文本触发 ValueError，平台模式中异常经过的 normalize 和根 Span 会记录错误。
- open_client 管理客户端生命周期；平台模式退出时 flush 等待发送，shutdown 释放资源。
- offline 只处理文本，trace_id 为 None；langfuse 上报记录，返回 Trace ID 不等于入库证明。
"""

from __future__ import annotations

import argparse
import json

from _runtime import add_mode_argument, open_client


def normalize(text: str) -> str:
    result = text.strip()
    if not result:
        raise ValueError("文本不能为空：这是供观察错误 Span 的演示异常。")
    return result


# 进入 open_client，创建客户端并检查认证
#     ↓
# 开始根 Span
#     ↓
# normalize 子 Span 开始 → 处理 → 记录输出 → 结束
#     ↓
# format-report 子 Span 开始 → 处理 → 记录输出 → 结束
#     ↓
# 记录根输出，获取 Trace ID
#     ↓
# 根 Span 结束
#     ↓
# 准备返回字典
#     ↓
# 退出 open_client，执行 flush → shutdown
#     ↓
# 调用方拿到字典
def run_demo(mode: str = "offline", text: str = "  Langfuse 学习  ") -> dict:
    with open_client(mode) as client:
        if client is None:
            normalized = normalize(text)
            return {"mode": mode, "result": f"已整理：{normalized}", "trace_id": None}

        # 最外层 observation 创建一条 Trace；上下文中的 observation 是它的子 Span。
        # root 的类型是 SDK 的 LangfuseSpan，代表整个处理过程。
        # 在独立运行这个脚本、没有上层活动 Span 时，它作为根 Span 开始一条新 Trace。进入 with 后，根 Span 成为当前活动 Span，下面嵌套创建的 Span 可以自动关联到它。
        with client.start_as_current_observation(
            name="part1-text-workflow",
            as_type="span",
            input={"text": text},
            metadata={"lesson": "part1", "model_used": False},
        ) as root:
            with client.start_as_current_observation(
                name="normalize", input=text  # 开始 normalize Span，记录 input
            ) as span:
                normalized = normalize(text)
                span.update(output=normalized)  # 记录 output
            # 退出 with，结束 normalize Span
            with client.start_as_current_observation(
                name="format-report", input=normalized
            ) as span:
                result = f"已整理：{normalized}"
                span.update(output=result)
            root.update(output={"result": result})
            trace_id = (
                client.get_current_trace_id()
            )  # 获取当前活动 Span 所属的 Trace ID
        # 三个 Span 共享同一个 Trace ID，各自有独立的 Span ID。
        return {"mode": mode, "result": result, "trace_id": trace_id}


# 启动命令：.venv/bin/python 6_langfuse_observability/part1_trace_basics.py
# 平台模式：同上追加 --mode langfuse；观察错误：追加 --text ""
# 参数枚举：--mode offline（默认）/ langfuse；--text 任意文本（默认带两端空格的教学文本）。
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_mode_argument(parser)
    parser.add_argument("--text", default="  Langfuse 学习  ")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_demo(args.mode, args.text), ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
