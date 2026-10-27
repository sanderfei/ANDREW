# OBS-22：本地镜像导入迁移V1并按集群归档任务日志

项目：g_web_installer。记录日期：2026-10-19。记录状态：代码已验证；121 编译、替换和启动命令已完成，接口功能未现场验证。

适用环境：Web `test` 分支，基线提交 `e901e0f2ff06cb0fe840dec0db17b7ddc0f6b384`，本次提交 `53f55142e7fa9e1577d8c16f6b9be6961b6611c3`；已同步个人和中央仓库 `test`，121 按同一提交构建并执行启动。Web 为独立后端进程，运行数据相对于服务工作目录，源包仍为 `data/obs/local/`，目标为后端固定的离线 Zot。此项不依赖 Kubernetes 版本或集群内组件状态。旧 V3 在 214 的历史功能证据见 [OBS-21](OBS-21.md)，不能替代本次 V1 改动的现场验证。

## OBS-22 问题表现

原接口注册为 `POST /api/v3/registry/images/import`，请求体为 `[{"path":"相对路径"}]`。用户要求迁到 V1，改为一个对象携带集群名和本地路径数组，任务 PID 日志写入对应集群的 `history`。原日志位于 `data/obs/history/<pid>/execute.log`，无法从指定集群的日志路径读取。

## OBS-22 问题原因与证据

- 原 handler 绑定 `[]request.ImportLocalImagesV3Request`，并从 V3 中间件取 `ObsV3Context`；直接迁入 V1 会缺少这一上下文。
- 原导入服务创建 `NewObsExecutor("obs", "registry_import", ...)`，没有接收集群名。
- `internal/service/file_server/obs_executor.go` 的 `prepareExecution` 原先固定使用 `data/obs/history`，`OwnerType`、`OwnerName` 只用于日志内容，不影响落盘目录。
- 已有 V1 日志接口为 `GET /api/v1/logs/:owner_type/:owner_name/tail/:pid/:file`，通过 WebSocket 读取 `data/<owner_type>/<owner_name>/history/<pid>/<file>`；因此归档到集群后可复用原有日志接口。

以上问题定位来自本地源码；后续本轮仅连接 121 发布 Web，未连接 214、215，发布命令证据见后文。

## OBS-22 修复方案与可执行步骤

已在本地实现：

1. 路由迁为 `POST /api/v1/registry/images/import`，移除旧 V3 注册和对应的 V3 中间件例外。
2. 请求模型改为 `ImportLocalImagesV1Request`。`cluster` 必填且必须为单级目录名，拒绝空白、点目录、斜杠、反斜杠和 NUL；`path` 为非空字符串数组。字段名为 `cluster`，末尾不带冒号。
3. handler 从现有 V1 JWT 上下文读取用户信息，直接传入请求 context，不再要求 OBS 网关上下文、IAM 会话或 OBS 用户身份。
4. 导入执行器归属改为 `cluster/<cluster>`；执行器仅对 `OwnerType == "cluster"` 写入 `data/cluster/<cluster>/history/<pid>/execute.log`，其他 OBS 操作仍沿用原路径。
5. 保留整批文件预检、占用锁、顺序导入、单包失败后继续、汇总终态、源包保留和临时文件清理；后台任务仍不随 HTTP 请求结束取消，超时仍为 12 小时。
6. 更新根目录 `swag.json`。为同时描述 V3 下载/列表和 V1 导入，`basePath` 改为 `/api`，各路径分别带 `/v3` 或 `/v1`；保留工作区中已有的下载/列表文档修改。

发布包含该改动的 Web 后，先确认所选源包已存在于服务本地 `data/obs/local/`，再以有效 Web JWT 调用：

```http
POST /api/v1/registry/images/import
Content-Type: application/json
Authorization: Bearer <当前有效的Web JWT>
```

```json
{
  "cluster": "test",
  "path": [
    "中间件/4.38.2/IAM/iam_4382_1006.tar",
    "制造部门/产品A/v1.0/images.tgz"
  ]
}
```

`path` 是相对于 `data/obs/local/` 的文件路径，不是 HTTP 下载 URL。数组中的文件必须全部存在且未被其他下载/导入任务占用，否则任务不启动。示例路径需替换为现场真实存在的文件。

接口沿用 `code/msg/data` 响应包装，`data` 含 `success` 和 `pid`；`success: true` 只表示已受理。使用同一个集群名和响应 PID，通过 WebSocket 订阅：

```text
GET /api/v1/logs/cluster/test/tail/<pid>/execute.log
```

日志实际路径为 `<Web工作目录>/data/cluster/test/history/<pid>/execute.log`。读取导入汇总和成功/失败终态后，再核验目标镜像 manifest；不能把任务创建成功视为镜像导入完成。

## OBS-22 验证结果与遗留事项

本地验证命令均退出 0：

```bash
CGO_ENABLED=0 go test -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./internal/service/file_server ./internal/transport -run TestV1RegistryImport -count=1

CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o /tmp/gweb-v1-registry-import-dxx33zsf/server ./cmd/server
```

