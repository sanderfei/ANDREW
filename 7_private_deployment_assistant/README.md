# 目录 7：私有化部署助手

基于 Web/KK 安装与运维场景的项目，提供纯文本会话窗口、原始文档浏览下载、可切换的
Qdrant / PostgreSQL+pgvector 录入与检索，以及 LangChain / LangGraph 多轮排障工作流。
问答默认使用 `framework` 模式，只演示信息收集和流程分支，不调用聊天模型、Embedding 或向量数据库。
显式启用 `glm` 模式后，才运行真实检索与 GLM 分析；回答会区分追问、待补充证据与待验证方案。
已提供临时 SSH 授权与只读取证、功能复测确认、案例自动归档及可靠入库任务，
服务端会话和 LangGraph 检查点写入本地 SQLite。执行记录、反馈与 Token 统计始终启用，
Langfuse 远程上报通过配置单独开启。

两套数据库的最简启动命令、配置切换、指定本地文件的录入接口见
[向量数据库使用说明](docs/vector-databases.md)。原始资料由使用者指定文件录入；
确认解决后生成的案例自动保存，Web 后台按配置处理其入库任务。
问答流程、节点职责和启用 GLM 的方式见 [助手工作流说明](docs/assistant-workflow.md)。

## 本地启动（2026-10-13 已验证）

在 Andrew 仓库根目录 `/home/wangfei/code/andrew` 执行。以下依次准备依赖、本地数据库环境、
启动 Qdrant 与 PostgreSQL+pgvector，最后启动 Web。

```bash
.venv/bin/python -m pip install -r 7_private_deployment_assistant/requirements.txt
.venv/bin/python 7_private_deployment_assistant/setup_local_databases.py
```

本机 WSL 发行版为 `Ubuntu`，当前用户没有 Docker socket 权限，已验证可以通过 WSL 管理员入口启动：

```bash
'/mnt/c/Windows/System32/wsl.exe' -d Ubuntu -u root -- docker compose --progress quiet \
  --env-file /home/wangfei/code/andrew/7_private_deployment_assistant/runtime/local.env \
  -f /home/wangfei/code/andrew/7_private_deployment_assistant/compose.yaml up -d
```

其他 Linux 环境可使用以下命令替代上一条；已有 Docker 权限时省略 `sudo`：

```bash
sudo docker compose \
  --env-file 7_private_deployment_assistant/runtime/local.env \
  -f 7_private_deployment_assistant/compose.yaml up -d
```

数据库启动后，启动 Web；该命令在当前终端前台运行，按 `Ctrl+C` 结束 Web 服务：

```bash
.venv/bin/python 7_private_deployment_assistant/app.py
```

| 服务 | 访问地址 |
| --- | --- |
| Web 界面 | <http://127.0.0.1:8070> |
| Web API 文档 | <http://127.0.0.1:8070/docs> |
| Qdrant 管理界面 | <http://127.0.0.1:6333/dashboard> |
| PostgreSQL+pgvector | `127.0.0.1:5433` |

2026-10-13 的启动验证确认：两套数据库均可连接，PostgreSQL 健康检查通过且 `vector` 扩展已启用，
Web 的 `/api/health`、`/api/workspace` 和 `/docs` 返回 200。
当时尚未录入文档，两个后端的 `chunks` 均为 0；这不是当前数据库状态查询结果。
集合和文档表在录入时创建。
`setup_local_databases.py` 会保留已有密码，数据库数据由 Docker 命名卷持久保存。

参数：`--host` 默认 `127.0.0.1`；`--port` 默认 `8070`。
例如：`.venv/bin/python 7_private_deployment_assistant/app.py --port 8071`。

## 当前界面

- 运维工作台：环境摘要、可展开的纯文本对话窗口、临时 SSH 连接与只读取证。
- 对话支持 Enter 发送、Shift + Enter 换行、粘贴日志、复制文本、失败重试和停止等待；支持会话切换和每个会话的输入草稿。
- 知识文档：展示原始 DOCX、Markdown、TXT 文件，提供下载和录入接口文档入口。
- 确认解决：提交明确根因、实际处理步骤与原故障功能复测证据，生成脱敏案例并排队入库。
- 执行与评测：展示本地真实执行记录、Token 汇总和用户反馈；固定问题集的批量质量评测仍待补充。
- 已完成会话由服务端保存，浏览器保留输入草稿与会话选择；没有用户账号和多租户权限系统。
- 发送问题进入 LangGraph 工作流。默认模式返回信息追问或框架待接入说明，不将未执行的检索写成“未命中”；清空会话需要在页面确认。

