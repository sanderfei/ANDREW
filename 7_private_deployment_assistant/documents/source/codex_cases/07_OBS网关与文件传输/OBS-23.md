# OBS-23：本地文件列表迁到V1并支持批量删除

项目：g_web_installer。记录日期：2026-10-19。记录状态：代码已验证；test 提交已同步，121 编译、替换和启动命令已完成，接口功能未现场验证。

适用环境：Web `test` 分支，基线提交 `53f55142e7fa9e1577d8c16f6b9be6961b6611c3`，本次提交 `e982a0f51e557d00caf4e6d66c7cc5820314eba2`。本地文件根目录为 `<Web工作目录>/data/obs/local/`。开发阶段只操作临时目录；后续按用户明确要求将 test 发布到 121，未连接 214、215。关联背景见 [OBS-22](OBS-22.md)：镜像导入已经迁到 V1，日志归属集群 history；本案例只覆盖本地列表和删除。

## OBS-23 问题表现

原列表接口为 `GET /api/v3/obs/file/local/list`，挂在 V3 OBS 中间件下，要求 JWT 中有 OBS 用户身份字段 `userId/userCn`。用户要求改用 V1 鉴权，并新增本地文件批量删除接口。

用户进一步明确：删除不考虑并发，文件报错就立即返回，接口同步返回执行结果，不需要 PID。

## OBS-23 问题原因与证据

- `internal/transport/router.go` 原先把本地列表注册到 V3 分组，`ObsV3Middleware` 即使不要求 IAM 网关会话，也会先要求非空的 `userId/userCn`。
- 列表服务本身只读取本地目录，不使用 OBS 网关、IAM 或 OBS 用户身份；可直接复用 V1 分组的 `JWTAuthMiddleware`。
- 删除复用本地相对路径解析，使用 `os.OpenRoot` 约束删除根目录；按用户要求，不接入下载/导入的路径占用锁表。
- 列表使用 `os.OpenRoot` 和 `fs.WalkDir`，递归返回按相对路径排序的正式普通文件；临时文件、临时解包目录、符号链接和特殊文件不列出。

以上为本地源码和临时目录行为测试证据，不代表真实客户文件或已部署服务已验证。

## OBS-23 修复方案

已在本地实现：

1. 列表迁为 `GET /api/v1/obs/file/local/list`，移除旧 V3 列表路由及其中间件例外，handler/service/model 对应改为 V1 命名。无参数，返回原有 `[{"path":"相对路径"}]`；目录不存在或为空时返回 `[]`，不创建目录。
2. 新增 `POST /api/v1/obs/file/local/delete`，使用 V1 JWT，普通本地登录即可调用，不要求 OBS 用户字段或 IAM 会话。
3. `path` 为非空字符串数组，路径相对于 `data/obs/local/`；按数组顺序逐个解析、校验并删除，不做整批文件预检或并发占用检查。
4. 当前路径越界、文件缺失、是目录或符号链接、属于特殊文件或临时条目，或者读取/删除失败时，立即返回当前错误，不再处理后续项。此前已删除的文件不回滚；重复路径在第二次处理时会因文件已删除而返回不存在。
5. 通过 `os.Root.Remove` 删除选中的普通文件，保留父目录。允许删除零字节普通文件；只使用 `docker_archive_bundle_` 前缀但属于普通文件的条目仍可删除，临时解包目录及其内容不可删除。
6. 全部成功时同步返回 `success: true` 和实际 `deleted` 路径，不创建后台任务或 PID。文件错误直接通过错误响应返回，不聚合失败项或继续后续文件。
7. 根目录 `swag.json` 同步迁移列表路由并补充删除请求、响应、认证与错误码，同时保留工作区已有的文档整理。

## OBS-23 可执行调用步骤

使用有效 Web JWT 请求本地列表：

```http
GET /api/v1/obs/file/local/list
Authorization: Bearer <当前有效的Web JWT>
```

成功响应示例：

