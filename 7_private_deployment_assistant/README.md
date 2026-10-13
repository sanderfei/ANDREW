# 目录 7：私有化部署助手

基于 Web/KK 安装与运维场景的项目，提供 Web 界面、原始文档浏览下载，以及可切换的
Qdrant / PostgreSQL+pgvector 录入与片段检索接口。
Agent、最终答案生成、真实集群连接和 Langfuse 评测仍未接入。
模型仅用于显式录入和搜索时生成本地 Embedding，不调用付费聊天模型。

两套数据库的最简启动命令、配置切换、指定本地文件的录入接口见
[向量数据库使用说明](docs/vector-databases.md)。启动和录入由使用者执行，应用不会自动录入资料。

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

本次已确认：两套数据库均可连接，PostgreSQL 健康检查通过且 `vector` 扩展已启用，
Web 的 `/api/health`、`/api/workspace` 和 `/docs` 返回 200。
尚未录入文档，两个后端的 `chunks` 均为 0；集合和文档表在显式录入时创建。
`setup_local_databases.py` 会保留已有密码，数据库数据由 Docker 命名卷持久保存。

参数：`--host` 默认 `127.0.0.1`；`--port` 默认 `8070`。
例如：`.venv/bin/python 7_private_deployment_assistant/app.py --port 8071`。

## 当前界面

- 运维工作台：服务器地址草稿、集群上下文占位、会话创建与切换、问题输入。
- 知识文档：展示原始 DOCX、Markdown、TXT 文件，提供下载和录入接口文档入口。
- 评测实验：说明评测入口与指标，真实实验待接入。
- 会话和服务器草稿只保存在当前浏览器；清除浏览器存储后会丢失，尚无用户账号或跨设备同步。
- 发送问题会得到明确的“尚未接入”提示，不生成模拟诊断结论。清空会话需要在页面确认。

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
vectorstores/          Qdrant、pgvector 适配层
vector_cli.py          数据库状态、指定文件录入、片段检索
compose.yaml           两套本地数据库
adapters/              Web 配置读取的预留适配层
workflows/             LangGraph/RAG 的预留入口
evaluations/           Langfuse 评测的预留入口
documents/source/      原始部署资料
```

## 后续对接边界

1. 通过已认证的 Web API 获取集群列表和详情，提取不含凭据的配置摘要。
2. 按 `1.23.10 → Ubuntu/CentOS`、`1.32.8 → Ubuntu` 的支持范围选择适用资料。
3. 集群配置与实时运行状态分开采集并标注时间；在线/离线模式结合配置和任务记录确认。
4. 在已有密集向量检索基础上接入混合检索、LangChain、LangGraph 和回答生成。
5. 接入 Langfuse Trace、反馈和固定环境快照的质量评测。

当前 API：`GET /api/health`、`GET /api/workspace`、`GET /api/documents`、
`GET /api/documents/{id}/download`；`GET /api/clusters`、
`POST /api/assistant/messages`、`GET /api/evaluations` 仅提供明确的待接入状态。

向量 API：`GET /api/vector/status`、`POST /api/documents/ingest`、`POST /api/vector/search`。
录入请求必须指定 `file_path`，只处理该文件，不扫描整个目录。
