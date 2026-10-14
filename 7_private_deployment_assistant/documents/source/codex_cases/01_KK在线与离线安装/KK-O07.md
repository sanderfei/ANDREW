# KK-O07：dpkg前端锁被unattended-upgrade占用

项目：g_kube_installer。记录状态：待验证。来源会话起始日期：2026-10-09（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 Ubuntu；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-O07 问题与表现

init registry / InstallNfsDebs 报 dpkg-lock-frontend 被占用，Ubuntu 自动更新进程仍在运行。

## KK-O07 最终根因或已确认边界

离线 artifact 不会自动关闭节点的更新定时器；unattended-upgrade --download-only 仍可能持有 dpkg 锁。锁文件存在不等于锁仍被持有。

## KK-O07 处理方案

确认持锁进程后等待结束或有序停止竞争的更新任务，确认锁释放，再执行 dpkg --configure --pending 并重试。APT 可设置有界 DPkg::Lock::Timeout=300；不要删除锁文件。

### KK-O07 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
ps -ef | rg "unattended|apt|dpkg"
sudo fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock
sudo dpkg --configure --pending
```

## KK-O07 验证证据与限制

历史识别了持锁进程并给出恢复步骤；未记录最终 APT 重试成功。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-O07 来源定位

- Codex 会话 `01a11e76-e245-75f0-82a7-b73685d728c7`；始于 2026-10-09。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
