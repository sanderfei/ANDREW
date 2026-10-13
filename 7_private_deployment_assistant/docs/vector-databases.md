# 本地向量数据库与文件录入

当前代码提供两套后端：Qdrant、PostgreSQL + pgvector。两者共用本地 MiniLM、文档解析、切块和检索逻辑。
启动和资料录入由使用者执行，应用启动时不会自动启动数据库、创建索引或录入文件。
Agent、模型问答、Web 集群读取和 Langfuse 仍未接入。

## 最简启动命令

以下命令在 Andrew 仓库根目录执行，需要本机 Docker 和 Docker Compose。
若当前用户已有 Docker 权限，命令中的 `sudo` 可以省略。

```bash
.venv/bin/python -m pip install -r 7_private_deployment_assistant/requirements.txt
.venv/bin/python 7_private_deployment_assistant/setup_local_databases.py

# 同时启动两套数据库
sudo docker compose --env-file 7_private_deployment_assistant/runtime/local.env \
  -f 7_private_deployment_assistant/compose.yaml up -d
```

只启动其中一套时，最后一个命令改为：

```bash
# Qdrant
sudo docker compose --env-file 7_private_deployment_assistant/runtime/local.env \
  -f 7_private_deployment_assistant/compose.yaml up -d qdrant

# PostgreSQL + pgvector
sudo docker compose --env-file 7_private_deployment_assistant/runtime/local.env \
  -f 7_private_deployment_assistant/compose.yaml up -d pgvector
```

| 服务 | 本地入口 | 持久数据 |
| --- | --- | --- |
| Qdrant | `http://127.0.0.1:6333`，管理界面 `/dashboard` | Docker 命名卷 `qdrant_data` |
| PostgreSQL + pgvector | `127.0.0.1:5433` | Docker 命名卷 `pgvector_data` |

Compose 项目名为 `andrew-private-vectors`，实际卷名带该项目前缀。
数据库密码由准备脚本生成到 Git 忽略的 `runtime/local.env`，重复准备保留原密码，脚本不会打印凭据。
PG 镜像自带 pgvector；首次初始化通过 `database/001-vector.sql` 启用扩展，显式录入时也会确认扩展和表存在。
Qdrant 使用固定镜像 `v1.19.2`；PG 使用官方 `pg17` 系列镜像。

```bash
# 查看状态
sudo docker compose --env-file 7_private_deployment_assistant/runtime/local.env \
  -f 7_private_deployment_assistant/compose.yaml ps

# 停止服务并保留数据卷
sudo docker compose --env-file 7_private_deployment_assistant/runtime/local.env \
  -f 7_private_deployment_assistant/compose.yaml down
```

参考：[Qdrant 本地部署](https://qdrant.tech/documentation/quickstart/)、
[pgvector 官方 Docker 说明](https://github.com/pgvector/pgvector#docker)。

## 切换数据库

修改目录 7 的 `config.toml`：

```toml
[vector_store]
backend = "qdrant" # 或 "pgvector"
namespace = "private_deployment"
```

接口每次请求读取配置，下一次请求即可使用新后端。
两个后端的数据独立；切换不自动搬迁或同步数据，需要分别调用录入接口。
模型名称和向量维度参与实际命名空间计算，避免不同模型的向量混用。

当前使用本地 `paraphrase-multilingual-MiniLM-L12-v2`，384 维。
默认复用前面教程的模型缓存；新电脑没有模型时，首次显式录入或检索可能下载模型。
模型路径和缓存目录可在 `[embedding]` 中调整。更换模型需要重新录入。

## 指定本地文件录入

先启动应用：

```bash
.venv/bin/python 7_private_deployment_assistant/app.py
```

打开 <http://127.0.0.1:8070/docs>，使用 **POST `/api/documents/ingest`**。
也可以运行：

```bash
curl -X POST http://127.0.0.1:8070/api/documents/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "file_path": "documents/source/未来企业事业群—私有化安装集成站台.docx",
    "metadata": {
      "title": "私有化在线与离线安装参考",
      "kubernetes_versions": ["1.32.8"],
      "operating_systems": ["Ubuntu"],
      "install_modes": ["online", "offline"]
    }
  }'
```

metadata 是适用条件的填写示例，实际版本和系统应由使用者按原文确认。
不指定 metadata 时，版本和系统为 `any`，表示没有设定版本限制，而不是已经证明支持所有版本。
检索过滤保留 `any` 资料，最终适用性判断仍需结合原文和环境。

- 支持 `.docx`、`.md`、`.txt`；DOCX 提取正文和表格，当前不处理截图 OCR、PDF 或 HTML。
- 相对路径以目录 7 为基准；绝对路径必须是运行后端的机器上可读取的路径。
- 默认只允许 `documents/source` 中的文件；其他本地目录需在 `[ingestion].allowed_roots` 中添加。
- WSL 中的 Windows 文件路径写作 `/mnt/c/Users/...`，不能直接传 `C:\\Users\\...`。
- 重复录入同一文件会替换该文件原有片段，其他文件保留；原始文件不会被修改。
- 配置的 `chunk_size=800`、`chunk_overlap=120` 是字符数；跨正文块不强制重叠，超长块才使用重叠切分。
- 基本密码、Token、私钥和 URL 凭据模式会在提取后脱敏，但资料入库前仍应人工检查。
- 可在原文件旁放置 `<文件名>.metadata.json`；接口 metadata 会覆盖同名字段。

如需读取桌面目录，可显式调整：

```toml
[ingestion]
chunk_size = 800
chunk_overlap = 120
allowed_roots = ["documents/source", "/mnt/c/Users/oswangfei/Desktop"]
```

CLI 同样需要明确指定文件，不会批量扫描和自动录入：

```bash
.venv/bin/python 7_private_deployment_assistant/vector_cli.py status
.venv/bin/python 7_private_deployment_assistant/vector_cli.py ingest "documents/source/未来企业事业群—私有化安装集成站台.docx"
```

## 检索和状态

```bash
curl http://127.0.0.1:8070/api/vector/status

curl -X POST http://127.0.0.1:8070/api/vector/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "离线安装之前要准备哪些内容？",
    "top_k": 5,
    "kubernetes_version": "1.32.8",
    "operating_system": "Ubuntu",
    "install_mode": "offline"
  }'
```

返回的是原文片段、来源定位、metadata 和余弦相似度，不生成最终答案，也不把相似度当成正确率。
当前实现密集向量检索；BM25、混合检索和重排留待后续质量优化。

```bash
# 临时指定后端检查状态或检索，不改配置文件
.venv/bin/python 7_private_deployment_assistant/vector_cli.py --backend qdrant status
.venv/bin/python 7_private_deployment_assistant/vector_cli.py --backend pgvector status
.venv/bin/python 7_private_deployment_assistant/vector_cli.py search "离线安装准备" --k8s 1.32.8 --os Ubuntu --mode offline
```

## 资料越多越好吗？

有效覆盖比总量重要。资料增加可以补足问题覆盖，但重复、过时、版本不明或相互冲突的资料会干扰检索。
正文提取丢失表格、截图中的命令或前置条件，也会降低质量；向量数据库无法补回未提取的内容。

优先加入与 Web/KK 当前版本相关、能定位来源、解决步骤经过确认的资料。
对相同内容去重，保留版本标签和验证状态，按一批固定真实问题评估每次新增资料的影响。
原始文件留在本地不等于检索能使用其中全部信息：只有成功提取、切块并录入的内容才参与检索。
