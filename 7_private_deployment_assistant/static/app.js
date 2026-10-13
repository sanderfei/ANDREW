"use strict";

const STORAGE_KEY = "private-deployment-assistant:v1";
const titles = {workspace: "运维工作台", documents: "知识文档", evaluations: "评测实验"};
let state = {sessions: [], activeId: null, serverUrl: ""};
let pending = false;
let toastTimer;

function notify(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
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
      state.sessions = saved.sessions.filter(s => s && typeof s.id === "string" && typeof s.title === "string" && Array.isArray(s.messages)).map(s => ({...s, messages: s.messages.filter(m => m && ["user", "notice", "error"].includes(m.role) && typeof m.content === "string")}));
      state.activeId = state.sessions.some(s => s.id === saved.activeId) ? saved.activeId : null;
      state.serverUrl = typeof saved.serverUrl === "string" ? saved.serverUrl : "";
    }
  } catch { notify("本地会话记录无法读取，已打开新的工作空间。"); }
}

function activeSession() { return state.sessions.find(s => s.id === state.activeId); }

function switchView(view) {
  if (!titles[view]) return;
  Object.keys(titles).forEach(key => {
    document.getElementById(`${key}-view`).hidden = key !== view;
  });
  document.querySelectorAll("[data-view]").forEach(button => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  document.getElementById("view-title").textContent = titles[view];
}

function newSession() {
  if (pending) { notify("请等待当前请求结束。"); return; }
  const id = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  state.sessions.unshift({id, title: "新的部署问题", messages: []});
  state.activeId = id;
  saveState();
  renderSessions();
  renderMessages();
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
      if (pending) { notify("请等待当前请求结束。"); return; }
      state.activeId = session.id;
      saveState(); renderSessions(); renderMessages(); switchView("workspace");
    });
    list.append(button);
  });
}

function renderMessages() {
  const session = activeSession();
  const messages = document.getElementById("messages");
  messages.replaceChildren();
  document.getElementById("welcome").hidden = Boolean(session?.messages.length);
  (session?.messages || []).forEach(message => {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${message.role}`;
    const label = document.createElement("div");
    label.className = "message-label";
    label.textContent = message.role === "user" ? "我的问题" : "工作空间提示";
    const body = document.createElement("div");
    body.className = "message-body";
    body.textContent = message.content;
    wrapper.append(label, body); messages.append(wrapper);
  });
  const conversation = document.getElementById("conversation");
  conversation.scrollTop = conversation.scrollHeight;
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
  document.getElementById("question").focus();
}));
document.getElementById("new-session").addEventListener("click", newSession);
document.getElementById("clear-sessions").addEventListener("click", () => {
  if (pending) { notify("请等待当前请求结束。"); return; }
  if (!confirm("清空此浏览器中的全部会话记录？服务器地址草稿将保留。")) return;
  state.sessions = []; state.activeId = null; saveState(); newSession(); notify("本地会话已清空。");
});
document.getElementById("save-server").addEventListener("click", () => {
  const input = document.getElementById("server-url");
  const value = input.value.trim();
  if (value) {
    try {
      const url = new URL(value);
      if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error();
    } catch { notify("请输入不含凭据或查询参数的 HTTP(S) 服务器地址。"); input.focus(); return; }
  }
  state.serverUrl = value; saveState(); notify(value ? "地址草稿已保存，服务器连接将在后续接入。" : "服务器地址草稿已清除。");
});
document.getElementById("question").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    document.getElementById("question-form").requestSubmit();
  }
});
document.getElementById("question-form").addEventListener("submit", async event => {
  event.preventDefault();
  const input = document.getElementById("question");
  const question = input.value.trim();
  if (!question || pending) return;
  if (!activeSession()) newSession();
  const session = activeSession();
  if (!session.messages.length) session.title = question.slice(0, 24);
  session.messages.push({role: "user", content: question});
  input.value = ""; pending = true;
  const button = document.getElementById("send-question"); button.disabled = true;
  saveState(); renderSessions(); renderMessages();
  try {
    const response = await fetch("/api/assistant/messages", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({thread_id: session.id, question, context: {server_url: state.serverUrl || null}})
    });
    const result = await response.json();
    if (response.status === 501 && result.status === "not_implemented") {
      session.messages.push({role: "notice", content: `${result.message}\n问题已保存在本地会话中，你可以先浏览和下载部署文档。`});
    } else {
      throw new Error("unexpected response");
    }
  } catch {
    session.messages.push({role: "error", content: "请求未能完成。问题已保留，请检查本地服务后重试。"});
  } finally {
    pending = false; button.disabled = false; saveState(); renderMessages(); input.focus();
  }
});

loadState();
document.getElementById("server-url").value = state.serverUrl;
if (!activeSession()) newSession();
else { renderSessions(); renderMessages(); }
loadWorkspace();