## 纯文本问答接口

窗口通过 `POST /api/assistant/messages` 调用 LangChain / LangGraph 工作流。
消息内容仅使用字符串，不上传图片或附件。请求示例：

```json
{
  "thread_id": "当前会话ID",
  "request_id": "本轮唯一请求ID",
  "question": "离线添加节点时镜像拉取失败，下一步检查什么？",
  "history": [
    {"role": "user", "content": "目标集群是 K8s 1.32.8、Ubuntu、离线部署。"},
    {"role": "assistant", "content": "请提供失败步骤和关键报错。"}
  ],
  "context": {}
}
```

`history` 只包含此前成功完成的问答轮次，最多携带最近 20 轮；当前问题单独放在
`question` 中，成功完成的追问、框架说明和诊断回复都属于正常对话，可进入历史；
失败、停止等待和旧版 HTTP 501 待接入提示不进入历史。
服务端已有历史时以服务端为准；浏览器历史只用于尚无服务端记录的会话初始化，避免重复追加。
本地 `runtime/assistant.sqlite3` 保存会话、幂等响应、案例任务和执行记录，
`runtime/checkpoints.sqlite3` 保存 LangGraph 检查点。相同 `thread_id + request_id` 的成功请求返回缓存结果；
失败请求使用同一 ID 重试时可从已保留的待执行节点恢复。临时 SSH 凭据不写入这些文件，重启后需重新授权连接。

工作流返回 HTTP 200，页面显示 `answer` 字符串，同时接口提供本轮流程状态：

```json
{
  "status": "completed",
  "thread_id": "当前会话ID",
  "answer": "请补充失败步骤和关键报错。",
  "workflow_status": "needs_information",
  "retrieval_status": "not_run",
  "steps": ["prepare_input", "check_information", "ask_for_information"],
  "sources": []
}
```

`status=completed` 表示本轮请求处理完成，不表示故障已经解决；排障进度看 `workflow_status`。
`steps` 是已执行节点名称列表，`sources` 是来源列表；完整合同见 API 文档。
框架模式不会返回真实案例命中或模型诊断结论。模型调用失败、结构化输出不合法、
引用越界或检索执行错误会返回 HTTP 503，不伪装成“没有相关案例”。
停止等待只取消浏览器请求，不保证后端任务终止；重试使用原请求 ID，不在会话中重复插入问题。

## 业务入口

```bash
# 同一会话补充信息；framework 模式不会调用聊天模型或向量检索。
.venv/bin/python 7_private_deployment_assistant/workflow_cli.py ask \
  "离线安装失败" --thread-id demo-7 --request-id demo-7-turn-1
.venv/bin/python 7_private_deployment_assistant/workflow_cli.py ask \
  "K8s 1.32.8，Ubuntu，添加节点时镜像拉取失败" --thread-id demo-7

.venv/bin/python 7_private_deployment_assistant/workflow_cli.py sessions
.venv/bin/python 7_private_deployment_assistant/workflow_cli.py metrics --thread-id demo-7
.venv/bin/python 7_private_deployment_assistant/workflow_cli.py jobs --thread-id demo-7
```

实际解决并复测后才能执行以下确认命令；示例文字需要替换为本次现场事实：

```bash
.venv/bin/python 7_private_deployment_assistant/workflow_cli.py verify demo-7 \
  --root-cause "已确认的实际根因" \
  --step "实际执行且有效的处理步骤" \
  --evidence "原故障功能复测的具体操作及结果" --confirmed

# CLI 不启动自动 worker。显式执行后才会生成 Embedding 并写入所选向量库。
.venv/bin/python 7_private_deployment_assistant/workflow_cli.py index-pending --limit 5
```