```json
{
  "code": 10000,
  "msg": "OK",
  "data": [
    {"path": "中间件/4.38.2/IAM/iam_4382_1006.tar"},
    {"path": "制造部门/产品A/v1.0/images.tgz"}
  ]
}
```

选择确实需要删除的文件，将各项 `path` 字符串组成数组；删除请求不需要 `cluster`：

```http
POST /api/v1/obs/file/local/delete
Authorization: Bearer <当前有效的Web JWT>
Content-Type: application/json
```

```json
{
  "path": [
    "目录/a.tar",
    "目录/b.tgz"
  ]
}
```

示例路径需替换为实际选中的本地文件。全部成功时返回：

```json
{
  "code": 10000,
  "msg": "OK",
  "data": {
    "success": true,
    "deleted": ["目录/a.tar", "目录/b.tgz"]
  }
}
```

路径或文件类型错误返回 HTTP 400，缺失文件返回 404，读取/删除失败返回 500，均在当前项报错后立即停止。列表为 `["a.tar", "missing.tar", "b.tar"]` 时，若 a 存在、missing 不存在，则 a 已删除、立即返回 missing 的错误，b 保留。操作后可重新列举本地文件核对实际状态。

## OBS-23 验证结果与遗留事项

以下本地命令退出 0：

```bash
CGO_ENABLED=0 go test -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./internal/service/file_server ./internal/transport -run TestLocalFilesV1 -count=1 -v

CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o /tmp/gweb-local-files-v1-p3na5nzu/server ./cmd/server
```

- 真实路由测试确认 V1 列表和删除无 JWT 返回 401；仅含本地用户名、没有 OBS 用户字段的 JWT 可调用；旧 V3 列表路径返回 404。
- 临时目录验证列表排序、空目录行为及临时条目过滤；批量删除后只保留未选中文件和父目录，零字节文件可删除，目录外的符号链接目标保持存在。
- 缺失文件位于第二项时，第一项已删除，第二项立即返回错误，第三项保留；HTTP 真实路由也验证了相同行为。
- 越界、目录、符号链接和临时文件拒绝删除，目录外文件保持存在。
- 使用只读父目录模拟真实权限错误，确认立即返回删除错误，第三项仍存在，此前完成的第一项保持已删除。
- 成功响应只含 `success/deleted`，没有 `pid`；错误响应同样不返回后台 PID。
- Swagger JSON、引用和 V1 路由校验通过，下载与镜像导入操作文档保持本轮开始时内容。

已按最终简化实现重新运行上述行为测试和服务构建，均退出 0。新增临时测试在通过后删除，测试生成的本地 JWT 文件也已清理；没有为最终删除实现执行并发检查。所有测试均仅操作本地临时目录，没有删除真实运行数据。随后按用户要求完成 test 提交和 121 发布，具体证据见下文；列表与删除接口仍未进行现场功能验证，元数据继续使用 `unverified`。

## OBS-23 test 提交与 121 发布补充（2026-10-19）

用户明确要求“提交代码到 test 分支并发布 test 分支到 121 环境”，覆盖仓库默认的 release 分支约定。本次只交付 Web，不修改 release 或发布 KK。

