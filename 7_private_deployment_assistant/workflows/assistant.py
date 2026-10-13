"""后续流程：环境上下文 → 检索 → 证据判断 → 追问或回答 → 引用检查。"""

from contracts import AssistantRequest


class WorkflowNotReady(RuntimeError):
    pass


class AssistantWorkflow:
    def invoke(self, request: AssistantRequest) -> dict:
        # 当前只保留调用合同；不创建 Agent，也不调用 LangChain、LangGraph 或模型。
        raise WorkflowNotReady("智能问答尚未接入，当前不会检索文档或调用模型。")
