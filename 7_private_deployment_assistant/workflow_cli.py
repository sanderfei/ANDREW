"""问答、会话恢复、功能验证、入库任务与成本统计的命令行入口。"""

import argparse
from dataclasses import replace
from hashlib import sha256
import json
from uuid import uuid4

from config import load_assistant_settings
from contracts import AssistantRequest, ClusterContext, VerificationRequest
from services.business_runtime import SessionBusyError
from workflows.assistant import AssistantWorkflow, WorkflowExecutionError


# 启动：.venv/bin/python 7_private_deployment_assistant/workflow_cli.py <子命令>
# graph：输出实际 Mermaid 图；sessions：读取服务端会话。
# ask "问题" [--thread-id 会话ID] [--request-id 请求ID]：同 thread 续聊，同请求ID重试。
# ask 环境参数：--k8s 1.23.10/1.32.8、--os Ubuntu/CentOS、--install-mode online/offline。
# 顶级 --mode framework/glm 放在子命令前；glm 会访问真实模型和向量库。
# metrics [--thread-id ID]：Token/费用统计；jobs [--thread-id ID]：持久入库任务。
# langfuse-status [--check]：查看上报配置；--check 才连接平台检查项目认证。
# verify ID --root-cause "明确根因" --step "实际步骤" [--step "另一步"]
#   --evidence "原故障功能复测的具体证据" --confirmed：确认并归档，不自动入库。
# index-pending [--limit 5]：显式执行待入库/失败任务，会调用本地 Embedding 和向量库。
# 示例：.venv/bin/python 7_private_deployment_assistant/workflow_cli.py ask "离线安装失败" --thread-id demo-7
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("framework", "glm"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("graph")
    ask = commands.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--k8s", choices=("1.23.10", "1.32.8"))
    ask.add_argument("--os", choices=("Ubuntu", "CentOS"))
    ask.add_argument("--install-mode", choices=("online", "offline"))
    ask.add_argument("--thread-id", help="使用已有会话续聊；省略时新建")
    ask.add_argument("--request-id", help="重试同一次失败请求时使用相同 ID")
    commands.add_parser("sessions")
    langfuse_status = commands.add_parser("langfuse-status", help="查看 Langfuse 上报状态")
    langfuse_status.add_argument("--check", action="store_true", help="连接平台检查项目认证")
    for command in ("metrics", "jobs"):
        child = commands.add_parser(command)
        child.add_argument("--thread-id")
    pending = commands.add_parser("index-pending", help="显式执行向量入库任务")
    pending.add_argument("--limit", type=int, default=5)
    verify = commands.add_parser("verify", help="提交已完成的实际处理和功能复测")
    verify.add_argument("thread_id")
    verify.add_argument("--root-cause", required=True)
    verify.add_argument("--step", action="append", required=True)
    verify.add_argument("--evidence", required=True)
    verify.add_argument("--confirmed", action="store_true", required=True)
    args = parser.parse_args(argv)
    workflow = None
    request = None
    try:
        settings = load_assistant_settings()
        if args.mode:
            settings = replace(settings, mode=args.mode)
        workflow = AssistantWorkflow(settings)
        if args.command == "graph":
            print(workflow.mermaid())
            return 0
        if args.command == "sessions":
            result = {"items": workflow.sessions()}
        elif args.command == "metrics":
            result = workflow.business.observability.metrics(args.thread_id)
        elif args.command == "langfuse-status":
            result = workflow.business.observability.status(check_connection=args.check)
        elif args.command == "jobs":
            result = {"items": workflow.business.knowledge.list_jobs(args.thread_id)}
        elif args.command == "index-pending":
            result = {"items": workflow.business.knowledge.run_index_jobs(limit=args.limit)}
        elif args.command == "verify":
            verification = VerificationRequest(
                thread_id=args.thread_id, confirmed=args.confirmed,
                root_cause=args.root_cause, resolution_steps=args.step, evidence=args.evidence,
            )
            fingerprint = sha256(json.dumps(verification.model_dump(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            request = AssistantRequest(
                thread_id=args.thread_id, request_id=f"verify-{fingerprint}",
                question="用户提交实际处理步骤与原故障功能复测结果。",
                action="verify_resolution", verification=verification,
            )
            result = {**workflow.invoke(request).model_dump(), "request_id": request.request_id}
        else:
            request = AssistantRequest(
                thread_id=args.thread_id or f"cli-{uuid4().hex}",
                request_id=args.request_id or uuid4().hex, question=args.question,
                context=ClusterContext(kubernetes_version=args.k8s, operating_system=args.os, install_mode=args.install_mode),
            )
            result = {**workflow.invoke(request).model_dump(), "request_id": request.request_id}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "langfuse-status" and args.check and result.get("connection_verified") is not True:
            return 1
        if args.command == "index-pending" and any(item["status"] == "failed" for item in result["items"]):
            return 1
        return 0
    except (ValueError, OSError, WorkflowExecutionError, SessionBusyError) as exc:
        result = {"error": str(exc)}
        if request is not None:
            result.update(thread_id=request.thread_id, request_id=request.request_id)
        print(json.dumps(result, ensure_ascii=False))
        return 1
    finally:
        if workflow is not None:
            workflow.close()


if __name__ == "__main__":
    raise SystemExit(main())
