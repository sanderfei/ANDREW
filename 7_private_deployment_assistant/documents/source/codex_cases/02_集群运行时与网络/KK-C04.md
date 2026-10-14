# KK-C04：Calico Init0/3因宿主机缺少bpffs目录

项目：g_kube_installer。记录状态：待验证。来源会话起始日期：2026-04-27（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-C04 问题与表现

calico-node Init:0/3；FailedMount: /sys/fs/bpf is not a directory，CoreDNS/controllers Pending。

## KK-C04 最终根因或已确认边界

模板 hostPath.type=Directory 要求目录预先存在，kubelet 校验失败后 initContainer 也无法创建/挂载。历史继续核对发现旧宿主内核能力也要检查，不是只由 2C8G 规格判断。

## KK-C04 处理方案

先在故障节点确认 uname -r 和目录/挂载状态；有 BPF 支持时准备目录/挂载后重建故障 Pod。若内核缺少能力，按 OS 支持范围升级并重启该节点后验证。模板可改 DirectoryOrCreate 或 bootstrap 预创建，但历史该建议不等于已合并。

### KK-C04 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
uname -r
ls -ld /sys/fs/bpf
mount | rg bpffs
kubectl -n kube-system describe pod <calico-pod>
```

## KK-C04 验证证据与限制

现场事件确认 FailedMount；记录有内核排查及建议，未证明重启后的集群恢复。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-C04 来源定位

- Codex 会话 `019dcda0-0c9b-7433-81b3-dc45661aadac`；始于 2026-04-27。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
