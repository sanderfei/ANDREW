# 目录 7：私有化部署助手

基于 Web/KK 安装与运维场景的项目，提供纯文本会话窗口、原始文档浏览下载、可切换的
Qdrant / PostgreSQL+pgvector 录入与检索，以及 LangChain / LangGraph 多轮排障工作流。
问答默认使用 `framework` 模式，只演示信息收集和流程分支，不调用聊天模型、Embedding 或向量数据库。
显式启用 `glm` 模式后，才运行真实检索与 GLM 分析；回答会区分追问、待补充证据与待验证方案。
已提供临时 SSH 授权与只读取证、功能复测确认、案例自动归档及可靠入库任务，
服务端会话和 LangGraph 检查点写入本地 SQLite。执行记录、反馈与 Token 统计始终启用，
Langfuse 远程上报由配置单独控制，仓库配置已开启；连接和认证状态可通过独立接口核验。

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

## 本地检索验证（2026-10-28）

已逐文件调用 `POST /api/documents/ingest`，将 1 份 DOCX、196 篇案例和 1 份覆盖范围说明录入本地 Qdrant，
共 198 份文档、604 个片段。集合为 `private_deployment_1d864d88e5`。只运行本地 MiniLM Embedding，
聊天模型调用数为 0；应用保持 `framework` 模式，本次启动临时关闭 Langfuse 上报。
DOCX 的正文和表格参与检索，50 张图片未执行 OCR。

首轮 30 条人工问题的结果如下。Hit@5 表示前 5 条包含已标注的主要相关文档，不是最终回答正确率。

| 方案 | Hit@1 | Hit@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| 原向量检索 | 46.67% | 24/30，80.00% | 0.5856 |
| 向量召回 20 条后按文档去重 | 46.67% | 25/30，83.33% | 0.6011 |
| 本地 BM25 | 90.00% | 30/30，100.00% | 0.9444 |
| 向量 + BM25 + RRF + 去重 | 83.33% | 29/30，96.67% | 0.9000 |

原 API 暖查询端到端 P50 为 50.39 ms。另以固定向量做独立消融，将查询前的全量统计替换为
轻量集合检查后，“检查 + 数据库查询”P50 从 15.29 ms 降至 4.12 ms，返回 ID 完全一致。
两者计量范围不同，不能把后者当作优化后的 API 端到端延迟。
这些是小型、来源衍生的探索问题，不能据首轮 BM25 全命中宣称真实请求普遍有 100% 成功率。

随后扩充为 **322 条唯一正例、24 条无答案观察题**，覆盖全部 198 份入库来源：保留原 30 题，
新增 269 题，另有 23 条环境过滤题。每题重复 3 次仅用于计时和稳定性，独立样本量仍是 322。
本次执行了 349 次 HTTP 检索、993 次本地候选查询，另有 10 次检查开销消融查询；六方案共享候选。

| 方案 | 扩展集 Hit@1 | 扩展集 Hit@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| 原向量检索 | 30.75% | 170/322，52.80% | 0.3820 |
| 向量召回 20 条后按文档去重 | 30.75% | 179/322，55.59% | 0.3987 |
| 本地 BM25 | 77.64% | 300/322，93.17% | 0.8364 |
| 本地 BM25 去重 | 77.64% | 301/322，93.48% | 0.8417 |
| 向量 + BM25 + RRF | 56.21% | 272/322，84.47% | 0.6637 |
| 向量 + BM25 + RRF + 去重 | 56.21% | 288/322，89.44% | 0.6849 |

原 30 题控制组的结果与首轮一致；扩大后的总分不能直接当作同一测试集上的回归。
扩展集显示：BM25 不再全命中；等权混合相对 BM25 去重丢 16 题、另救 3 题；混合按来源去重救回 16 题。
当前优先记录的优化项为：移出查询热路径的全量统计、复核多相关来源标签、保存完整候选与融合贡献、
评估来源聚合和融合权重、补充非模型术语归一化与少上下文问题的追问策略。均尚未替换业务算法。
扩展 API 端到端 P50/P95 为 49.32/61.01 ms；依然不等于进程内阶段计时。

[详细执行结果、扩展集对比与优化记录](docs/retrieval-evaluation/2026-10-28/README.md)
保留首轮数据并记录后续扩充结果。完整本地逐题输出位于 Git 忽略的 `reports/`；
文档目录保存脱敏后的汇总和可核验逐题结果。

