"""LangGraph 组织追问、检索、证据判断和 LangChain 模型调用。"""

import json
import logging
import re
from collections.abc import Callable
from threading import Lock
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Overwrite

from config import AssistantSettings, Settings, load_assistant_settings
from contracts import AssistantRequest, AssistantResponse
from services.chat_model import build_chat_model
from services.business_runtime import BusinessRuntime, _safe
from services.ingestion import redact
from services.remote_diagnostics import CHECK_CATALOG, RemoteDiagnosticError
from services.vector_service import VectorService
from workflows.prompts import ANALYZE_INPUT, ASSESS_EVIDENCE, ANSWER_FROM_CASES, DIAGNOSE
from workflows.state import AnswerDraft, DiagnosisDraft, EvidenceAssessment, InputAnalysis, WorkflowState


class WorkflowExecutionError(RuntimeError):
    """区分依赖/输出错误与证据不足；不向客户端暴露原始异常。"""


def _update(node: str, **values) -> dict:
    return {"steps": [node], **values}


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _history_messages(history: list[dict]) -> list:
    return [(HumanMessage if item["role"] == "user" else AIMessage)(content=item["content"]) for item in history]


def _citation_ids(text: str) -> set[int]:
    # 命令中的 items[0] 是数组下标；代码块和行内代码不按来源引用扫描。
    prose = re.sub(r"```.*?```|`[^`\n]*`", "", text, flags=re.S)
    return {int(value) for value in re.findall(r"\[(\d+)\]", prose)}


