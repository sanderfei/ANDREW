# KK-C09：NodePort在master超时而worker正常

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-05-21（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-C09 问题与表现

MongoDB 导入访问 master:30004 超时，worker 同端口可用。

## KK-C09 最终根因或已确认边界

Service externalTrafficPolicy=Local，只转发本节点 Endpoint；MongoDB Pod 在 worker，master 没有本地 Endpoint。

## KK-C09 处理方案

按应用需要用有 Endpoint 的 NodeIP，或评估改成 Cluster 允许跨节点转发；同步调整导入目标发现逻辑，不默认固定第一 Master。校验 Service、Endpoints 和 Pod 节点后再检查防火墙。

## KK-C09 验证证据与限制

历史确认 Local 策略及 Pod 位置，后续错误进入解压阶段证明连接问题已跨过；最终数据恢复未记录。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-C09 来源定位

- Codex 会话 `019e49fd-4546-7761-921f-432304983f3e`；始于 2026-05-21。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