归档写入 `documents/source/assistant_cases/`，维护独立的 Markdown、metadata、README 和索引，
不会改写已有 `codex_cases`。故障已解决、文档已保存、向量已入库是三个状态；
失败任务保留错误摘要并重试，已完成任务不重复执行，新版本会淘汰旧的待入库任务。
Web 的 `[business].auto_index=true` 默认每 15 秒处理队列；可改为 `false` 后使用 CLI 显式处理。

SSH 当前支持主机概况、节点、Pod、事件、Pod describe、Pod 日志、Helm 状态七种固定检查。
需要可信 `known_hosts` 或已核验的 SHA256 主机指纹，密码仅在内存中按 TTL 保存；
模型只接收连接引用和脱敏取证结果。当前不执行任意 Shell、配置变更、重启或升级。
命令退出成功不自动标记故障解决，仍需提交具体功能复测证据。

Langfuse 的 `[langfuse].enabled` 默认 `false`；开启时从环境读取
`LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY` 和可选 `LANGFUSE_BASE_URL`。
本地统计使用模型实际返回的 usage；缺少 usage 时标记未知，不按字符串估算，
没有价格时费用为 `null`。按模型和阶段聚合的数据用于后续优化，不代表已有固定问题集的自动质量评分。

原始文件位于 [documents/source](documents/source/)，参考其私有化在线、离线部署内容。

## 项目结构

```text
app.py                 FastAPI 入口和接口
config.py / config.toml 路径、版本范围、向量数据库配置
contracts.py           问答请求和集群环境的数据合同
static/                Web 页面、样式、浏览器交互
services/documents.py  原始文档目录与下载
services/ingestion.py  指定文件解析、脱敏和切块
services/vector_service.py 统一录入与检索
services/chat_model.py 根据配置创建 GLM 聊天模型
services/business_runtime.py SQLite 会话、检查点、后台入库 worker
services/remote_diagnostics.py 临时 SSH 授权、固定只读取证
services/knowledge_business.py 功能验证、案例归档、版本化入库任务
services/observability.py 本地 Trace、Token/费用、反馈及可选 Langfuse 上报
vectorstores/          Qdrant、pgvector 适配层
vector_cli.py          数据库状态、指定文件录入、片段检索
workflow_cli.py        问答、恢复、验证、会话与统计、显式入库
compose.yaml           两套本地数据库
adapters/              Web 配置读取的预留适配层
workflows/             LangGraph 状态图、LangChain 提示词与扩展协议
evaluations/           固定问题集评测的扩展入口
documents/source/      原始部署资料
```

## 后续对接边界

1. 通过已认证的 Web API 获取集群列表和详情，提取不含凭据的配置摘要。
2. 按 `1.23.10 → Ubuntu/CentOS`、`1.32.8 → Ubuntu` 的支持范围选择适用资料。
3. 集群配置与实时运行状态分开采集并标注时间；在线/离线模式结合配置和任务记录确认。
4. 完善证据质量判断、混合检索和针对不同原故障的专项功能复测工具。
5. 增加固定问题集的批量评测、引用支持检查与不同配置的实验对比。
6. 按实际 GLM 计价配置 Langfuse 模型价格，再评估成本优化收益。

当前 API：`GET /api/health`、`GET /api/workspace`、`GET /api/documents`、
`GET /api/documents/{id}/download`、`POST /api/assistant/messages`；
`GET /api/clusters` 仍是 Web 集群适配的预留入口。

业务 API（公共前缀 `/api/assistant`）：`GET /sessions`、`POST /connections`、
`DELETE /connections/{connection_id}`、`GET /diagnostics/catalog`、`POST /diagnostics`、
`POST /verification`、`POST /feedback`、`GET /metrics`、`GET /index-jobs`、`POST /index-jobs/retry`。
`GET /api/evaluations` 返回本地真实 Trace 和统计，不是模拟列表。

向量 API：`GET /api/vector/status`、`POST /api/documents/ingest`、`POST /api/vector/search`。
录入请求必须指定 `file_path`，只处理该文件，不扫描整个目录。

当前交付是业务实现与本地可测试入口；真实 GLM、真实 SSH、知识库质量、Langfuse 远端上报和现场恢复，
必须分别运行对应路径后验证。默认启动不会证明这些外部功能已正常工作。
