# HELM-32：RocketMQ Proxy Service targetPort指向7001错误

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-08-04（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-32 问题与表现

ProxyNodePort无法连接，Topic/消息链路与外部入口表现不一致。

## HELM-32 最终根因或已确认边界

Service targetPort7001不对应实际命名remote端口8080。

## HELM-32 处理方案

Chart映射改为targetPort:remote并核对container端口/Endpoints，重新嵌包部署；分别测NodePort和真实消息发送消费。

## HELM-32 验证证据与限制

b0f7571；正式合并发布后3个NodePort连通、Topic创建与消息发送/消费通过。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-32 来源定位

- Codex 会话 `019fca60-203c-77e3-aede-263fd60b5a7a`；始于 2026-08-04。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
