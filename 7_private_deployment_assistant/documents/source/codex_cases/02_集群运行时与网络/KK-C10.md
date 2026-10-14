# KK-C10：kubectl和Helm能SSH执行但无法访问API

项目：g_kube_installer。记录状态：源码结论。来源会话起始日期：2026-08-06, 2026-08-12（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-C10 问题与表现

SSH 或 sudo 成功，helm/kubectl 仍报未授权或 API 连接错误；worker 没有 kubeconfig。

## KK-C10 最终根因或已确认边界

远程 Shell 身份和 Kubernetes API 身份独立。KK 一般在第一 Master sudo -E 执行，实际 KUBECONFIG/证书/RBAC 决定 API 权限。

## KK-C10 处理方案

在正确控制面读取实际命令环境并显式指定有效 kubeconfig；分别查连接、TLS、认证和 kubectl auth can-i。worker 没有管理 kubeconfig不能证明节点上的业务服务不可用。

### KK-C10 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes
KUBECONFIG=/etc/kubernetes/admin.conf kubectl auth can-i get pods --all-namespaces
```

## KK-C10 验证证据与限制

历史调用链分析；未把 SSH 授权描述为 Kubernetes 业务授权。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-C10 来源定位

- Codex 会话 `019fd691-52d5-77e3-a7b9-9e104320bcb8`；始于 2026-08-06。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019ff49e-b946-72a0-8913-0ab2764c18ca`；始于 2026-08-12。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
