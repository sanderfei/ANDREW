"use strict";

const STORAGE_KEY = "private-deployment-assistant:v1";
const titles = {workspace: "运维工作台", documents: "知识文档", evaluations: "评测实验"};
let state = {sessions: [], activeId: null, serverUrl: ""};
let pending = null;
let toastTimer;
let restoringSessions = false;
let remoteBusy = false;
// 连接句柄仅保留在页面内存；密码从不写入 state、消息或 localStorage。
const remoteConnections = new Map();
// 配置摘要和日志列表只保存在当前页面内存；不保存 YAML 或凭据。
const clusterContexts = new Map();
let clusterBusy = false;
let webLogPage = null;
let clusterRevision = 0;
let clusterRestoreId = 0;
const workflowLabels = {
  needs_information: "等待补充关键信息", framework_ready: "历史框架响应",
  awaiting_evidence: "等待现场证据", awaiting_verification: "方案待功能复测",
  awaiting_remote_authorization: "等待授权只读远程诊断",
  resolved: "问题已确认解决", collecting_evidence: "正在采集现场信息",
};

function safeText(value) {
  return String(value || "")
    .replace(/\b(password|passwd|token|secret|api[_-]?key|authorization)\b\s*[:=]\s*[^\n]+/gi, "$1=[REDACTED]")
    .replace(/(密码|口令)\s*[:：=]\s*\S+/g, "$1：[REDACTED]")
    .replace(/sk-[A-Za-z0-9_-]{16,}/g, "[REDACTED]")
    .replace(/-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----/g, "[REDACTED]");
}

async function apiRequest(url, {method = "GET", body, signal} = {}) {
  const response = await fetch(url, {method, signal, cache: "no-store",
    headers: body === undefined ? {} : {"Content-Type": "application/json"},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let result = {};
  try { result = await response.json(); }
  catch { if (response.ok && response.status !== 204) throw new Error("服务端返回了无法识别的结果。"); }
  if (!response.ok) throw new Error(typeof result.detail === "string" ? safeText(result.detail) : `操作未完成（HTTP ${response.status}），请检查输入与本地服务。`);
  return result;
}

function createId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function notify(message) {
  const toast = document.getElementById("toast");
  toast.textContent = safeText(message);
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 4000);
}

function saveState() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
  catch { notify("浏览器未能保存记录，当前会话仍可继续使用。"); }
}

function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (saved && Array.isArray(saved.sessions)) {
      state.sessions = saved.sessions.filter(s => s && typeof s.id === "string" && typeof s.title === "string" && Array.isArray(s.messages)).map(s => {
        let lastUserId;
        const messages = s.messages.filter(m => m && ["user", "assistant", "notice", "error"].includes(m.role) && typeof m.content === "string").map(m => {
          const message = {id: typeof m.id === "string" ? m.id : createId(), role: m.role, content: m.content};
          if (typeof m.traceId === "string") message.traceId = m.traceId;
          if ([0, 1].includes(m.feedback)) message.feedback = m.feedback;
          if (m.role === "user") lastUserId = message.id;
          else message.replyTo = typeof m.replyTo === "string" ? m.replyTo : lastUserId;
          return message;
        });
        if (messages.at(-1)?.role === "user") {
          messages.push({id: createId(), role: "notice", content: "上次请求未完成，可以重试该问题。", replyTo: messages.at(-1).id});
        }
        return {id: s.id, title: s.title, messages, draft: typeof s.draft === "string" ? s.draft.slice(0, 12000) : "",
          serverOwned: s.serverOwned === true, workflowStatus: typeof s.workflowStatus === "string" ? s.workflowStatus : "",
          proposal: s.proposal && typeof s.proposal === "object" ? s.proposal : {},
        };
      });
      state.activeId = state.sessions.some(s => s.id === saved.activeId) ? saved.activeId : null;
      state.serverUrl = typeof saved.serverUrl === "string" ? saved.serverUrl : "";
    }
  } catch { notify("本地会话记录无法读取，已打开新的工作空间。"); }
}

function activeSession() { return state.sessions.find(s => s.id === state.activeId); }

