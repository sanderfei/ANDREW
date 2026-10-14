# KK-C07：多Master的API VIP不是业务Ingress VIP

项目：g_kube_installer。记录状态：源码结论。来源会话起始日期：2026-09-10（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-C07 问题与表现

希望集群外机器通过一个额外 IP 访问所有服务，认为多个 Master/NFS 自动组成完整 HA。

## KK-C07 最终根因或已确认边界

kube-vip 配置的 controlPlaneEndpoint 通常是 6443 API 入口；80/443 的 Ingress 暴露另有配置。etcd quorum、API active-active 和 VIP leader 是不同机制。

## KK-C07 处理方案

API VIP 应为同二层未使用地址，允许 ARP 漂移、证书 SAN 和 6443；业务入口单独配置。3 个 etcd 容忍 1 故障，4 个仍只容忍 1。网络可达之后仍需客户端认证/RBAC；不要分发 admin.conf。

## KK-C07 验证证据与限制

历史源码与拓扑解释，未做 VIP 故障切换或首 Master 故障演练。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-C07 来源定位

- Codex 会话 `01a089e4-3852-7840-9a78-acdcd4c7825a`；始于 2026-09-10。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a08a16-ebab-7ed1-b0a8-5ad5afece0c8`；始于 2026-09-10。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