- HTTP 行为测试使用真实路由：无 JWT 返回 401；旧 V3 路由返回 404；旧数组请求、缺失/无效集群和错误的 path 类型返回 400；缺失文件返回 404。普通本地 JWT 无需 OBS 用户字段即可创建 V1 任务。
- 使用本地 `httptest` 镜像仓库和生成的两个 Docker-save 包验证双包导入成功；核对目标 manifest 可读、镜像配置摘要保留、源包保留、文件锁释放，导入日志仅写到指定集群路径。镜像归档转换可能重新压缩 layer，因此不以源镜像 manifest digest 完全相同作为验证条件。
- 首包使用损坏的归档、第二包使用有效归档，确认第二包仍成功导入，最终汇总为 `total=2 success=1 failed=1`，整批终态为失败。
- 已取消的请求 context 不取消后台导入；无效批次启动前失败且释放此前的源文件锁。其他 OBS 操作的日志仍写入原 OBS history。
- Swagger JSON、引用、V1 请求 schema 和原 V3 下载/列表内容保留检查通过；Go 格式和 `git diff --check` 通过。
- 新增临时测试已在通过后删除，测试生成的本地 JWT 文件也已清理。

开发验证阶段仅进行了本地测试与构建；后续 `test` 提交推送及 121 发布记录见下文。没有访问真实 Zot、OBS 或集群。新 V1 接口和日志 WebSocket 的现场验证仍待执行，元数据继续为 `unverified`；不把模拟仓库结果、编译或启动命令通过写成功能恢复。

## OBS-22 test 提交与 121 发布补充（2026-10-19）

用户明确要求仅更新 `test`，其他分支不动，覆盖默认的 release 交付分支约定。此前发布 121 的授权继续适用，本次仅发布 Web，不发布 KK。

- 提交为 `53f55142e7fa9e1577d8c16f6b9be6961b6611c3`，标题 `fix: move local image import to v1 cluster history`，共 8 个文件。Swagger 只提交本次接口契约相关调整，保留原有 28 个操作路径；本地此前未提交的 Swagger 精简/整理继续留在工作区，未随本次提交推送。
- 依次推送个人仓库 `wangfei/g_web_installer` 的 `refs/heads/test` 和中央仓库 `Installation-package/g_web_installer` 的 `refs/heads/test`，两者均从 `e901e0f` 快进到本次提交。随后 `git ls-remote --heads` 核对两个远端 `test` 均等于上述完整 SHA；中央 `release` 仍为 `0fdbf8b44a3f32666dcdf85ea1783deee1f7abca`，没有写入 release 或创建 release PR。此次为直接提交的 test 分支快进交付，没有额外创建合并提交。
- 固定使用 `ssh codex-test-121`，工作目录 `/root/wfweb/g_web_installer`，保留 `configs/users.json`、`data` 和后端专用的 `router.go` 调整。更新前确认该路由文件仅移除 Vue import 与 `vue.ServeVue`；暂时恢复该文件以拉取，更新后在最新源码上重新应用这两行调整。
- 仓库同时有名为 `test` 的分支和标签。首次短引用拉取选中了标签，未更新工作分支，后续改用 `git pull --ff-only origin refs/heads/test`，实际快进成功并核对 HEAD 等于中央 test 的本次提交。准备脚本曾因 121 的 Python 3.6 不支持 `capture_output` 而提前退出，改用兼容写法后完成；这些错误均发生在停止旧服务之前。
- 使用登录 Shell 执行规定的 `CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o server.next ./cmd/server`，成功后 `mv -f server.next server`，命令退出 0，直接输出 `WEB_BUILD_AND_REPLACE_OK`。发布阶段没有重复执行测试。
- 只执行一次 `ss -lntp 'sport = :8080'`，定位旧 PID `692339`；同一次归属核对确认 cwd 为 `/root/wfweb/g_web_installer`、exe 为该目录的 `server (deleted)`，随后 `kill -9` 并立即运行 `/root/wfweb/web_start.sh`。启动命令退出 0，脚本直接输出 `server started, pid=757425`。

按照用户发布约定，没有追加版本/二进制哈希检查、接口探测、日志关键字匹配、多轮进程/端口验证或自动回退。PID `757425` 为启动脚本报告值，编译/替换/启动成功仅是本次发布命令证据，不是 V1 导入功能或进程持续健康的证明。原本地功能测试通过结论保持不变；案例元数据仍为 `unverified`。

仅在 andrew 更新本地案例和索引状态，没有提交、推送该仓库文档，也未向向量库录入。

## OBS-22 来源

- `g_web_installer/internal/transport/router.go`、`internal/transport/handler/obs_v3_local_import.go`、`internal/transport/handler/obs_v3_middleware.go`。
- `g_web_installer/internal/model/request/obs.go`、`internal/model/reply/obs.go`。
- `g_web_installer/internal/service/file_server/obs_v3_local_import.go`、`internal/service/file_server/obs_executor.go`、`internal/transport/handler/log.go`。
- 本轮本地临时 HTTP/模拟仓库行为测试、服务构建及 Swagger 校验结果。

[返回案例索引](../README.md)
