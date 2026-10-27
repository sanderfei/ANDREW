# OBS-28：V3版本目录一键下载并导入集群数据与镜像的串行任务

项目：g_web_installer。记录日期：2026-10-26。记录状态：本地实现及定向验证通过，未提交发布；真实导入待验证。

适用环境：Web 本地 `release` 工作区，基线 HEAD 为 `5f148d0`，实现尚未提交、推送或部署。本轮从方案讨论进入后端编码，完成本地源码及模拟链路验证，没有调用真实 OBS、离线 Zot 或数据库。路径相对于 Web 服务工作目录；宿主机与容器部署需按实际挂载核对，数据库组件、工具和连接参数仍须匹配现场。未修改前端实现。

## OBS-28 问题与最终选择

用户希望在 OBS V3 的版本目录增加“导入到集群”能力：选择已有集群后，把版本直属文件中的镜像包、数据包下载到该集群目录，自动完成镜像入离线仓库和数据导入。XLSX、PDF 等资料跳过，缺某类包就不执行该类导入。

曾讨论并行业务、子日志落盘后按编号归并的备选；用户认为复杂，明确放弃。最终实现采用一个总 PID、一个 `execute.log`，内部全部顺序串行，没有新增 `progress.log`、`tasks/` 子日志或归并器。外层后台异步受理与内部顺序执行分别处理。

相关已有案例为 [OBS-22：本地镜像导入迁移 V1 并按集群归档任务日志](OBS-22.md) 和 [WEB-17：PID WebSocket 结束通知与自动衔接](../05_Web配置鉴权与任务/WEB-17.md)。本次新增后端版本任务，不把旧接口或历史现场证据视为本功能已上线。

## OBS-28 接口、权限与受理边界

已在本地增加路由、handler、request/reply 及错误映射；API 尚未部署：

```http
POST /api/v3/obs/folder/version/import
Content-Type: application/json
```

```json
{
  "path": "安装包仓库/知识智能/1.6.7/",
  "cluster": "cluster-a"
}
```

`path` 是完整 OBS 版本目录前缀，规范为一个末尾 `/`；`cluster` 必须是已有真实 `config.yaml` 的单级集群名，拒绝斜杠、冒号、控制字符等非法名称。不接受任意本地目标路径、数据库账号或目标仓库覆盖参数。复用有效 Web JWT、Ops 身份及 V3 IAM 会话，实时读取当前用户 OBS 目录权限，按 `all` 或匹配的顶层目录授权；普通目录授权不扩展到 `config/`。

受理成功沿用标准 `code/msg/data`：

```json
{"code":10000,"msg":"OK","data":{"success":true,"pid":"<本次总任务PID>"}}
```

`success: true` 只表示后台任务已受理，不代表下载或导入完成。同步坏参数为 400，目录无权限为 403，集群不存在为 404，同集群本入口正执行为 409；JWT/IAM 会话错误沿用 V3 认证规则，返回受理结果前的同步元数据超时可映射 504。扫描歧义、下载或导入失败可能发生在受理后，只在该 PID 日志报告，不会追改已经返回的 HTTP 状态。

## OBS-28 文件识别与串行流程

后端使用 `ListAll(prefix)` 完整分页，随后只保留前缀内的直属文件，排除目录标记、子目录及相邻版本；可处理文件按文件名稳定排序。先检查去掉完整压缩扩展名后的末尾 `_数据库标识`，大小写不敏感，不以任意子串猜测类型：

| 数据标识 | 内部类型 | 现有压缩格式 |
|---|---|---|
| `Mysql`、`MariaDB` | `mysql`、`mariadb` | `.zip` |
| `PostgreSQL` | `postgresql` | `.zip` |
| `MongoDB` | `mongodb` | `.tar.gz` |
| `Elastic`、`ElasticSearch` | `elastic` | `.tar.gz` |
| `StarRocks` | `starrocks` | `.tar.gz` |

例如 `1.6.7_ElasticSearch.tar.gz`、`1.6.7_MongoDB.tar.gz`、`1.6.7_Mysql.zip` 分别进入对应数据导入。命中数据库后缀但压缩格式不符、同一数据库出现多个数据包时停止并报告错误，不推断分片或覆盖顺序。未命中数据库的 `.tar`、`.tar.gz`、`.tgz` 仅为镜像候选，仍须通过内容预检；未识别 ZIP、XLSX、PDF 等文件跳过且不下载。

