# KK-O06：离线初始化NFS依赖解包后未配置

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-09-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 Ubuntu；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-O06 问题与表现

init registry 在 Zot 安装之前报 libnfsidmap1、rpcbind、keyutils 等依赖缺失，nfs-common/nfs-kernel-server 已解包未配置。

## KK-O06 最终根因或已确认边界

原流程先 dpkg -i 两个 NFS 包；dpkg 不解析补齐依赖，后续 APT 步骤尚未运行就退出。历史核对 ISO 中已有所需依赖。

## KK-O06 处理方案

改用 APT 安装本地 NFS 包，限定从离线 ISO 补齐依赖并修复未配置状态；离线时不因 KKZONE=cn 更新公网源。同步包按节点隔离，避免多节点共享临时文件。现场按已挂载的离线源执行受限 --fix-broken --no-remove 后再重试。

### KK-O06 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
sudo apt-get -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/g_kube_installer.list -o Dir::Etc::sourceparts=- --no-remove --fix-broken install
```

## KK-O06 验证证据与限制

214/215 的首次安装、失败重试、重复安装及缺依赖场景已验证，后续日志显示 NFS 依赖步骤通过；未把这一阶段成功等同完整集群安装。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-O06 来源定位

- Codex 会话 `01a0bca9-a5c7-7c81-bf16-7ef6acbf6739`；始于 2026-09-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