class AssistantWorkflow:
    def __init__(self, settings: AssistantSettings | None = None, *, model=None,
                 retriever_factory: Callable | None = None, business: BusinessRuntime | None = None):
        self.settings = settings or load_assistant_settings()
        self._model = model
        self._model_lock = Lock()
        self._retriever_factory = retriever_factory or VectorService
        self.business = business or BusinessRuntime(retriever_factory=retriever_factory)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(WorkflowState)
        for name in (
            "prepare_input", "check_information", "ask_for_information", "retrieve_documents",
            "framework_pending", "assess_evidence", "answer_from_cases", "diagnose",
            "request_evidence", "validate_citations", "await_verification", "collect_remote_evidence",
            "verify_resolution", "publish_case",
        ):
            builder.add_node(name, getattr(self, f"_{name}"))
        builder.add_conditional_edges(START, lambda state: state.get("action", "message"),
                                      {"message": "prepare_input", "verify_resolution": "verify_resolution"})
        builder.add_edge("prepare_input", "check_information")
        builder.add_conditional_edges("check_information", lambda state: bool(state["missing_information"]),
                                      {True: "ask_for_information", False: "retrieve_documents"})
        builder.add_edge("ask_for_information", END)
        builder.add_conditional_edges("retrieve_documents", lambda state: self.settings.mode,
                                      {"framework": "framework_pending", "glm": "assess_evidence"})
        builder.add_edge("framework_pending", END)
        builder.add_conditional_edges("assess_evidence", lambda state: state["assessment"]["sufficient"],
                                      {True: "answer_from_cases", False: "diagnose"})
        builder.add_edge("answer_from_cases", "validate_citations")
        builder.add_conditional_edges("diagnose", self._diagnosis_route,
                                      {"solution": "validate_citations", "remote": "collect_remote_evidence", "evidence": "request_evidence"})
        builder.add_edge("collect_remote_evidence", "diagnose")
        builder.add_edge("request_evidence", END)
        builder.add_edge("validate_citations", "await_verification")
        builder.add_edge("await_verification", END)
        builder.add_conditional_edges("verify_resolution", lambda state: state["verification"]["verified"],
                                      {True: "publish_case", False: END})
        builder.add_edge("publish_case", END)
        return builder.compile(checkpointer=self.business.checkpointer)

    @staticmethod
    def _model_evidence(state: WorkflowState) -> str:
        return _json([{**item, "stdout": str(item.get("stdout", ""))[:6000], "stderr": str(item.get("stderr", ""))[:2000]}
                      for item in state.get("evidence", [])[-6:]])

    def _diagnosis_route(self, state: WorkflowState) -> str:
        if state["draft"].get("proposed_solution"):
            return "solution"
        checks = state["draft"].get("requested_checks", [])
        unseen = [check for check in checks if _json(check) not in state.get("executed_checks", [])]
        if (state.get("connection_id") and unseen and state.get("remote_rounds", 0) < self.settings.max_remote_rounds):
            return "remote"
        return "evidence"

    def _structured(self, prompt, schema, values: dict, config: RunnableConfig):
        try:
            with self._model_lock:
                if self._model is None:
                    self._model = build_chat_model(self.settings)
        except Exception:
            raise WorkflowExecutionError("聊天模型初始化失败，请检查 ZHIPU_API_KEY、接口地址与模型配置。") from None
        if self._model is None:
            raise WorkflowExecutionError("当前框架模式未启用聊天模型。")
        parser = PydanticOutputParser(pydantic_object=schema)
        chain = prompt.partial(format_instructions=parser.get_format_instructions()) | self._model | parser
        try:
            return chain.invoke(values, config=config)
        except Exception:
            raise WorkflowExecutionError("模型调用或结构化输出解析失败，请检查模型配置与服务。") from None

    def _prepare_input(self, state: WorkflowState, config: RunnableConfig):
        if self.settings.mode == "glm":
            analysis = self._structured(ANALYZE_INPUT, InputAnalysis, {
                "question": state["question"], "context": _json(state["context"]),
                "history": _history_messages(state["history"]),
                "evidence": self._model_evidence(state),
            }, config)
        else:
            # 框架模式只做规则演示，不伪装成模型分析或现场事实。
            context = {}
            conflicts = []
            texts = [item["content"] for item in state["history"] if item["role"] == "user"] + [state["question"]]
            for text in texts:
                versions = re.findall(r"(?<![\d.])1\.(?:23\.10|32\.8)(?![\d.])", text)
                if versions:
                    context["kubernetes_version"] = versions[-1]
                for pattern, field, value in (
                    (r"ubuntu", "operating_system", "Ubuntu"), (r"centos", "operating_system", "CentOS"),
                    (r"离线|\boffline\b", "install_mode", "offline"), (r"在线|\bonline\b", "install_mode", "online"),
                ):
                    if re.search(pattern, text, re.I):
                        context[field] = value
            for field in ("kubernetes_version", "operating_system", "install_mode"):
                confirmed = state.get("explicit_context", {}).get(field)
                if confirmed is not None:
                    if field in context and context[field] != confirmed:
                        conflicts.append(f"环境摘要与用户描述中的 {field} 不一致，请确认实际环境。")
                    context[field] = confirmed
            is_fault = bool(re.search(r"失败|报错|异常|无法|故障|error|exception|backoff|timeout", state["question"], re.I))
            labels = {"kubernetes_version": "Kubernetes 版本", "operating_system": "操作系统", "install_mode": "在线或离线部署方式"}
            missing = [f"请补充{label}。" for key, label in labels.items() if is_fault and not context.get(key)]
            missing.extend(conflicts)
            analysis = InputAnalysis(summary=state["question"][:1500], query=state["question"][:2000],
                                     environment=context, missing_information=missing, is_fault=is_fault)
        extracted = analysis.environment.model_dump(exclude_none=True)
        missing = list(analysis.missing_information)
        for field, value in extracted.items():
            confirmed = state.get("explicit_context", {}).get(field)
            if confirmed is not None and confirmed != value:
                missing.append(f"环境摘要与当前描述中的 {field} 不一致，请确认实际环境。")
        context = {**state["context"], **extracted, **state.get("explicit_context", {})}
        return _update("prepare_input", analysis=analysis.model_dump(), context=context, query=analysis.query,
                       missing_information=missing)

    def _check_information(self, state: WorkflowState):
        missing = list(state["missing_information"])
        version, system = state["context"].get("kubernetes_version"), state["context"].get("operating_system")
        if version and system and system not in Settings().support_matrix.get(version, []):
            missing.append("当前版本和系统组合不在项目支持范围内，请确认实际版本与操作系统。")
        return _update("check_information", missing_information=missing)

    def _ask_for_information(self, state: WorkflowState):
        lines = "\n".join(f"{number}. {question}" for number, question in enumerate(state["missing_information"], 1))
        prefix = "框架模式按规则识别了当前描述。" if self.settings.mode == "framework" else "继续判断前，需要补充以下信息："
        return _update("ask_for_information", workflow_status="needs_information", answer=f"{prefix}\n{lines}\n请在当前会话继续补充。")

    def _retrieve_documents(self, state: WorkflowState):
        if self.settings.mode == "framework":
            return _update("retrieve_documents", retrieval_status="not_run", documents=[])
        filters = {key: state["context"][field] for key, field in (
            ("kubernetes_versions", "kubernetes_version"), ("operating_systems", "operating_system"),
            ("install_modes", "install_mode"),
        ) if state["context"].get(field)}
        service = None
        try:
            service = self._retriever_factory()
            result = service.search(state["query"], self.settings.top_k, filters)
            documents = [{"source_id": number, "chunk_id": item["chunk_id"], "content": redact(item["content"]),
                          "metadata": item["metadata"], "score": item["score"]}
                         for number, item in enumerate(result["items"], 1)]
        except Exception:
            raise WorkflowExecutionError("资料检索失败，请检查数据库、索引和本地 Embedding 模型；这不代表没有相关案例。") from None
        finally:
            if service is not None:
                try:
                    service.close()
                except Exception:
                    logging.getLogger(__name__).warning("检索资源释放失败。")
        return _update("retrieve_documents", documents=documents, retrieval_status="matched" if documents else "no_matches")

    def _framework_pending(self, state: WorkflowState):
        environment = _json({key: value for key, value in state["context"].items() if value is not None})
        return _update("framework_pending", workflow_status="framework_ready", answer=(
            f"LangGraph 工作流框架已运行。\n当前问题：{state['query']}\n已知环境：{environment}\n\n"
            "下一步将按环境检索文档，再判断是复用案例还是进入 GLM 诊断。\n"
            "当前为 framework 模式：未执行向量检索、未调用 GLM，也没有连接主机或生成故障诊断结论。\n"
            "配置 assistant.mode=glm 后启用检索与模型分析。远程授权、功能验证、案例归档和执行记录已有独立业务入口。"))

    def _assess_evidence(self, state: WorkflowState, config: RunnableConfig):
        if not state["documents"]:
            assessment = EvidenceAssessment(sufficient=False, reason="本次检索没有返回片段，需要结合用户描述继续诊断。")
        else:
            assessment = self._structured(ASSESS_EVIDENCE, EvidenceAssessment, {
                "query": state["query"], "context": _json(state["context"]), "documents": _json(state["documents"]),
            }, config)
            valid_ids = {item["source_id"] for item in state["documents"]}
            if not set(assessment.source_ids) <= valid_ids or (assessment.sufficient and not assessment.source_ids):
                raise WorkflowExecutionError("证据判断引用了本次检索范围以外的来源。")
            selected = [item for item in state["documents"] if item["source_id"] in assessment.source_ids]
            if assessment.sufficient and all(item["metadata"].get("verification_status") == "unverified" for item in selected):
                assessment = EvidenceAssessment(sufficient=False, reason="当前依据仅包含待验证案例，需继续取证。", source_ids=assessment.source_ids)
        return _update("assess_evidence", assessment=assessment.model_dump())

    def _answer_from_cases(self, state: WorkflowState, config: RunnableConfig):
        draft = self._structured(ANSWER_FROM_CASES, AnswerDraft, {
            "query": state["query"], "context": _json(state["context"]),
            "assessment": _json(state["assessment"]), "documents": _json(state["documents"]),
        }, config)
        return _update("answer_from_cases", draft=draft.model_dump())

    def _diagnose(self, state: WorkflowState, config: RunnableConfig):
        draft = self._structured(DIAGNOSE, DiagnosisDraft, {
            "query": state["query"], "question": state["question"], "context": _json(state["context"]),
            "assessment": _json(state["assessment"]), "documents": _json(state["documents"]),
            "history": _history_messages(state["history"]),
            "evidence": self._model_evidence(state), "tools": _json(CHECK_CATALOG),
        }, config)
        return _update("diagnose", draft=draft.model_dump())

    def _request_evidence(self, state: WorkflowState):
        draft = state["draft"]
        parts = ["待验证分析", draft["analysis"]]
        for label, key in (("候选原因", "hypotheses"), ("下一步检查", "next_checks"), ("需要补充", "questions")):
            if draft[key]:
                parts.append(label + "：\n" + "\n".join(f"- {item}" for item in draft[key]))
        status = "awaiting_evidence"
        if draft["needs_remote_evidence"] or draft.get("requested_checks"):
            if not state.get("connection_id"):
                status = "awaiting_remote_authorization"
                parts.append("可以通过‘授权只读诊断’提供本会话连接。账号密码只交给连接执行器，不要粘贴到聊天中。")
            else:
                parts.append("本轮已完成可用的自动检查，请补充上述检查结果或新的现场线索后继续。")
        return _update("request_evidence", answer="\n\n".join(parts), workflow_status=status)

    def _collect_remote_evidence(self, state: WorkflowState):
        checks = [item for item in state["draft"]["requested_checks"] if _json(item) not in state.get("executed_checks", [])]
        try:
            results = self.business.remote.collect(state["connection_id"], state["thread_id"], checks)
        except RemoteDiagnosticError as exc:
            raise WorkflowExecutionError(str(exc)) from None
        return _update("collect_remote_evidence", evidence=(state.get("evidence", []) + results)[-40:],
                       executed_checks=state.get("executed_checks", []) + [_json(item) for item in checks],
                       remote_rounds=state.get("remote_rounds", 0) + 1)

    def _validate_citations(self, state: WorkflowState):
        draft = state["draft"]
        if "proposed_solution" in draft:
            text = draft["analysis"] + "\n\n建议处理：\n" + draft["proposed_solution"]
            if _citation_ids(text):
                raise WorkflowExecutionError("通用诊断生成了未关联真实来源的引用，请重新分析。")
            sources = []
        else:
            text = draft["answer"]
            selected = set(draft["source_ids"])
            available = {item["source_id"]: item for item in state["documents"]}
            inline = _citation_ids(text)
            if not selected or not selected <= available.keys() or not inline or inline != selected:
                raise WorkflowExecutionError("回答中的引用与本次检索来源不一致，未输出该方案。")
            sources = [{"source_id": key, "chunk_id": available[key]["chunk_id"],
                        "source": available[key]["metadata"].get("source", ""),
                        "location": available[key]["metadata"].get("location", ""),
                        "verification_status": available[key]["metadata"].get("verification_status", "unverified")}
                       for key in sorted(selected)]
            text += "\n\n资料来源：\n" + "\n".join(f"[{item['source_id']}] {item['source']} · {item['location']}" for item in sources)
        return _update("validate_citations", answer=text, sources=sources)

    def _await_verification(self, state: WorkflowState):
        checks = state["draft"].get("verification_steps", [])
        text = "建议方案，尚未完成现场验证。\n\n" + state["answer"]
        if checks:
            text += "\n\n功能验证：\n" + "\n".join(f"- {item}" for item in checks)
        text += "\n\n执行处理后，请通过‘确认解决’提交实际步骤与原故障功能复测结果，验证通过后自动归档并排队入库。"
        draft = state["draft"]
        proposal = {"question": state["query"], "summary": state["analysis"]["summary"],
                    "answer": draft.get("proposed_solution") or draft.get("answer"), "context": state["context"],
                    "root_cause": draft.get("root_cause"), "verification_steps": checks, "sources": state["sources"]}
        return _update("await_verification", workflow_status="awaiting_verification", answer=text, proposal=proposal)

    def _verify_resolution(self, state: WorkflowState):
        if not state.get("proposal"):
            # 用户自行完成处理也可归档，但必须提交明确根因、实际步骤与复测证据。
            if not state.get("question"):
                raise WorkflowExecutionError("请先创建问题会话，再提交解决记录。")
            proposal = {"question": state["question"], "summary": state.get("analysis", {}).get("summary", state["question"]),
                        "answer": "\n".join(state["verification_request"]["resolution_steps"]),
                        "context": state.get("context", {}), "sources": []}
        else:
            proposal = state["proposal"]
        verification = dict(state["verification_request"])
        if verification["method"] == "remote_check":
            verification["checks"] = state.get("evidence", [])
        result = self.business.knowledge.verify(state["thread_id"], proposal, verification)
        return _update("verify_resolution", verification=result, proposal=proposal, workflow_status="awaiting_verification",
                       answer="功能复测尚未确认通过，请继续提供复测结果。")

    def _publish_case(self, state: WorkflowState):
        request = state["verification_request"]
        record = {**state["proposal"], "verified": True, "verification": state["verification"],
                  "root_cause": request["root_cause"], "steps": request["resolution_steps"],
                  "answer": "\n".join(request["resolution_steps"]),
                  "root_cause_evidence": "用户确认的根因：" + request["root_cause"] + "\n功能复测：" + request["evidence"],
                  "trace_id": state.get("trace_id")}
        try:
            case = self.business.knowledge.publish(state["thread_id"], record)
        except (ValueError, OSError):
            raise WorkflowExecutionError("复测记录已保留在检查点，但案例归档失败，请检查环境与本地目录后重试。") from None
        self.business.wake_indexer()
        return _update("publish_case", case=case, workflow_status="resolved", answer=(
            f"已记录本次故障恢复及功能复测证据。\n案例：{case['case_id']}\n本地文档：{case['path']}\n"
            "向量入库已建立持久任务，成功前仍显示待入库；失败会保留并重试。"))

    def _save_result(self, request, request_id, history, result, trace_id):
        response = AssistantResponse(thread_id=request.thread_id, answer=result["answer"],
            workflow_status=result["workflow_status"], steps=result["steps"], sources=result.get("sources", []),
            retrieval_status=result.get("retrieval_status", "not_run"), trace_id=trace_id,
            case=result.get("case"), proposal=result.get("proposal") or None)
        messages = history + [{"role": "user", "content": redact(request.question)}, {"role": "assistant", "content": response.answer}]
        self.business.sessions.save(request.thread_id, {
            "messages": messages[-200:], "context": result.get("context", {}), "workflow_status": response.workflow_status,
            "proposal": result.get("proposal", {}), "evidence": result.get("evidence", []), "last_response": response.model_dump(),
        }, request_id=request_id, response=response.model_dump())
        return response

    def invoke(self, request: AssistantRequest, config: RunnableConfig | None = None) -> AssistantResponse:
        with self.business.sessions.lock(request.thread_id):
            cached = self.business.sessions.cached(request.thread_id, request.request_id)
            if cached:
                return AssistantResponse.model_validate(cached)
            saved = self.business.sessions.get(request.thread_id) or {}
            history = saved.get("messages", []) or [{"role": item.role, "content": redact(item.content)} for item in request.history]
            context = {**saved.get("context", {}), **request.context.model_dump(exclude_none=True)}
            context = {key: redact(value) if isinstance(value, str) else value for key, value in context.items()}
            options = {**(config or {}), "configurable": {**(config or {}).get("configurable", {}), "thread_id": request.thread_id}}
            snapshot = self.graph.get_state(options)
            # 图已完成但响应缓存尚未落盘的崩溃窗口：仅补存结果，不重跑模型和归档。
            if (request.request_id and snapshot.values.get("request_id") == request.request_id
                    and not snapshot.next and snapshot.values.get("answer") and snapshot.values.get("workflow_status")):
                response = self._save_result(request, request.request_id, history, snapshot.values, snapshot.values.get("trace_id"))
                self.business.observability.finalize_recovered(response.trace_id, response.answer, response.workflow_status)
                return response
            if request.action == "verify_resolution" and (request.verification is None or request.verification.thread_id != request.thread_id):
                raise WorkflowExecutionError("解决验证请求缺少信息，或不属于当前会话。")
            if request.action == "verify_resolution" and not snapshot.values:
                raise WorkflowExecutionError("找不到需要验证的问题会话。")
            request_id = request.request_id or uuid4().hex
            initial: WorkflowState = {
                "thread_id": request.thread_id, "request_id": request_id, "action": request.action,
                "question": redact(request.question), "history": history[-40:], "context": context,
                "explicit_context": _safe(request.context.model_dump(exclude_none=True)),
                "retrieval_status": "not_run", "documents": [], "sources": [], "steps": Overwrite([]),
                "analysis": {}, "assessment": {}, "draft": {}, "missing_information": [], "answer": "",
                "evidence": saved.get("evidence", []), "connection_id": request.connection_id,
                "executed_checks": [], "remote_rounds": 0, "proposal": {}, "case": None,
            }
            if request.action == "verify_resolution":
                initial = {"action": request.action, "request_id": request_id, "steps": Overwrite([]),
                           "verification_request": _safe(request.verification.model_dump()),
                           "evidence": saved.get("evidence", snapshot.values.get("evidence", []))}
            self.business.sessions.save(request.thread_id, {**saved, "messages": history,
                "context": context, "pending_request": {"request_id": request_id, "question": redact(request.question),
                    "action": request.action,
                    "verification": _safe(request.verification.model_dump()) if request.verification else None}})
            with self.business.observability.trace(request.thread_id, redact(request.question), metadata={
                "action": request.action, "mode": self.settings.mode, "request_id": request_id,
                "previous_trace_id": snapshot.values.get("trace_id") if snapshot.values.get("request_id") == request_id else None,
            }) as trace:
                initial["trace_id"] = trace.trace_id
                options["callbacks"] = [*(options.get("callbacks") or []), *trace.callbacks]
                options.setdefault("run_name", "deployment-assistant-workflow")
                options["metadata"] = {**(options.get("metadata") or {}),
                    "langfuse_session_id": request.thread_id,
                    "local_trace_id": trace.trace_id, "action": request.action,
                    "mode": self.settings.mode}
                options["recursion_limit"] = 30
                try:
                    resume = snapshot.values.get("request_id") == request_id and bool(snapshot.next)
                    if resume and request.connection_id and request.connection_id != snapshot.values.get("connection_id"):
                        # 新授权连接使用一轮新的图输入，避免恢复时反复调用已失效的旧连接。
                        resume = False
                    result = self.graph.invoke(None if resume else initial, config=options)
                    response = self._save_result(request, request_id, history, result, trace.trace_id)
                    trace.update(output=response.answer, status=response.workflow_status,
                                 metadata={"retrieval_status": response.retrieval_status, "steps": response.steps})
                    return response
                except WorkflowExecutionError:
                    trace.update(status="error")
                    raise
                except Exception:
                    trace.update(status="error")
                    raise WorkflowExecutionError("工作流执行失败，检查点已保留；请检查配置、模型或业务服务后重试。") from None

    def collect_evidence(self, thread_id: str, connection_id: str, checks: list[dict]) -> dict:
        with self.business.sessions.lock(thread_id):
            saved = self.business.sessions.get(thread_id) or {"messages": [], "context": {}}
            with self.business.observability.trace(thread_id, "用户授权的只读现场取证", metadata={"action": "remote_diagnostics"}) as trace:
                with trace.span("remote_diagnostics", input={"checks": checks}) as span:
                    results = self.business.remote.collect(connection_id, thread_id, checks)
                    span.update(output=results)
                saved["evidence"] = (saved.get("evidence", []) + results)[-40:]
                self.business.sessions.save(thread_id, saved)
                trace.update(output={"checks": len(results)}, status="evidence_collected")
                return {"thread_id": thread_id, "evidence": results, "trace_id": trace.trace_id}

    def sessions(self) -> list[dict]:
        result = self.business.sessions.list()
        for session in result:
            pending = session.get("pending_request")
            if pending:
                session["messages"] = session.get("messages", []) + [
                    {"id": pending["request_id"], "role": "user", "content": pending["question"]},
                    {"role": "notice", "content": "上次请求未完成或仍在执行，可以等待后重试同一问题。"},
                ]
        return result

    def close(self):
        self.business.close()

    def mermaid(self) -> str:
        return self.graph.get_graph().draw_mermaid()