识别细节（2026-10-26 只读澄清）：`classifyObsVersionPackage` 先限制扩展名为 `.zip`、`.tar.gz`、`.tgz`、`.tar`，其中 `.tar.gz` 作为完整后缀去除；随后仅取剩余文件名最后一个下划线后的 token，忽略大小写匹配表中数据库，前面的版本号、日期不参与分类。数据库标识必须位于去压缩扩展名后的末尾，例如 `v_Mysql_backup.zip` 的末尾 token 是 `backup`，因此作为未知 ZIP 跳过；`v_Mysql.tar.gz` 则已命中数据库但扩展不符，报告错误。未知 tar/tar.gz/tgz 只是镜像候选，若内容不是受支持的 Docker-save 或 bundle，预检失败并停止，不能扫描包内 SQL/BSON 来猜数据库类型。本次仅解释当前规则，没有修改业务代码或重新运行测试。

```text
扫描、识别直属文件（集群与权限在受理前校验）
  → 逐包下载
  → 全部包格式及数据组件预检
  → 全部镜像逐包导入
  → 全部数据逐包导入
  → 执行汇总及一次总终态
```

每一步真正结束才进入下一步，所有下载与全部预检均先于本次仓库/数据库写入。缺镜像或数据包时记录跳过；全部无包时明确记录“无可处理包，本次没有执行镜像或数据导入”，以 no-op 结束，不能把该总任务结束解释为已导入数据。

目录按集群与本次 PID 隔离：

```text
data/cluster/<cluster>/obs-import/<PID>/packages/<原文件名>
data/cluster/<cluster>/obs-import/<PID>/work/
data/cluster/<cluster>/history/<PID>/execute.log
```

下载原包保留，不覆盖集群根目录的旧固定包名。预检为镜像和数据创建私有工作副本，后续导入读取已检副本，避免重新打开不同内容；总流程结束时清理 `work/`，保留 `packages/` 原包。任一步失败即停止后续并记录已完成数量，已导入镜像或已写入数据保留，不自动回滚或重试数据库；重复导入可能覆盖数据。

镜像目标沿用当前本地镜像导入的固定 444 端口离线 Zot，认证由后端提供；`cluster` 决定数据目标、下载目录和日志归属，不自动改用该集群的其他仓库。它与 `apps/:cluster/images/push` 的应用镜像流程分别处理。本功能没有新增 NFS 前置条件。

## OBS-28 PID、取消、互斥与导入核心

只有最外层调用一次 `ExecuteAsync`，总 PID 增加随机尾；内部下载、镜像和数据核心均同步等待，不调用会返回另一个 PID 的高层异步 API，也不解析日志猜成功后启动下一步。日志通过现有 WebSocket 实时读取：

```text
GET /api/v1/logs/cluster/<cluster>/tail/<pid>/execute.log
```

阶段、文件名、单包完成、汇总与唯一总成功/失败写入同一文件。HTTP 请求结束或浏览器关闭不取消后台流程，后台 context 脱离请求取消并使用总异步超时，每个文件另有传输超时。WebSocket 重连和日志回放只用于展示，不负责重复触发业务。

本入口在集群目录使用专用 `.obs-version-import.lock`、非阻塞 `flock`，约束同集群的新版导入任务并返回 409。锁只约束本入口，旧手动导入或其他写路径没有因此共同互斥，不能声称已排除所有共享数据库冲突；旧 `LockOwner` 的注释锁逻辑也没有被恢复。新数据核心不再使用共享 `/tmp/mongo_dump`。

镜像核心 `obs_version_images.go` 根据魔数处理 gzip，并完整读取校验 CRC、tar 结构、安全成员路径、`manifest.json`/`RepoTags` 和层引用；bundle 中每个内层 Docker-save tar 也预检。导入复用 `common` 的带 context 仓库复制能力。结构预检不验证镜像 config 的全部业务字段或层 digest，实际推送仍可能因内容、认证或仓库条件失败。

数据核心 `PrepareArchiveImport` / `Run` 接受显式包路径及工作目录，不创建子 PID。预检包含 ZIP/tar 完整读取、CRC、安全路径和相应 SQL 文件、JSON/BSON、PostgreSQL、StarRocks 原格式规则，并通过带连接、握手和命令超时的 context SSH 做只读组件校验；这些检查不证明 SQL 业务语义或目标库导入已成功。Elasticsearch 继续沿用现有 elasticdump JSON 及脚本的 7.15.0 边界，不把 snapshot 当成同类包。

新 MySQL/MariaDB、MongoDB 路径使用严格脚本，解包和数据库命令错误向上传递；MongoDB 使用私有临时目录，并检查本机 `mongorestore --help` 支持 `--config` 与 `--stopOnError` 后执行。ES、PostgreSQL、StarRocks 复用参数化生成器。凭据经 stdin 传入，日志 writer 对跨多次 write 的敏感值脱敏；取消时杀死并等待整个命令进程组，日志 flush 错误计入失败。

