# KK-O09：离线新增节点APT依赖冲突发生在join之前

项目：g_kube_installer。记录状态：待验证。来源会话起始日期：2026-10-08（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes 1.32.8；系统 Ubuntu；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-O09 问题与表现

worker01 apt error 100；chrony 与 systemd-timesyncd 的 time-daemon 冲突，同时 ipset/NFS 依赖未满足。

## KK-O09 最终根因或已确认边界

日志 file:/tmp/g_kube_installer/iso Packages 证明已读取离线源。失败在 AddNodesPipeline → RepositoryModule → InstallPackage，尚未 kubeadm join；节点包状态、版本/hold 与 ISO 依赖是否一致仍需核对。

## KK-O09 处理方案

先检查 dpkg --audit、apt-mark showhold、冲突包版本和 ISO Packages 索引，再判断是损坏/未配置包、被 hold 的版本还是制品缺包。master 的零新增包安装不能证明 worker 依赖齐全。不得仅据这一日志直接归因 ISO 错误或改成在线安装。

### KK-O09 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
dpkg --audit
apt-mark showhold
dpkg-query -W chrony systemd-timesyncd ipset nfs-common nfs-kernel-server
```

## KK-O09 验证证据与限制

离线分支和失败代码位置已确认，worker01 最终根因及恢复结果未取得。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-O09 来源定位

- Codex 会话 `01a11a9f-ba61-7e73-a4e3-accd4ec7d7a7`；始于 2026-10-08。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
