# REG-09：Zot就绪检查节点缺curl

项目：g_kube_installer / g_web_installer。记录状态：待验证。来源会话起始日期：2026-09-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 Ubuntu；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-09 问题与表现

checkZotReady 命令未找到curl，Web容器中有curl仍报错。

## REG-09 最终根因或已确认边界

检查通过SSH runner.SudoCmd 在registry节点执行；Web容器依赖不能代替目标节点依赖。

## REG-09 处理方案

在日志标出的registry节点安装/提供可用curl，离线使用匹配依赖包；联网节点可apt-get安装后再init。只读连通排查可先用已有wget/openssl，但不能改变旧检查脚本必须curl的事实。

## REG-09 验证证据与限制

历史确认执行节点与依赖，未记录补curl后完整初始化成功。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-09 来源定位

- Codex 会话 `01a0bca9-a5c7-7c81-bf16-7ef6acbf6739`；始于 2026-09-20。可按本条标题及关键错误定位相关提问与后续结论。

## 2026-11-16：Web 离线初始化 Zot 的检查执行位置

环境：用户提供 Web 离线安装任务截图，日志节点名为 `[master]`；实际主机地址、Web 和 KK 运行版本、操作系统及 Web 容器与目标节点是否同机均未提供。截图包含 `registry API probe failed`、`/bin/bash: line 1: curl: command not found` 和退出码 127。

本地源码证据：Web `internal/service/offline/offline.go:151-179` 在 Web 所在运行环境启动 `kk init registry`；KK 本机 `install_tiny/da595f94c304` 的 `cmd/kk/pkg/bootstrap/registry/module.go:99-101` 将 `InstallZot` 作为 RemoteTask 分配给 registry 角色节点，`zot.go:126-127,169-194` 通过该节点 runner 执行 systemd 启动与 `curl` 检测，`cmd/kk/pkg/core/connector/runner.go:37-42,67-72` 将 sudo 命令交给连接执行。日志的 `[master]` 指此次任务中的节点名；应从该集群配置的 `spec.hosts` 和 `spec.roleGroups.registry` 确认对应机器。若 Web 容器宿主机恰好也是该节点，检查才会在同一台主机上；不能仅凭截图断定两者关系。

截图表明目标节点执行检测的 shell 找不到 curl，可能是未安装或 sudo 环境 PATH 找不到它；不能仅凭此断言 Zot 服务本身故障。截图中 Web 展示报错不代表检测在 Web 容器执行。本地源码不能证明现场运行的 KK 版本一致。

在配置对应的 registry 节点依次检查：

```bash
command -v curl
```

```bash
sudo -E /bin/bash -c 'command -v curl'
```

确认节点系统和离线软件来源后，安装与系统架构及依赖匹配的 curl，或修正其在 sudo 执行环境中的可见性。重新触发初始化前核对已有状态及影响；完成后查看任务终态，并验证仓库 `/v2/` 和镜像实际操作。未连接现场、安装软件或重试；Zot 状态、实际原因及恢复均待验证。

## 2026-11-16：纯离线最小系统的检测方案讨论

用户补充目标节点是纯离线、最小安装的 Ubuntu，缺少 curl，并询问将检查移至 Web 容器的方案。可以评估在 Web 容器内运行的 KK 使用 Go HTTP 客户端访问 registry 节点，从而消除目标节点对 curl 的依赖。

设计时需保留现有 CA 校验、TLS 域名、认证、`/v2/` 与 GUI 检测和重试；同时核实 Web 容器到 registry 节点仓库端口可达。检测语义会从 registry 节点本机回环访问变为 Web 容器到节点的网络访问，因此还会受容器网络、路由和防火墙影响，不能把两种检测视为等价。

以上仅为方案讨论；代码尚未实现，Web 容器网络、现场节点环境和调整后的初始化功能均未验证。

## 2026-11-16：registry 节点可能是任意机器，ping 的检查边界

registry 可以配置在不同机器，Web 所在服务器的 `ping` 只检查 ICMP 连通性，不能证明 Zot 端口、HTTPS、仓库 API 或认证可用。最小系统也不保证提供 ping，且目标可能禁用 ICMP；ping 失败不能直接判定仓库不可用。

可考虑由 KK 所在运行环境使用 Go HTTPS 客户端访问具体 registry 节点，保留 CA、TLS 域名和认证验证，并检查 `/v2/` 与 GUI。Web 容器和宿主机网络环境可能不同，应从实际运行 KK 的环境验证到目标地址及端口的可达性。此方案仍未实现或现场验证。

[返回案例索引](../README.md)
