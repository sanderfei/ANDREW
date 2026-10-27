# KK-O08：Ubuntu24.04离线ISO缺项与按OS版本选择

项目：g_kube_installer。记录状态：历史代码已验证；2026-10-20 补充源码复核，24.04 现场功能待验证。来源会话起始日期：2026-10-08（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes 1.32.8；系统 Ubuntu；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-O08 问题与表现

22.04 制品用于 24.04 节点；不知道不同节点是否自动选择对应 ISO。

## KK-O08 最终根因或已确认边界

artifact 导出阶段按 manifest 下载/打包；安装阶段读远端 /etc/os-release 的 ID、VERSION_ID 和架构匹配包，不在节点上自动下载缺少的 ISO。

## KK-O08 处理方案

manifest 为 Ubuntu 22.04、24.04 分列，重新导出包含二者的 artifact。24.04 路径是 repository/amd64/ubuntu/24.04/ubuntu-24.04-amd64.iso。ISO 是 APT 仓库，不是 OS 安装盘或镜像全集。历史 24.04 ISO 未含 nfs-kernel-server，该包另由内嵌 nfs.tgz 提供，不能据此断言 NFS 完整可用。

## KK-O08 验证证据与限制

历史实际检查 Packages.gz 和 95 个 deb，聚焦测试/构建通过，PR #64 合并；24.04 NFS 现场闭环未验证。

以上为历史归档结论；2026-10-20 的源码复核范围见下文，未重新连接客户环境、部署或触发业务操作。

## KK-O08 2026-10-20 补充：manifest 的 osImage 是否可以自定义

适用环境：本地 `g_kube_installer` 的 `test` 分支，HEAD `9094b520a13775b7225943c02f5c04843fc55dd8`；检查用户当前工作区中的 `cmd/kk/manifest-v1.32.8.yaml`。该文件已包含 Ubuntu 22.04、24.04 和 CentOS 7 条目；本轮未改动 manifest 或业务代码，也未验证这些系统的完整安装兼容性。

### 问题表现

用户询问 `osImage` 能否任意自定义，当前 Ubuntu 24.04 条目写为 `osImage: Ubuntu 24.04.6 LTS`。本轮没有安装失败日志。

### 已确认边界与源码证据

- 当前 manifest 的 `OsImage` 是普通字符串，加载时进行 YAML/JSON 解析，没有操作系统名称枚举或版本校验。全仓 Go 源码检索中，该字段只出现在类型声明、manifest 生成赋值和模板输出，没有参与 ISO 选择。
- 从已有集群生成 manifest 时，代码把 Kubernetes Node 的 `status.nodeInfo.osImage` 原样写入该字段；生成器还会解析 Node 上报的 OS 名称来推导 `id`、`version`，这与导入用户手写 manifest 后是否使用其 `osImage` 字段是两条不同路径。
- 导出入口为 `kk artifact export` → `pipelines.ArtifactExport` → `NewArtifactExportPipeline` → `artifact.RepositoryModule`。ISO 下载地址来自 `repository.iso.url`，文件名为 `<id>-<version>-<arch>.iso`，打包目录为 `repository/<arch>/<id>/<version>/`，均未使用 `osImage`。
- 安装阶段 `bootstrap/os.RepositoryModule` 执行 `GetOSData` 和 `SyncRepositoryFile`：读取目标节点 `/etc/os-release` 的 `ID`、`VERSION_ID`，结合节点架构查找相应 ISO。因此，manifest 的 `arch`、`id`、`version` 必须与实际节点匹配；更改 `osImage` 不会改变这些匹配键。

### 配置方法

1. 在目标节点执行 `cat /etc/os-release`，核对 `ID`、`VERSION_ID`，并核对节点架构。
2. 按实际系统配置 manifest 的 `arch`、`id`、`version` 及对应 ISO 来源。对 `amd64`、`ubuntu`、`24.04`，预期制品路径为 `repository/amd64/ubuntu/24.04/ubuntu-24.04-amd64.iso`。
3. `osImage` 可以自定义描述文本；为了便于辨认，建议采用目标节点 `PRETTY_NAME` 的实际值。例如仅将上述描述改成 `"Ubuntu 24.04 LTS"`，不会改变 ISO 下载、打包或安装匹配。该名称不构成对具体系统发行版本存在性或 ISO 兼容性的验证。
4. 如果更改了匹配键或 ISO 内容，重新导出并核对制品；仅修改 `osImage` 描述不会改变当前实现的 ISO 路径或来源。

### 验证结果与遗留事项

本轮通过源码检索及调用链核对确认字段用途；未执行构建、artifact 导出、ISO 下载、远程命令或集群功能验证。没有核验当前 ISO URL 可下载性及包内容。元数据继续保持 `verification_status: unverified`，历史 24.04 NFS 现场验证边界不变。

本轮源码定位：

- `cmd/kk/apis/g_kube_installer/v1alpha2/manifest_types.go:34`；`cmd/kk/pkg/common/artifact_runtime.go:65`。
- `cmd/kk/pkg/artifact/manifest.go:96`、`:115`；`cmd/kk/pkg/artifact/templates/manifest.go:41`。
- `cmd/kk/cmd/artifact/export.go:80`；`cmd/kk/pkg/pipelines/artifact_export.go:34`、`:106`；`cmd/kk/pkg/artifact/module.go:28`。
- `cmd/kk/pkg/artifact/tasks.go:45`、`:99`；`cmd/kk/pkg/bootstrap/os/module.go:254`；`cmd/kk/pkg/bootstrap/os/tasks.go:291`、`:353`。

## KK-O08 2026-10-20 后续：直接覆盖 121 的 manifest

用户要求将本地当前 `cmd/kk/manifest-v1.32.8.yaml` 发送到 121 的 manifest 目录，不备份、直接覆盖已有文件。

- 经 `ssh codex-test-121` 确认 `/root/wfkk/manifest` 存在，其中已有 `manifest-v1.32.8.yaml`。
- 执行 `scp /home/wangfei/code/g_kube_installer/cmd/kk/manifest-v1.32.8.yaml codex-test-121:/root/wfkk/manifest/manifest-v1.32.8.yaml`，退出码为 0，直接覆盖完成，没有生成备份文件。
- 本次结果仅覆盖 manifest 文件传输；不构成 artifact 重新导出、ISO 内容检查或集群安装功能验证。元数据仍为 `unverified`。

## KK-O08 来源定位

- Codex 会话 `01a1191d-6db7-7c42-8d00-6194d609a369`；始于 2026-10-08。可按本条标题及关键错误定位相关提问与后续结论。
- 2026-10-20 本地源码复核；不属于 2026-10-14 历史扫描，也不增加独立案例数量。

[返回案例索引](../README.md)