旧单独数据接口的 MySQL/Mongo 宽松脚本仍保留，包括历史忽略解包错误、`mysql --force` 或 `mongorestore ... || true` 等边界；本次不能描述为所有旧导入入口已经修复。新路径仍有 `--drop` 等覆盖语义，失败重跑前需要结合日志与实际数据判断已完成步骤。

## OBS-28 本地验证与证据边界

开发阶段已通过以下定向验证，测试使用本地模拟网关、仓库动作、数据库命令和生成脚本，不代表真实环境功能恢复：

- 镜像归档临时定向测试覆盖结构预检；没有执行真实离线仓库推送。
- 六类数据 archive 验证，以及真实生成 shell 配合 mock 命令的失败传播、取消、凭据脱敏和语法检查通过；未执行真实数据库恢复。
- 总流程模拟网关覆盖分页、相邻版本/子目录隔离、跳过资料、下载及所有预检先于导入、镜像优先、预检或首镜像失败停止、原包保留、私有工作目录清理。
- HTTP 请求结束后后台继续、同集群重复锁拒绝、单 PID、handler 的 400/403/404/409 与标准 200 包装通过。本地现有 WebSocket 在后台 OBS 列表阻塞、任务尚未结束时已读取到 `execute.log`，随后读取到 no-op 总终态；这是本地实时日志证据。

```bash
CGO_ENABLED=1 go test -race -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./internal/service/file_server ./internal/service/importdata -run '^(TestObsVersion|TestArchiveReview)' -count=1
CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o <临时目录>/server ./cmd/server
```

上述 race 定向测试及 server 构建通过；最终源码又完成同 tags 的 server 构建，12 个本轮 Go 文件的 `gofmt -l` 为空，`git diff --check` 通过。临时二进制目录精确清理，所有本轮临时测试文件按用户约定在通过后删除。忽略文件 `swag.json` 已增量保留原接口并新增本接口，现为 14 条路径、19 个定义，最终再次校验 JSON 及 46 个定义引用通过；未修改 `.gitignore`。

真实 OBS/IAM 权限、固定 Zot 推送、六类真实数据库导入尚未验证，当前开发宿主机还缺少 `mongorestore`、`unzip` 等实际运行依赖；mock 不能替代工具版本和真实数据验证。业务代码未提交、推送、发布或重启服务，没有现场功能证据，metadata 保持 `unverified`。

后续部署与验证须按明确授权执行：准备符合格式的版本目录、目标集群组件和客户端工具，以有效会话受理后跟踪该 PID 的总终态，再检查目标仓库 manifest/可用镜像和目标数据库数据或业务查询。测试失败、部分写入、旧手动入口并发及重复导入的影响仍应结合现场判断，不能仅凭 HTTP 200、日志文件存在、编译或服务启动宣称整版恢复成功。

## OBS-28 来源定位

- `g_web_installer/internal/transport/router.go:193`；`internal/transport/handler/obs_v3_version_import.go:14`；`internal/transport/handler/obs_v3_middleware.go:138`。
- `internal/model/request/obs.go:51`；`internal/model/reply/obs.go:65`；根目录本地 `swag.json`。
- `internal/service/file_server/obs_v3_version_import.go:35`（受理、权限、异步 context）、`:109`（专用锁）、`:131`（计划）、`:175`（后缀映射）、`:222`（串行流程及清理）、`:346`（下载与传输超时）。
- `internal/service/file_server/obs_version_images.go:30`（私有预检副本）、`:96`（同步推送）、`:122`、`:228`、`:268`（tar、manifest、bundle 校验）。
- `internal/service/importdata/archive_import.go:44`（准备）、`:180`（等待与取消）、`:225`（私有副本）、`:273`（SSH context）、`:322`、`:352`、`:401`（格式校验）、`:566`（日志脱敏）、`:627`、`:675`（严格脚本）。
- `internal/service/importdata/importdata.go:57`（组件校验）、`importdataV2.go:92`、`:406`（参数化 ES）、`:535`、`:628`（旧脚本边界）；`postgresql.go`、`starrocks.go:83`（复用生成器）。
- `internal/service/image_gateway/client.go:236`（前缀分页）；`internal/service/file_server/obs_executor.go:44`、`:60`、`:95`（异步受理、日志归属与统一终态）。
- `internal/transport/handler/log.go:28`；`internal/service/log/tail.go:69`（现有 PID WebSocket）。
- 本轮本地模拟链路、脚本、HTTP/WebSocket、race 定向测试、构建与 Swagger 校验结果；未保存原始会话、完整日志或实际认证值。

[返回案例索引](../README.md)
