# REG-06：containerd1.x使用certs.d而非旧inline镜像配置

项目：g_kube_installer / g_web_installer。记录状态：源码结论。来源会话起始日期：2026-09-28, 2026-10-08（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes 1.32.8；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-06 问题与表现

修改 /etc/containerd/config.toml 的 registry mirrors 不生效；节点配置看起来不同。

## REG-06 最终根因或已确认边界

进程可能使用另一 --config 文件，或 CRI config_path 指向 /etc/containerd/certs.d。此时 host:port 目录的 hosts.toml 决定镜像主机行为；角色不是配置差异的唯一原因。

## REG-06 处理方案

先 ps 和 systemctl show 确认活跃配置，再核对 /etc/containerd/certs.d/<registry:port>/hosts.toml。此案例适用历史 containerd1.x，2.x需要对应插件路径。改主配置需重启运行时，改 unit 才需要 daemon-reload；最终验证用同节点 crictl pull。

### REG-06 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
ps -ww -C containerd -o pid,args
systemctl show containerd -p MainPID -p ExecStart -p FragmentPath -p DropInPaths
crictl pull <registry:port/project/image:tag>
```

## REG-06 验证证据与限制

历史提供活跃 config_path 的配置并解释；完整拉取错误不足，未宣称修复。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-06 来源定位

- Codex 会话 `01a0e73a-d872-7de0-b4bd-898a8dc97d47`；始于 2026-09-28。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a11acc-4df5-78f3-9d32-2b2307bff4c5`；始于 2026-10-08。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