function switchView(view) {
  if (!titles[view]) return;
  if (view !== "workspace") setChatExpanded(false);
  Object.keys(titles).forEach(key => {
    document.getElementById(`${key}-view`).hidden = key !== view;
  });
  document.querySelectorAll("[data-view]").forEach(button => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  document.getElementById("view-title").textContent = titles[view];
  if (view === "evaluations") loadEvaluations();
}

function newSession() {
  if (pending || clusterBusy) { notify("请等待当前请求结束。"); return; }
  const id = createId();
  state.sessions.unshift({id, title: "新的部署问题", messages: [], draft: ""});
  state.activeId = id;
  saveState();
  renderSessions();
  renderMessages();
  restoreDraft();
  switchView("workspace");
  document.getElementById("question").focus();
}

function renderSessions() {
  const list = document.getElementById("session-list");
  list.replaceChildren();
  state.sessions.forEach(session => {
    const button = document.createElement("button");
    button.className = "session-item" + (session.id === state.activeId ? " selected" : "");
    button.textContent = session.title;
    button.title = session.title;
    button.addEventListener("click", () => {
      if (pending || clusterBusy) { notify("请等待当前请求结束。"); return; }
      state.activeId = session.id;
      saveState(); renderSessions(); renderMessages(); restoreDraft(); switchView("workspace");
    });
    list.append(button);
  });
}

function renderMessages() {
  const session = activeSession();
  const messages = document.getElementById("messages");
  messages.replaceChildren();
  document.getElementById("welcome").hidden = Boolean(session?.messages.length);
  const lastUser = (session?.messages || []).filter(message => message.role === "user").at(-1);
  (session?.messages || []).forEach(message => {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${message.role}`;
    const label = document.createElement("div");
    label.className = "message-label";
    label.textContent = {user: "你", assistant: "部署助手", notice: "会话提示", error: "请求失败"}[message.role];
    const body = document.createElement("div");
    body.className = "message-body";
    body.textContent = message.content;
    wrapper.append(label, body); messages.append(wrapper);
    const actions = document.createElement("div");
    actions.className = "message-actions";
    if (["user", "assistant"].includes(message.role)) {
      const copy = document.createElement("button");
      copy.type = "button"; copy.className = "chat-action"; copy.textContent = "复制";
      copy.setAttribute("aria-label", message.role === "user" ? "复制问题" : "复制回答");
      copy.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(message.content); notify("文本已复制。"); }
        catch { notify("无法自动复制，请选中文本后复制。"); }
      });
      actions.append(copy);
    }
    if (message.role === "assistant" && message.traceId) {
      [ [1, "有帮助"], [0, "无帮助"] ].forEach(([score, title]) => {
        const feedback = document.createElement("button");
        feedback.type = "button";
        feedback.className = "chat-action" + (message.feedback === score ? " feedback-selected" : "");
        feedback.textContent = title;
        feedback.setAttribute("aria-pressed", String(message.feedback === score));
        feedback.addEventListener("click", () => submitFeedback(message, score));
        actions.append(feedback);
      });
    }
    if (lastUser && ["notice", "error"].includes(message.role) && message.replyTo === lastUser.id) {
      const retry = document.createElement("button");
      retry.type = "button"; retry.className = "chat-action";
      retry.textContent = session.pendingVerification ? "继续提交复测结果" : "重试此问题";
      retry.disabled = Boolean(pending);
      retry.addEventListener("click", () => session.pendingVerification
        ? openVerificationDialog(session.pendingVerification) : sendQuestion(lastUser.content, lastUser.id));
      actions.append(retry);
    }
    if (actions.childElementCount) wrapper.append(actions);
  });
  updateChatControls();
  const conversation = document.getElementById("conversation");
  conversation.scrollTop = conversation.scrollHeight;
}

function updateChatControls() {
  document.getElementById("send-question").disabled = Boolean(pending) || restoringSessions || !document.getElementById("question").value.trim();
  document.getElementById("stop-question").hidden = !pending;
  document.getElementById("reply-pending").hidden = !pending;
  document.getElementById("conversation").setAttribute("aria-busy", String(Boolean(pending)));
  document.getElementById("chat-status").textContent = pending
    ? "正在等待回复。停止等待不会保证后端任务终止。"
    : restoringSessions ? "正在恢复服务端会话…" : "会话可从服务端恢复；输入草稿保存在当前浏览器。";
  updateBusinessControls();
}

function currentConnection() {
  const session = activeSession();
  const connection = session && remoteConnections.get(session.id);
  if (connection && connection.expires_at && Date.parse(connection.expires_at) <= Date.now()) {
    remoteConnections.delete(session.id);
    return null;
  }
  return connection;
}

function updateBusinessControls() {
  const session = activeSession();
  const connection = currentConnection();
  const busy = Boolean(pending) || remoteBusy || restoringSessions;
  document.getElementById("remote-status").textContent = connection
    ? `已授权 ${connection.username}@${connection.host}${connection.collected ? " · 已采集现场" : "（首次采集验证连接）"}` : "未授权远程连接";
  document.getElementById("workflow-status").textContent = workflowLabels[session?.workflowStatus] || "等待提问";
  document.getElementById("authorize-remote").disabled = busy || Boolean(connection);
  document.getElementById("collect-diagnostics").disabled = busy || !connection;
  document.getElementById("revoke-remote").disabled = remoteBusy || !connection;
  document.getElementById("verify-resolution").disabled = busy || !session?.messages.some(message => message.role === "user");
  document.getElementById("refresh-sessions").disabled = busy || clusterBusy;
  document.getElementById("open-cluster-config").disabled = busy || clusterBusy;
  document.getElementById("refresh-web-logs").disabled = busy || clusterBusy || !clusterContexts.has(session?.id);
}

function restoreDraft() {
  document.getElementById("question").value = activeSession()?.draft || "";
  renderClusterContext();
  updateChatControls();
  if (activeSession()) restoreClusterContext(activeSession().id);
}

function setChatExpanded(expanded) {
  document.body.classList.toggle("chat-expanded", expanded);
  const card = document.querySelector(".conversation-card");
  if (expanded) {
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-modal", "true");
  } else {
    card.removeAttribute("role");
    card.removeAttribute("aria-modal");
  }
  const button = document.getElementById("expand-chat");
  button.setAttribute("aria-pressed", String(expanded));
  button.textContent = expanded ? "收起窗口 ↙" : "展开窗口 ↗";
  requestAnimationFrame(() => {
    const conversation = document.getElementById("conversation");
    conversation.scrollTop = conversation.scrollHeight;
  });
}

// 只传成功完成的问答轮次；当前问题、失败及占位提示不作为模型历史。
function completedHistory(session, questionId) {
  const history = [];
  let user = null;
  for (const message of session.messages) {
    if (message.id === questionId) break;
    if (message.role === "user") user = message;
    else if (message.role === "assistant" && user && message.replyTo === user.id) {
      history.push({role: "user", content: user.content}, {role: "assistant", content: message.content});
      user = null;
    }
  }
  return history.slice(-40);
}

async function sendQuestion(question, retryId = null) {
  if (!question.trim() || pending || restoringSessions) return;
  if (question.length > 12000) { notify("问题最多支持 12000 个字符，请精简后发送。"); return; }
  if (!activeSession()) newSession();
  const session = activeSession();
  let user;
  if (retryId) {
    user = session.messages.find(message => message.id === retryId && message.role === "user");
    if (!user) return;
    session.messages = session.messages.filter(message => message.replyTo !== retryId);
  } else {
    user = {id: createId(), role: "user", content: question};
    if (!session.messages.length) session.title = question.slice(0, 24);
    session.messages.push(user);
    session.draft = "";
    document.getElementById("question").value = "";
  }
  const request = {controller: new AbortController(), sessionId: session.id, userId: user.id};
  pending = request;
  saveState(); renderSessions(); renderMessages();
  try {
    const response = await fetch("/api/assistant/messages", {
      method: "POST", headers: {"Content-Type": "application/json"}, signal: request.controller.signal,
      body: JSON.stringify({thread_id: session.id, request_id: user.id,
        connection_id: currentConnection()?.connection_id || null,
        question: user.content, history: session.serverOwned ? [] : completedHistory(session, user.id), context: {}})
    });
    const result = await response.json();
    if (pending !== request) return;
    if (response.status === 501 && result.status === "not_implemented") {
      session.messages.push({id: createId(), role: "notice", replyTo: user.id, content: `${result.message}\n问题已保留，问答接入后可以重试。`});
    } else if (response.ok && result.status === "completed" && result.thread_id === session.id && typeof result.answer === "string" && result.answer.trim()) {
      appendAssistantResponse(session, result, user.id);
    } else {
      throw new Error(typeof result.detail === "string" ? result.detail : "请求返回了无法识别的结果。");
    }
  } catch (error) {
    if (pending !== request) return;
    const detail = error instanceof Error && error.message !== "Failed to fetch" ? safeText(error.message) : "请检查本地服务与网络。";
    session.messages.push({id: createId(), role: "error", replyTo: user.id, content: `请求未能完成。${detail}\n问题已保留，可以重试。`});
  } finally {
    // 停止后的迟到响应不得覆盖后续请求或另一个会话。
    if (pending === request) {
      pending = null;
      saveState(); renderMessages(); document.getElementById("question").focus();
    }
  }
}

function stopWaiting() {
  if (!pending) return;
  const request = pending;
  pending = null;
  request.controller.abort();
  const session = state.sessions.find(item => item.id === request.sessionId);
  if (session) session.messages.push({id: createId(), role: "notice", replyTo: request.userId,
    content: "已停止等待本次操作。后端任务可能仍在运行；稍后恢复服务端会话可查看结果，避免立即重复执行。"});
  saveState(); renderMessages(); document.getElementById("question").focus();
}

function appendAssistantResponse(session, result, replyTo) {
  session.messages.push({id: createId(), role: "assistant", replyTo,
    content: safeText(result.answer), traceId: typeof result.trace_id === "string" ? result.trace_id : undefined});
  session.serverOwned = true;
  session.workflowStatus = result.workflow_status || "";
  session.proposal = result.proposal || session.proposal || {};
  session.pendingVerification = null;
}

async function restoreServerSessions() {
  if (pending || restoringSessions || clusterBusy) return;
  restoringSessions = true;
  updateChatControls();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const result = await apiRequest("/api/assistant/sessions", {signal: controller.signal});
    if (!Array.isArray(result.items)) throw new Error("服务端会话格式不正确。");
    const restored = [];
    for (const item of result.items) {
      if (typeof item.thread_id !== "string" || !Array.isArray(item.messages)) continue;
      const local = state.sessions.find(session => session.id === item.thread_id);
      let lastUserId = null;
      const messages = item.messages.filter(message => message && ["user", "assistant", "notice", "error"].includes(message.role) && typeof message.content === "string").map((message, index) => {
        const saved = {id: typeof message.id === "string" ? message.id : `${item.thread_id}:server:${index}`,
          role: message.role, content: safeText(message.content)};
        if (saved.role === "user") lastUserId = saved.id;
        else saved.replyTo = lastUserId;
        if (typeof message.trace_id === "string") saved.traceId = message.trace_id;
        return saved;
      });
      const lastAssistant = messages.filter(message => message.role === "assistant").at(-1);
      if (lastAssistant && typeof item.last_response?.trace_id === "string") lastAssistant.traceId = item.last_response.trace_id;
      restored.push({id: item.thread_id, title: messages.find(message => message.role === "user")?.content.slice(0, 24) || local?.title || "诊断会话",
        messages, draft: local?.draft || "", serverOwned: true,
        workflowStatus: item.workflow_status || "", proposal: item.proposal || {}, updatedAt: item.updated_at,
        pendingVerification: item.pending_request?.action === "verify_resolution" ? item.pending_request.verification : null,
      });
    }
    // 已存在于服务端的 thread 以服务端历史为准；尚未发送的新草稿继续保留。
    const ids = new Set(restored.map(session => session.id));
    state.sessions = [...restored, ...state.sessions.filter(session => !ids.has(session.id)).map(session => ({...session, serverOwned: false}))];
    if (!activeSession() || (!activeSession().messages.length && restored.length)) state.activeId = restored[0]?.id || state.sessions[0]?.id;
    saveState(); renderSessions(); renderMessages(); restoreDraft();
  } catch (error) {
    notify(error.name === "AbortError" ? "恢复会话超时，浏览器中的草稿仍可使用。" : `暂未恢复服务端会话。${safeText(error.message)}`);
  } finally {
    clearTimeout(timer);
    restoringSessions = false;
    updateChatControls();
  }
}

async function restoreClusterContext(threadId) {
  const requestId = ++clusterRestoreId;
  const revision = clusterRevision;
  try {
    const response = await fetch(`/api/assistant/cluster-config?thread_id=${encodeURIComponent(threadId)}`, {cache: "no-store"});
    if (requestId !== clusterRestoreId || revision !== clusterRevision || state.activeId !== threadId) return;
    if (response.status === 404) {
      clusterContexts.delete(threadId);
      renderClusterContext(); updateBusinessControls();
      return;
    }
    if (!response.ok) throw new Error("读取失败");
    const result = await response.json();
    if (requestId !== clusterRestoreId || revision !== clusterRevision || state.activeId !== threadId) return;
    if (!result.cluster || !Array.isArray(result.cluster.nodes)) throw new Error("结果格式错误");
    const entry = {cluster: result.cluster, logs: result.logs || {items: []},
      selectedLog: result.selected_log || null};
    clusterContexts.set(threadId, entry);
    if (!remoteConnections.has(threadId)) {
      setClusterConnection(threadId, entry.cluster, result.connection,
        result.connection?.node_name || entry.cluster.master_name);
    }
    renderClusterContext(); updateBusinessControls();
  } catch {
    if (requestId === clusterRestoreId && revision === clusterRevision && state.activeId === threadId) {
      notify("集群摘要暂未恢复，请检查本地服务。");
    }
  }
}

function renderClusterContext() {
  const session = activeSession();
  const entry = session && clusterContexts.get(session.id);
  const summary = document.getElementById("cluster-summary");
  const nodes = document.getElementById("cluster-nodes");
  const logs = document.getElementById("web-logs-list");
  const credentials = document.getElementById("cluster-credentials");
  const choice = document.getElementById("web-cluster-choice");
  const select = document.getElementById("web-cluster-select");
  nodes.replaceChildren();
  logs.replaceChildren();
  credentials.replaceChildren();
  choice.hidden = true;
  if (!entry) {
    summary.textContent = "粘贴 config.yaml 后识别节点，并通过第一个 master 查找 Web 任务日志。";
    document.getElementById("web-logs-status").textContent = "尚未读取。";
    return;
  }
  const cluster = entry.cluster;
  const fields = [
    ["集群", cluster.cluster_name || "未指定"],
    ["Kubernetes", cluster.kubernetes_version || "未指定"],
    ["安装方式", cluster.install_mode || "未指定"],
    ["首个 master", cluster.master_name || "未指定"],
    ["容器运行时", cluster.container_manager],
    ["控制面地址", cluster.control_plane_endpoint?.address],
    ["控制面域名", cluster.control_plane_endpoint?.domain],
    ["控制面端口", cluster.control_plane_endpoint?.port],
    ["网络插件", cluster.network?.plugin],
    ["Pod 网段", cluster.network?.kube_pods_cidr],
    ["Service 网段", cluster.network?.kube_service_cidr],
    ["仓库类型", cluster.registry?.type],
    ["仓库地址", cluster.registry?.private_registry],
  ];
  summary.textContent = fields.filter(([, value]) => value).map(([label, value]) => `${label}：${value}`).join(" · ");
  for (const node of cluster.nodes || []) {
    const row = document.createElement("div");
    row.className = "cluster-node";
    const text = document.createElement("span");
    text.textContent = `${node.name || "未命名"} · ${node.address || "未指定地址"}:${node.port || 22} · ${node.username || "root"} · ${(node.roles || []).join(" / ") || "未指定角色"}`;
    const fingerprint = document.createElement("input");
    fingerprint.type = "text";
    fingerprint.className = "node-fingerprint";
    fingerprint.placeholder = "主机指纹（可选）";
    fingerprint.setAttribute("aria-label", `${node.name} 的 SHA256 主机指纹`);
    fingerprint.maxLength = 64;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chat-action";
    button.textContent = "使用此节点诊断";
    button.disabled = clusterBusy || Boolean(pending) || !node.name;
    button.addEventListener("click", () => connectClusterNode(node, fingerprint.value.trim() || null));
    row.append(text);
    appendCredentialViewer(row, session.id, "node", node.name, node.has_password);
    row.append(fingerprint, button);
    nodes.append(row);
  }
  for (const [category, label, items] of [["component", "组件", cluster.components || []], ["registry", "镜像仓库", cluster.registries || []]]) {
    for (const item of items) {
      const name = category === "registry" ? item.address : item.name;
      const row = document.createElement("div");
      row.className = "cluster-node";
      const text = document.createElement("span");
      text.textContent = `${label} · ${name || "未命名"} · 账号：${item.username || "未配置"}`;
      row.append(text);
      appendCredentialViewer(row, session.id, category, name, item.has_password);
      credentials.append(row);
    }
  }
  document.getElementById("web-logs-status").textContent = entry.logs.error
    ? safeText(entry.logs.error)
    : `找到 ${(entry.logs.items || []).length} 条任务日志。`;
  const options = entry.logs.cluster_options || [];
  if (options.length > 1 || (options.length && !entry.logs.selected_cluster)) {
    select.replaceChildren();
    const empty = document.createElement("option");
    empty.value = ""; empty.textContent = "请选择集群目录";
    select.append(empty);
    for (const name of options) {
      const option = document.createElement("option");
      option.value = name; option.textContent = name;
      select.append(option);
    }
    select.value = entry.logs.selected_cluster || "";
    select.disabled = clusterBusy;
    choice.hidden = false;
  }
  for (const item of entry.logs.items || []) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "web-log-item";
    const selected = entry.selectedLog?.scope === item.scope && entry.selectedLog?.pid === item.pid;
    button.textContent = `${item.scope === "obs" ? "OBS" : "集群"} · ${item.pid} · ${formatSize(item.size || 0)}${selected ? " · 当前诊断任务" : ""}`;
    button.addEventListener("click", () => openWebLog(item));
    logs.append(button);
  }
}

function appendCredentialViewer(row, threadId, category, name, hasPassword) {
  if (!hasPassword || !name) return;
  const button = document.createElement("button");
  button.type = "button"; button.className = "chat-action"; button.textContent = "查看密码";
  const value = document.createElement("span");
  value.className = "credential-value";
  button.addEventListener("click", async () => {
    if (value.textContent) {
      value.textContent = ""; button.textContent = "查看密码";
      return;
    }
    button.disabled = true;
    try {
      const params = new URLSearchParams({thread_id: threadId, category, name});
      const result = await apiRequest(`/api/assistant/cluster-config/credential?${params}`);
      if (typeof result.password !== "string") throw new Error("账号密码不可用。");
      value.textContent = result.password;
      button.textContent = "隐藏密码";
    } catch { notify("账号密码读取失败，请重新导入配置。"); }
    finally { button.disabled = false; }
  });
  row.append(button, value);
}

function setClusterConnection(sessionId, cluster, connection, nodeName) {
  if (!connection?.connection_id) return;
  const node = (cluster.nodes || []).find(item => item.name === nodeName) || {};
  remoteConnections.set(sessionId, {connection_id: connection.connection_id,
    host: node.address || node.name || nodeName, username: node.username || "root", expires_at: connection.expires_at});
}

async function submitClusterConfig(event) {
  event.preventDefault();
  const session = activeSession();
  const input = document.getElementById("cluster-yaml");
  if (!session || clusterBusy || !input.value.trim()) return;
  clusterRevision++;
  const payload = {thread_id: session.id, yaml_content: input.value,
    host_key_sha256: document.getElementById("cluster-master-fingerprint").value.trim() || null};
  input.value = "";
  clusterBusy = true;
  document.getElementById("submit-cluster-config").disabled = true;
  document.getElementById("cluster-config-status").textContent = "正在解析配置并查找 Web 任务日志…";
  updateBusinessControls();
  try {
    const result = await apiRequest("/api/assistant/cluster-config", {method: "POST", body: payload});
    if (!result.cluster || !Array.isArray(result.cluster.nodes)) throw new Error("服务端未返回有效集群配置。");
    const entry = {cluster: result.cluster, logs: result.logs || {items: []}};
    clusterContexts.set(session.id, entry);
    setClusterConnection(session.id, entry.cluster, result.connection || result, entry.cluster.master_name);
    document.getElementById("cluster-config-dialog").close();
    renderClusterContext();
    notify(entry.logs.error ? "集群配置已读取，Web 日志暂不可用。" : "集群配置和 Web 任务日志已读取。");
  } catch (error) {
    document.getElementById("cluster-config-status").textContent = `配置读取未完成。${safeText(error.message)} 请重新粘贴配置。`;
  } finally {
    payload.yaml_content = "";
    clusterBusy = false;
    document.getElementById("submit-cluster-config").disabled = false;
    renderClusterContext();
    updateBusinessControls();
  }
}

async function connectClusterNode(node, hostKeySha256 = null) {
  const session = activeSession();
  const entry = session && clusterContexts.get(session.id);
  if (!entry || clusterBusy || pending) return;
  clusterRevision++;
  clusterBusy = true;
  renderClusterContext(); updateBusinessControls();
  try {
    const result = await apiRequest("/api/assistant/cluster-config/connect", {method: "POST",
      body: {thread_id: session.id, node_name: node.name, host_key_sha256: hostKeySha256}});
    if (!result.connection_id) throw new Error("服务端未返回节点连接。");
    setClusterConnection(session.id, entry.cluster, result, node.name);
    notify(`已选择节点 ${node.name} 进行只读诊断。`);
  } catch (error) { notify(`节点连接未建立。${safeText(error.message)}`); }
  finally { clusterBusy = false; renderClusterContext(); updateBusinessControls(); }
}

async function refreshWebLogs() {
  const session = activeSession();
  const entry = session && clusterContexts.get(session.id);
  if (!entry || clusterBusy) return;
  clusterRevision++;
  clusterBusy = true;
  document.getElementById("web-logs-status").textContent = "正在读取任务日志列表…";
  updateBusinessControls();
  try {
    const result = await apiRequest(`/api/assistant/web-logs/list?thread_id=${encodeURIComponent(session.id)}`);
    entry.logs = result;
  } catch (error) { entry.logs = {items: [], error: `日志列表读取失败。${safeText(error.message)}`}; }
  finally { clusterBusy = false; renderClusterContext(); updateBusinessControls(); }
}

async function selectWebCluster(event) {
  const session = activeSession();
  const entry = session && clusterContexts.get(session.id);
  const name = event.target.value;
  if (!entry || clusterBusy || !name) return;
  clusterRevision++;
  clusterBusy = true;
  renderClusterContext(); updateBusinessControls();
  try {
    const result = await apiRequest("/api/assistant/cluster-config/select", {method: "POST",
      body: {thread_id: session.id, cluster_name: name}});
    entry.logs = result.logs || result;
    entry.selectedLog = null;
  } catch (error) { notify(`集群目录选择失败。${safeText(error.message)}`); }
  finally { clusterBusy = false; renderClusterContext(); updateBusinessControls(); }
}

async function openWebLog(item) {
  const session = activeSession();
  if (!session) return;
  clusterRevision++;
  webLogPage = {threadId: session.id, scope: item.scope, pid: item.pid, offsets: [0], index: 0, next: null};
  const page = webLogPage;
  document.getElementById("web-log-title").textContent = `任务日志 · ${item.pid}`;
  document.getElementById("web-log-content").textContent = "";
  document.getElementById("web-log-status").textContent = "正在选择任务并读取日志…";
  document.getElementById("web-log-previous").disabled = true;
  document.getElementById("web-log-next").disabled = true;
  document.getElementById("web-log-dialog").showModal();
  try {
    await apiRequest("/api/assistant/web-logs/select", {method: "POST",
      body: {thread_id: session.id, scope: item.scope, pid: item.pid}});
    const entry = clusterContexts.get(session.id);
    if (entry) entry.selectedLog = {scope: item.scope, pid: item.pid};
    page.selectionStatus = "已选作后续诊断任务";
    renderClusterContext();
  } catch (error) {
    page.selectionStatus = `未选作后续诊断任务：${safeText(error.message)}`;
  }
  if (webLogPage === page) loadWebLogPage();
}

async function loadWebLogPage() {
  const page = webLogPage;
  if (!page || page.loading) return;
  page.loading = true;
  const previous = document.getElementById("web-log-previous"), next = document.getElementById("web-log-next");
  previous.disabled = true; next.disabled = true;
  document.getElementById("web-log-status").textContent = "正在读取日志…";
  try {
    const params = new URLSearchParams({thread_id: page.threadId, scope: page.scope, pid: page.pid,
      offset: String(page.offsets[page.index])});
    const result = await apiRequest(`/api/assistant/web-logs?${params}`);
    if (webLogPage !== page) return;
    if (typeof result.content !== "string") throw new Error("服务端未返回日志内容。");
    document.getElementById("web-log-content").textContent = result.content;
    page.next = result.eof ? null : result.next_offset;
    document.getElementById("web-log-status").textContent = `${page.selectionStatus} · 第 ${page.index + 1} 页 · 文件大小 ${formatSize(result.size || 0)}${result.eof ? " · 已到末尾" : ""}`;
  } catch (error) {
    if (webLogPage === page) document.getElementById("web-log-status").textContent = `日志读取失败。${safeText(error.message)}`;
  } finally {
    page.loading = false;
    if (webLogPage === page) { previous.disabled = page.index === 0; next.disabled = page.next == null; }
  }
}

function openRemoteDialog() {
  if (!activeSession() || pending || remoteBusy) return;
  const form = document.getElementById("remote-form");
  form.reset();
  document.getElementById("remote-form-status").textContent = "";
  document.getElementById("remote-dialog").showModal();
}

function clearRemoteForm() {
  document.getElementById("remote-form").reset();
  document.getElementById("remote-password").value = "";
  document.getElementById("remote-form-status").textContent = "";
}

async function authorizeRemote(event) {
  event.preventDefault();
  if (remoteBusy) return;
  const session = activeSession();
  const payload = {thread_id: session.id,
    host: document.getElementById("remote-host").value.trim(),
    port: Number(document.getElementById("remote-port").value),
    username: document.getElementById("remote-username").value.trim(),
    password: document.getElementById("remote-password").value,
  };
  const fingerprint = document.getElementById("remote-fingerprint").value.trim();
  if (fingerprint) payload.host_key_sha256 = fingerprint;
  document.getElementById("remote-password").value = "";
  remoteBusy = true;
  document.getElementById("submit-remote").disabled = true;
  document.getElementById("remote-form-status").textContent = "正在登记本会话的临时只读授权…";
  updateBusinessControls();
  try {
    const result = await apiRequest("/api/assistant/connections", {method: "POST", body: payload});
    if (typeof result.connection_id !== "string") throw new Error("服务端未返回有效连接句柄。");
    remoteConnections.set(session.id, {connection_id: result.connection_id, host: payload.host,
      username: payload.username, expires_at: result.expires_at});
    document.getElementById("remote-dialog").close();
    notify("已登记只读授权，点击采集基础信息验证连接并读取现场。");
  } catch (error) {
    document.getElementById("remote-form-status").textContent = safeText(error.message) || "授权未完成，请重新检查连接信息。";
  } finally {
    payload.password = "";
    document.getElementById("remote-password").value = "";
    remoteBusy = false;
    document.getElementById("submit-remote").disabled = false;
    updateBusinessControls();
  }
}

async function revokeRemote() {
  const session = activeSession(), connection = currentConnection();
  if (!connection || remoteBusy) return;
  remoteBusy = true;
  updateBusinessControls();
  try {
    await apiRequest(`/api/assistant/connections/${encodeURIComponent(connection.connection_id)}?thread_id=${encodeURIComponent(session.id)}`, {method: "DELETE"});
    remoteConnections.delete(session.id);
    notify("临时连接授权已撤销。");
  } catch (error) { notify(`撤销未完成。${safeText(error.message)}`); }
  finally { remoteBusy = false; updateBusinessControls(); }
}

async function collectBasicDiagnostics() {
  const session = activeSession(), connection = currentConnection();
  if (!connection || pending) return;
  const request = {controller: new AbortController(), sessionId: session.id, kind: "diagnostics"};
  pending = request;
  updateChatControls();
  try {
    const result = await apiRequest("/api/assistant/diagnostics", {method: "POST", signal: request.controller.signal,
      body: {thread_id: session.id, connection_id: connection.connection_id,
        checks: ["host_summary", "cluster_nodes", "events"].map(name => ({name, parameters: {}}))},
    });
    if (pending !== request) return;
    if (result.thread_id !== session.id || !Array.isArray(result.evidence)) throw new Error("服务端未返回有效诊断证据。");
    const summaries = result.evidence.map(item => {
      const name = item.check?.name || item.check || "现场检查";
      const output = safeText([item.stdout, item.stderr].filter(Boolean).join("\n"));
      return `${name} · 退出码 ${item.exit_code ?? "未知"}\n${output.slice(0, 1800)}${output.length > 1800 || item.truncated ? "\n（窗口仅展示部分输出）" : ""}`;
    });
    session.messages.push({id: createId(), role: "notice", content: `现场信息已采集并保存，后续诊断将使用这些证据。\n\n${summaries.join("\n\n")}\n\n可以继续描述问题，让助手结合现场信息分析。`});
    connection.collected = true;
  } catch (error) {
    if (pending === request) session.messages.push({id: createId(), role: "error", content: `现场采集未完成。${safeText(error.message)}`});
  } finally {
    if (pending === request) { pending = null; saveState(); renderMessages(); }
  }
}

function openVerificationDialog(values = null) {
  const session = activeSession();
  if (pending || !session?.messages.some(message => message.role === "user")) return;
  document.getElementById("verification-form").reset();
  const verification = values && typeof values.root_cause === "string" ? values : session.pendingVerification;
  document.getElementById("verified-cause").value = verification?.root_cause || (typeof session.proposal?.root_cause === "string" ? session.proposal.root_cause : "");
  document.getElementById("verified-steps").value = Array.isArray(verification?.resolution_steps) ? verification.resolution_steps.join("\n") : "";
  document.getElementById("verified-evidence").value = verification?.evidence || "";
  document.getElementById("verification-form-status").textContent = "";
  document.getElementById("verification-dialog").showModal();
}

async function submitVerification(event) {
  event.preventDefault();
  if (pending) return;
  const session = activeSession();
  const evidence = document.getElementById("verified-evidence").value.trim();
  const rootCause = document.getElementById("verified-cause").value.trim();
  const steps = document.getElementById("verified-steps").value.split("\n").map(value => value.trim()).filter(Boolean);
  if (rootCause.length < 2 || !steps.length || steps.length > 20 || evidence.length < 8 || !document.getElementById("verified-confirmed").checked) {
    document.getElementById("verification-form-status").textContent = "请填写至少 2 字的根因、1～20 行实际解决步骤，以及至少 8 字的功能复测结果，并勾选确认。";
    return;
  }
  const request = {controller: new AbortController(), sessionId: session.id, kind: "verification",
    userId: session.messages.filter(message => message.role === "user").at(-1)?.id};
  const verification = {thread_id: session.id, confirmed: true,
    method: session.pendingVerification?.method || "user_confirmation", evidence,
    root_cause: rootCause, resolution_steps: steps};
  session.pendingVerification = verification;
  pending = request;
  document.getElementById("submit-verification").disabled = true;
  document.getElementById("verification-form-status").textContent = "正在记录复测结果、整理案例并尝试入库…";
  updateChatControls();
  try {
    const result = await apiRequest("/api/assistant/verification", {method: "POST", signal: request.controller.signal,
      body: verification,
    });
    if (pending !== request) return;
    if (result.thread_id !== session.id || typeof result.answer !== "string") throw new Error("服务端未返回有效验证结果。");
    appendAssistantResponse(session, result);
    document.getElementById("verification-dialog").close();
  } catch (error) {
    if (pending === request) document.getElementById("verification-form-status").textContent = `验证提交未完成。${safeText(error.message)}`;
  } finally {
    document.getElementById("submit-verification").disabled = false;
    if (pending === request) { pending = null; saveState(); renderMessages(); }
  }
}

async function submitFeedback(message, score) {
  try {
    await apiRequest("/api/assistant/feedback", {method: "POST", body: {trace_id: message.traceId, score}});
    message.feedback = score;
    saveState(); renderMessages(); notify("反馈已提交。");
  } catch (error) { notify(`反馈暂未提交。${safeText(error.message)}`); }
}

function countText(value) {
  return Number.isFinite(value) ? value.toLocaleString("zh-CN") : "—";
}

function costText(metrics) {
  if (Number.isFinite(metrics.cost)) return metrics.cost.toFixed(6);
  if (Number.isFinite(metrics.known_cost)) return `${metrics.known_cost.toFixed(6)}（部分）`;
  return metrics.call_count ? "未知" : "暂无调用";
}

function tokenText(metrics, field) {
  if (Number.isFinite(metrics[field])) return countText(metrics[field]);
  if (metrics[field] === null || metrics.missing_usage_count > 0) {
    const known = metrics[`known_${field}`];
    return Number.isFinite(known) ? `未知（已知 ${countText(known)}）` : "未知";
  }
  return "—";
}

async function loadEvaluations() {
  const button = document.getElementById("refresh-evaluations");
  if (button.disabled) return;
  button.disabled = true;
  document.getElementById("evaluation-status").textContent = "正在加载本地执行与用量记录…";
  try {
    const result = await apiRequest("/api/evaluations");
    const metrics = result.metrics || {};
    document.getElementById("metric-traces").textContent = countText(metrics.trace_count);
    document.getElementById("metric-calls").textContent = countText(metrics.model_call_count ?? metrics.call_count);
    document.getElementById("metric-usage-detail").textContent = metrics.missing_usage_count
      ? `${countText(metrics.missing_usage_count)} 次调用缺少完整用量，Token 总计未知` : "包含失败及未返回用量的调用";
    document.getElementById("metric-tokens").textContent = tokenText(metrics, "total_tokens");
    document.getElementById("metric-token-detail").textContent = `输入 ${tokenText(metrics, "input_tokens")} / 输出 ${tokenText(metrics, "output_tokens")}`;
    document.getElementById("metric-cost").textContent = costText(metrics);
    document.getElementById("metric-cost-detail").textContent = metrics.missing_cost_count
      ? `${countText(metrics.missing_cost_count)} 次用量记录缺少费用；不按零元计算` : "按接口实际费用或已配置计价记录统计";
    const langfuse = result.langfuse || {state: result.langfuse_reporting ? "configured" : "disabled"};
    const langfuseStates = {
      disabled: "未启用",
      unconfigured: "配置尚不完整",
      configured: "已配置，连接与认证尚未校验",
      connected: "连接与认证检查通过",
      error: "当前不可用",
    };
    const langfuseState = langfuseStates[langfuse.state] || "状态未知";
    const langfuseMessage = langfuse.message ? ` ${safeText(langfuse.message)}` : "";
    document.getElementById("evaluation-status").textContent =
      `以下数据来自本地观测记录。Langfuse：${langfuseState}。${langfuseMessage}`;
    const breakdown = document.getElementById("usage-breakdown");
    breakdown.replaceChildren();
    for (const [field, label] of [["by_model", "模型"], ["by_stage", "阶段"]]) {
      for (const [name, usage] of Object.entries(metrics[field] || {})) {
        const row = document.createElement("p");
        row.className = "field-help";
        row.textContent = `${label} ${safeText(name)}：${countText(usage.model_call_count ?? usage.call_count)} 次模型调用，输入 ${tokenText(usage, "input_tokens")} / 输出 ${tokenText(usage, "output_tokens")} Token，缺少完整用量 ${countText(usage.missing_usage_count ?? 0)} 次，费用 ${costText(usage)}`;
        breakdown.append(row);
      }
    }
    if (!breakdown.childElementCount) {
      const empty = document.createElement("p");
      empty.className = "field-help";
      empty.textContent = "尚无模型用量记录。模型未返回用量时不会编造 Token 数。";
      breakdown.append(empty);
    }
    const list = document.getElementById("trace-list");
    list.replaceChildren();
    const items = Array.isArray(result.items) ? result.items : [];
    document.getElementById("trace-total").textContent = `最近 ${items.length} 条`;
    for (const trace of items) {
      const row = document.createElement("div");
      row.className = "document-row";
      const info = document.createElement("div");
      info.className = "document-info";
      const heading = document.createElement("h3");
      heading.textContent = safeText(trace.question || "诊断执行").slice(0, 180);
      const meta = document.createElement("div");
      meta.className = "document-meta";
      const values = [workflowLabels[trace.status] || trace.status || "未知状态", trace.created_at,
        Number.isFinite(trace.duration_ms) ? `${Math.round(trace.duration_ms)} ms` : "执行中",
        `Trace ${trace.trace_id || "—"}`];
      if (trace.langfuse_trace_id) values.push(`Langfuse Trace ${trace.langfuse_trace_id}`);
      if (trace.langfuse_observation_id) values.push(`Langfuse Observation ${trace.langfuse_observation_id}`);
      if (Array.isArray(trace.report_errors) && trace.report_errors.length) values.push("Langfuse 上报有异常，记录已保存在本地");
      values.filter(Boolean).forEach(value => {
        const span = document.createElement("span");
        span.textContent = safeText(value);
        meta.append(span);
      });
      info.append(heading, meta);
      row.append(info);
      list.append(row);
    }
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "document-row muted";
      empty.textContent = "还没有执行记录。发送问题或采集现场后，可在此刷新查看。";
      list.append(empty);
    }
  } catch (error) {
    document.getElementById("evaluation-status").textContent = `运行记录暂未加载。${safeText(error.message)}`;
  } finally { button.disabled = false; }
}

function formatSize(bytes) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${(bytes / 1024).toFixed(1)} KB`;
}

function renderDocuments(documents) {
  document.getElementById("nav-doc-count").textContent = documents.length;
  document.getElementById("workspace-doc-count").textContent = documents.length;
  document.getElementById("document-total").textContent = `${documents.length} 份原始文档`;
  const list = document.getElementById("document-list");
  list.replaceChildren();
  if (!documents.length) {
    const empty = document.createElement("p");
    empty.className = "document-row muted";
    empty.textContent = "尚未添加原始文档。";
    list.append(empty);
  }
  documents.forEach(documentInfo => {
    const row = document.createElement("div"); row.className = "document-row";
    const icon = document.createElement("div"); icon.className = "file-icon"; icon.textContent = documentInfo.format;
    const info = document.createElement("div"); info.className = "document-info";
    const title = document.createElement("h3"); title.textContent = documentInfo.name;
    const meta = document.createElement("div"); meta.className = "document-meta";
    [documentInfo.category, documentInfo.modes.join(" / "), formatSize(documentInfo.size_bytes)].forEach(text => {
      const span = document.createElement("span"); span.textContent = text; meta.append(span);
    });
    const badge = document.createElement("span"); badge.className = "muted-badge"; badge.textContent = "通过接口录入";
    const download = document.createElement("a"); download.className = "download-link";
    download.href = documentInfo.download_url; download.textContent = "下载原文 ↓";
    info.append(title, meta); row.append(icon, info, badge, download); list.append(row);
  });
}

async function loadWorkspace() {
  try {
    const response = await fetch("/api/workspace");
    if (!response.ok) throw new Error();
    const workspace = await response.json();
    document.getElementById("assistant-mode").textContent = "GLM 问答";
    document.getElementById("assistant-summary").textContent = "GLM 问答 · 只读远程诊断";
    document.getElementById("assistant-scope").textContent = "发送问题将调用配置的 GLM 与检索服务。可单独授权只读诊断，复测确认后整理案例并尝试入库。";
    renderDocuments(workspace.documents);
    const matrix = document.getElementById("support-matrix"); matrix.replaceChildren();
    Object.entries(workspace.support_matrix).forEach(([version, systems]) => {
      const row = document.createElement("div"); row.className = "version-row";
      const strong = document.createElement("strong"); strong.textContent = version;
      const span = document.createElement("span"); span.textContent = systems.join(" / ");
      row.append(strong, span); matrix.append(row);
    });
  } catch { notify("工作空间信息加载失败，请检查本地服务后刷新页面。"); }
}

document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => switchView(button.dataset.view)));
document.querySelectorAll("[data-open-view]").forEach(button => button.addEventListener("click", () => switchView(button.dataset.openView)));
document.querySelectorAll("[data-question]").forEach(button => button.addEventListener("click", () => {
  document.getElementById("question").value = button.dataset.question;
  activeSession().draft = button.dataset.question;
  saveState(); updateChatControls();
  document.getElementById("question").focus();
}));
document.getElementById("new-session").addEventListener("click", newSession);
document.getElementById("clear-sessions").addEventListener("click", () => {
  if (pending || clusterBusy) { notify("请等待当前请求结束。"); return; }
  if (!confirm("清空浏览器会话缓存？服务端历史不会删除，刷新后仍可恢复。")) return;
  state.sessions = []; state.activeId = null; saveState(); newSession(); notify("本地缓存已清空，服务端历史仍可恢复。");
});
document.getElementById("refresh-sessions").addEventListener("click", restoreServerSessions);
document.getElementById("refresh-evaluations").addEventListener("click", loadEvaluations);
document.getElementById("open-cluster-config").addEventListener("click", () => {
  if (!activeSession() || pending || clusterBusy) return;
  document.getElementById("cluster-config-form").reset();
  document.getElementById("cluster-config-status").textContent = "";
  document.getElementById("cluster-config-dialog").showModal();
});
document.getElementById("cluster-config-form").addEventListener("submit", submitClusterConfig);
for (const id of ["close-cluster-config", "cancel-cluster-config"]) {
  document.getElementById(id).addEventListener("click", () => document.getElementById("cluster-config-dialog").close());
}
document.getElementById("cluster-config-dialog").addEventListener("close", () => {
  document.getElementById("cluster-yaml").value = "";
  document.getElementById("cluster-master-fingerprint").value = "";
  document.getElementById("cluster-config-status").textContent = "";
});
document.getElementById("refresh-web-logs").addEventListener("click", refreshWebLogs);
document.getElementById("web-cluster-select").addEventListener("change", selectWebCluster);
document.getElementById("close-web-log").addEventListener("click", () => document.getElementById("web-log-dialog").close());
document.getElementById("web-log-dialog").addEventListener("close", () => {
  webLogPage = null;
  document.getElementById("web-log-content").textContent = "";
});
document.getElementById("web-log-previous").addEventListener("click", () => {
  if (webLogPage && webLogPage.index > 0) { webLogPage.index--; loadWebLogPage(); }
});
document.getElementById("web-log-next").addEventListener("click", () => {
  if (webLogPage?.next != null) {
    webLogPage.offsets = webLogPage.offsets.slice(0, webLogPage.index + 1);
    webLogPage.offsets.push(webLogPage.next);
    webLogPage.index++;
    loadWebLogPage();
  }
});
document.getElementById("authorize-remote").addEventListener("click", openRemoteDialog);
document.getElementById("remote-form").addEventListener("submit", authorizeRemote);
document.getElementById("collect-diagnostics").addEventListener("click", collectBasicDiagnostics);
document.getElementById("revoke-remote").addEventListener("click", revokeRemote);
document.getElementById("verify-resolution").addEventListener("click", openVerificationDialog);
document.getElementById("verification-form").addEventListener("submit", submitVerification);
for (const id of ["close-remote-dialog", "cancel-remote-dialog"]) {
  document.getElementById(id).addEventListener("click", () => {
    clearRemoteForm();
    document.getElementById("remote-dialog").close();
  });
}
for (const id of ["close-verification-dialog", "cancel-verification-dialog"]) {
  document.getElementById(id).addEventListener("click", () => document.getElementById("verification-dialog").close());
}
document.getElementById("remote-dialog").addEventListener("close", clearRemoteForm);
document.getElementById("remote-dialog").addEventListener("cancel", clearRemoteForm);
document.getElementById("question").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    document.getElementById("question-form").requestSubmit();
  }
});
document.getElementById("question").addEventListener("input", event => {
  if (activeSession()) { activeSession().draft = event.target.value; saveState(); }
  updateChatControls();
});
document.getElementById("stop-question").addEventListener("click", stopWaiting);
document.getElementById("expand-chat").addEventListener("click", () => {
  setChatExpanded(!document.body.classList.contains("chat-expanded"));
  document.getElementById("question").focus();
});
document.addEventListener("keydown", event => {
  if (document.querySelector("dialog[open]")) return;
  if (!document.body.classList.contains("chat-expanded")) return;
  if (event.key === "Escape") {
    setChatExpanded(false);
    document.getElementById("expand-chat").focus();
  }
  if (event.key === "Tab") {
    const controls = [...document.querySelectorAll(".conversation-card button:not(:disabled):not([hidden]), .conversation-card textarea")].filter(element => element.getClientRects().length);
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
});
document.getElementById("question-form").addEventListener("submit", event => {
  event.preventDefault();
  sendQuestion(document.getElementById("question").value.trim());
});

loadState();
if (!activeSession()) newSession();
else { renderSessions(); renderMessages(); restoreDraft(); }
loadWorkspace();
restoreServerSessions();
setInterval(updateBusinessControls, 30000);
