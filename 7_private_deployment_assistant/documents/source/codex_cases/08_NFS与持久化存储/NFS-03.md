# NFS-03：Web NFSv4客户端不能自动兼容v3

项目：g_kube_installer / g_web_installer。记录状态：历史功能验证。来源会话起始日期：2026-09-29（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## NFS-03 问题与表现

创建NFS任务或备份传输拒NFSv3，只探测2049仍成功。

## NFS-03 最终根因或已确认边界

旧nfs4.DialAuto只试v4.1/v4.0，v3另需rpcbind/mountd和独立RPC路径。

## NFS-03 处理方案

历史共享客户端v4优先，仅明确协议/版本不支持才回退v3；权限、missingexport、超时不触发盲目降级。v3放通rpcbind111、mountd及NFS实际端口，验证上传/下载/比对/删除及真实认证CreateTask。

## NFS-03 验证证据与限制

121v3/v4各2.4MB读写删除一致，真实create-task成功并持久execution_location=REMOTE，无效export不落任务；PR#404。

上述为 2026-09-29 历史功能验证结论；后续源码复核不表示重新验证当前服务器的部署或运行结果。

## NFS-03 2026-10-21 兼容修改记录复核

记录日期：2026-10-21。用户询问 Web 是否修改过 NFS 协议兼容。本轮在本地 `g_web_installer` 的 `release` 分支核对 Git 记录和当前源码，HEAD 为 `132955179ae4e494f984e4b615d7b293d9d4ee44`。本轮适用对象为 Web 内置 NFS 客户端，不涉及修改 KK 的节点挂载协议。

已确认该兼容修改实际存在，且仍包含在本地当前分支中：

| 项目 | 复核结果 |
|---|---|
| 修改提交 | `2dfbd656e86626815727b964069b42e22304009f`，2026-09-29，`feat: Web NFS storage supports NFSv3 fallback` |
| 合并提交 | `f962f3f31aabcc39855bf8ea3fb6306f5256345a`，2026-09-29，PR #404，从个人仓库 `release` 合入中央仓库 `release` |
| 当前包含关系 | `git merge-base --is-ancestor f962f3f HEAD` 返回 0，确认本地 HEAD 包含该合并；没有据此声称当前远端服务二进制已核验 |
| 修改文件 | `internal/service/nfs_client/client.go`、`nfs3.go`、`nfs4.go` 和 `internal/transport/handler/nfs_validation.go` |

旧实现直接调用 `nfs4.DialAuto`。本项目锁定的 `github.com/mactav683/go-nfs-client v0.1.0` 在 `nfs4/transport.go:59` 中先试 v4.1，符合明确版本回退条件时才试 v4.0，不包含 v3。新增实现将 v3 作为独立协议路径，正常优先级为 v4.1、按条件回退 v4.0，再在明确不支持 v4 时尝试 v3。

当前 `client.go:75` 仍先调用 `dialNFS4`，只有 `unsupportedNFS4` 识别到明确的版本/协议不支持，且上下文未取消时才调用 `dialNFS3`。`nfs4.go:34` 分类包括 `NFS4ERR_MINOR_VERS_MISMATCH`、`NFS4ERR_NOTSUPP`、`NFS4ERR_OP_ILLEGAL` 及固定的 RPC program/version 拒绝信息。权限失败、导出路径不存在、超时和普通网络失败仍返回错误。

覆盖范围也已核对：创建 NFS 任务的可写性探针调用 `nfsclient.ValidateWritable`；备份上传、下载、删除均调用同一 `nfsclient.Dial`。它是公共客户端能力，没有给请求新增手选 NFS 版本的字段。NFSv3 路径通过 TCP 111 上的 rpcbind 发现 mountd，文件数据连接尊重用户配置的 NFS 端口，未填写时默认为 2049。

可执行核对与处理步骤：

1. 在目标 Web 源码中检查是否包含 `2dfbd65` / `f962f3f`，或核对 `client.go` 的 `dialNFS3` 回退分支；针对目标运行服务，还需另行核对其实际部署版本。
2. 使用实际 `host`、`port`、`export_path` 创建 NFS 任务；仅 TCP 端口连通不能替代创建/删除探针。使用 v3 时同时确认 rpcbind、mountd 与 NFS 数据端口可达。
3. 使用创建成功的任务完成备份上传、下载内容比对和删除；若错误是权限、路径或超时，按对应错误检查服务配置与网络。

历史记录中，121 的 v3/v4 均完成过 2.4 MB 上传、下载内容比对和删除，真实认证创建任务也通过；这是历史功能证据。本轮只复核提交及源码，没有连接 121 或其他测试服务器，没有新增测试、修改业务代码、部署、重启或验证当前功能。元数据保留 `verified` 仅对应上述历史功能验证。

## NFS-03 来源定位

- Codex 会话 `01a0ec7f-4204-78e0-a504-3fcda2f86723`；始于 2026-09-29。可按本条标题及关键错误定位相关提问与后续结论。
- 2026-10-21 本地 Git 命令：`git show 2dfbd65`、`git show --no-patch f962f3f`、`git log -- internal/service/nfs_client internal/transport/handler/nfs_validation.go`、`git merge-base --is-ancestor f962f3f HEAD`。
- 当前后端源码：`g_web_installer/internal/service/nfs_client/client.go:75`、`nfs4.go:18`、`nfs4.go:34`、`nfs3.go:31`；`internal/transport/handler/nfs_validation.go:14`、`task_execution.go:121`；`internal/service/backup/local_backup.go:3280`、`:3326`、`:3342`。
- `g_web_installer/go.mod` 锁定 `github.com/mactav683/go-nfs-client v0.1.0`；对应本地模块源码 `nfs4/transport.go:59` 的 `DialAuto` 与版本回退判断。

[返回案例索引](../README.md)
