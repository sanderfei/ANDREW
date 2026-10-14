# HELM-20：RabbitMQ管理入口404因classless Ingress被忽略

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-09-02（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-20 问题与表现

rabbitmq.<master-ip>.nip.io返回404，Chart已包含Ingress。

## HELM-20 最终根因或已确认边界

ingress.ingressClassName为空，ingress-nginx不监听无class资源；nip.io本身不做代理。

## HELM-20 处理方案

DeployRabbitmq传ingress.enabled=true与ingress.ingressClassName=nginx。管理HTTP走http-stats15672；AMQP5672仍通过NodePort等协议入口，不使用普通HTTPIngress。

## HELM-20 验证证据与限制

ce94f6e6；214PodReady/PVCBound/diagnostic ping，121外部访问HTTP200 RabbitMQManagement。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-20 来源定位

- Codex 会话 `01a060f1-9100-7d30-88ac-056f1de8919b`；始于 2026-09-02。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
