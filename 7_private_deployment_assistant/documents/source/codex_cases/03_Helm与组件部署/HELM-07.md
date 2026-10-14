# HELM-07：Kafka KRaft Secret被错误绑定SASL条件

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-04-15（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-07 问题与表现

关闭SASL后kafka-kraft Secret不存在，Kafka启动失败。

## HELM-07 最终根因或已确认边界

模板将KRaft元数据Secret包含在SASL分支内，但关闭客户端SASL不意味着不需要KRaft初始化数据。

## HELM-07 处理方案

将KRaft Secret独立生成，SASL Secret仍按认证条件生成，重新打包kafka.tgz。不要只把密码字段补回以绕开模板缺陷。

## HELM-07 验证证据与限制

lint/template通过，默认渲染包含kafka-kraft；未记录这一轮Kafka实装。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-07 来源定位

- Codex 会话 `019d9001-85fa-74e1-8139-e17f1bfb9e81`；始于 2026-04-15。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