- 提交为 `e982a0f51e557d00caf4e6d66c7cc5820314eba2`，标题 `feat: move local file listing to v1 and add batch deletion`，共 9 个相关文件：8 个 Go 文件及本次 Swagger 变更。Swagger 保留原有其他操作，列表迁到 V1 并新增删除后共 29 个操作路径；工作区先前已有的 Swagger 精简/整理保留为未提交改动。
- 个人仓库 `wangfei/g_web_installer` 与中央仓库 `Installation-package/g_web_installer` 的 `refs/heads/test` 都从 `53f5514` 快进到上述提交，推送退出 0；随后分别用 `git ls-remote --heads` 核对两个 test 分支的完整 SHA。没有修改其他分支或额外创建合并提交。
- 固定使用 `ssh codex-test-121`，在 `/root/wfweb/g_web_installer` 的 test 分支操作，保留 `data`、`configs/users.json` 与禁用 Vue import / `vue.ServeVue` 的目标机本地调整。临时恢复已确认的两行路由差异后，用 `git pull --ff-only origin refs/heads/test` 拉取，避免同名 test 标签歧义；在最新源码上重新应用这两行调整。
- 拉取后核对目标 HEAD 等于 `origin/test` 且等于本次提交。登录 Shell 执行 `CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o server.next ./cmd/server`，成功后 `mv -f server.next server`。命令退出 0，直接输出 `WEB_BUILD_AND_REPLACE_OK`。
- 通过一次 `ss -lntp 'sport = :8080'` 定位旧 Web PID `757425`，同一次进程归属核对确认 cwd 为 `/root/wfweb/g_web_installer`、exe 为该目录的 `server (deleted)`。随后结束旧进程并立即执行 `/root/wfweb/web_start.sh`；命令退出 0，直接输出 `server started, pid=776462`。

| 检查项 | 结果 | 证据或边界 |
|---|---|---|
| 范围和工作区 | PASS | 只提交 9 个相关文件，保留已有 Swagger 整理 |
| 敏感信息 | PASS | 新增 Go 差异字面凭据扫描通过 |
| 格式与行为测试 | PASS | gofmt/diff 检查通过，沿用前轮已通过的最终实现测试 |
| 构建和替换 | PASS | 121 构建及 server 替换命令退出 0 |
| Git 交付 | PASS | 个人和中央 test SHA 均已核对 |
| 121 启动命令 | PASS | 启动脚本退出 0，报告 PID 776462 |
| 接口现场功能 | NOT RUN | 本次没有追加 HTTP 或删除实际文件验证 |

按发布约定，本轮没有重复执行测试，也未追加版本/二进制哈希检查、接口探测、日志关键字匹配、多轮进程/端口验证或自动回退。PID 来自启动脚本直接输出，发布命令成功不等同于列表、删除功能已现场验证。元数据保持 `unverified`。

仅在 andrew 更新本地案例及索引状态，没有提交/推送该仓库文档或录入向量库。

## OBS-23 请求路径复核补充（2026-10-20）

用户随后提供 Network 中的 V3 登录会话错误截图。本轮在 121 进行只读核对，源码 HEAD 仍为本次提交 `e982a0f51e557d00caf4e6d66c7cc5820314eba2`。相关脱敏访问记录中，`GET /api/v1/obs/file/local/list` 多次返回 200，但本地删除曾发送为 `POST /api/v3/obs/file/local/delete`，返回 404。当前注册的本地删除接口实际为 `POST /api/v1/obs/file/local/delete`，调用方需使用 V1 地址，不能只改列表接口版本。

上述 404 与截图中的 `v3 login session is missing or expired` 是不同问题。V3 会话错误的来源和内存会话机制见 [WEB-16](../05_Web配置鉴权与任务/WEB-16.md)。截图没有完整 Request URL，不能单凭 Network 的 `list/delete` 名称断定其对应哪一条日志。

本轮没有检查或修改前端源码、业务代码、认证凭据或运行文件，没有再次部署/重启。日志中的本地列表 200 仅是 HTTP 访问证据，没有读取该请求响应正文，尚无正确 V1 删除接口的成功记录，因此案例元数据继续为 `unverified`。

## OBS-23 来源

- `g_web_installer/internal/transport/router.go`、`internal/transport/handler/obs_v3_local_list.go`、`internal/transport/handler/obs_local_delete.go`、`internal/transport/handler/obs_v3_middleware.go`。
- `g_web_installer/internal/service/file_server/obs_v3_local_list.go`、`obs_local_delete.go`、`obs_v3_local_download.go`、`obs_v3_local_import.go`。
- `g_web_installer/internal/model/request/obs.go`、`internal/model/reply/obs.go`、`swag.json`。
- 本轮本地 HTTP/文件生命周期/首错停止行为测试、Swagger 校验及服务编译结果。

[返回案例索引](../README.md)