```bash
# 默认运行首轮 30 题；只读检索，不调用聊天模型或向量入库。
.venv/bin/python 7_private_deployment_assistant/evaluations/retrieval_benchmark.py \
  --output-dir 7_private_deployment_assistant/reports/retrieval-repeat

# 扩展集：322条正例、24条观察题；详细结果按类别、问法、过滤和新旧题组拆分。
.venv/bin/python 7_private_deployment_assistant/evaluations/retrieval_benchmark.py \
  --questions 7_private_deployment_assistant/evaluations/data/retrieval_cases_expanded.json \
  --output-dir 7_private_deployment_assistant/reports/retrieval-expanded-repeat \
  --repeats 3 --candidate-k 20
```

混合召回、去重和 BM25 当前位于独立实验脚本，尚未替换业务检索接口。

## 当前界面

- 运维工作台：环境摘要、可展开的纯文本对话窗口、临时 SSH 连接与只读取证。
- 对话支持 Enter 发送、Shift + Enter 换行、粘贴日志、复制文本、失败重试和停止等待；支持会话切换和每个会话的输入草稿。
- 知识文档：展示原始 DOCX、Markdown、TXT 文件，提供下载和录入接口文档入口。
- 确认解决：提交明确根因、实际处理步骤与原故障功能复测证据，生成脱敏案例并排队入库。
- 执行与评测：展示本地真实执行记录、Token 汇总和用户反馈；已有独立纯检索批测，端到端回答质量和 Langfuse 实验仍待补充。
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

Langfuse 的仓库配置为 `[langfuse].enabled=true`，使用 SDK `4.15.4`，依赖中已包含
LangChain 回调所需的 `langchain`。从进程环境、教程 7 的 `runtime/local.env`、仓库根 `.env`
依次读取 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY` 和可选 `LANGFUSE_BASE_URL`；不把实际密钥写入 TOML。
`LANGFUSE_ENABLED=false` 可关闭远端上报，`LANGFUSE_TRACING_ENVIRONMENT` 可覆盖
`[langfuse].environment`，默认环境标识为 `andrew-private-deployment`。

```bash
.venv/bin/python -m pip install -r 7_private_deployment_assistant/requirements.txt
# 只查看配置和客户端初始化状态，不访问 Langfuse。
.venv/bin/python 7_private_deployment_assistant/workflow_cli.py langfuse-status
# 显式检查服务连接与项目认证；失败返回非零退出码。
.venv/bin/python 7_private_deployment_assistant/workflow_cli.py langfuse-status --check
```

`framework` 模式也可上报流程 Trace 和节点，仍不调用 GLM 或向量检索。GLM 模式的模型调用、
实际 usage 和用户反馈会关联到对应远端 Trace。Web“执行与评测”区分未启用、配置不完整、
已配置、认证通过和检查失败；只开启开关不会显示为已连接。SDK 使用异步批量上报，
关闭时执行 flush/shutdown；认证通过或 flush 完成不等于记录已经能在平台查询。

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
evaluations/           纯检索对比脚本、固定问题集及端到端评测的扩展入口
documents/source/      原始部署资料
```

## 后续对接边界

1. 通过已认证的 Web API 获取集群列表和详情，提取不含凭据的配置摘要。
2. 按 `1.23.10 → Ubuntu/CentOS`、`1.32.8 → Ubuntu` 的支持范围选择适用资料。
3. 集群配置与实时运行状态分开采集并标注时间；在线/离线模式结合配置和任务记录确认。
4. 完善证据质量判断、混合检索和针对不同原故障的专项功能复测工具。
5. 在已有纯检索批测基础上，增加端到端回答质量、引用支持检查与 Langfuse 实验对比。
6. 按实际 GLM 计价配置 Langfuse 模型价格，再评估成本优化收益。

当前 API：`GET /api/health`、`GET /api/workspace`、`GET /api/documents`、
`GET /api/documents/{id}/download`、`POST /api/assistant/messages`；
`GET /api/clusters` 仍是 Web 集群适配的预留入口。

业务 API（公共前缀 `/api/assistant`）：`GET /sessions`、`POST /connections`、
`DELETE /connections/{connection_id}`、`GET /diagnostics/catalog`、`POST /diagnostics`、
`POST /verification`、`POST /feedback`、`GET /metrics`、`GET /index-jobs`、`POST /index-jobs/retry`、
`GET /observability`。后者默认只查看状态，添加 `?check_connection=true` 才访问 Langfuse 检查连接与认证。
`GET /api/evaluations` 返回本地真实 Trace、统计和 Langfuse 状态，不是固定问题集的质量评测报告。

向量 API：`GET /api/vector/status`、`POST /api/documents/ingest`、`POST /api/vector/search`。
录入请求必须指定 `file_path`，只处理该文件，不扫描整个目录。

当前交付是业务实现与本地可测试入口；真实 GLM、真实 SSH、知识库质量、Langfuse 远端上报和现场恢复，
必须分别运行对应路径后验证。默认启动不会证明这些外部功能已正常工作。
