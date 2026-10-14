# KK-O08：Ubuntu24.04离线ISO缺项与按OS版本选择

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-10-08（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes 1.32.8；系统 Ubuntu；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-O08 问题与表现

22.04 制品用于 24.04 节点；不知道不同节点是否自动选择对应 ISO。

## KK-O08 最终根因或已确认边界

artifact 导出阶段按 manifest 下载/打包；安装阶段读远端 /etc/os-release 的 ID、VERSION_ID 和架构匹配包，不在节点上自动下载缺少的 ISO。

## KK-O08 处理方案

manifest 为 Ubuntu 22.04、24.04 分列，重新导出包含二者的 artifact。24.04 路径是 repository/amd64/ubuntu/24.04/ubuntu-24.04-amd64.iso。ISO 是 APT 仓库，不是 OS 安装盘或镜像全集。历史 24.04 ISO 未含 nfs-kernel-server，该包另由内嵌 nfs.tgz 提供，不能据此断言 NFS 完整可用。

## KK-O08 验证证据与限制

历史实际检查 Packages.gz 和 95 个 deb，聚焦测试/构建通过，PR #64 合并；24.04 NFS 现场闭环未验证。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-O08 来源定位

- Codex 会话 `01a1191d-6db7-7c42-8d00-6194d609a369`；始于 2026-10-08。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
