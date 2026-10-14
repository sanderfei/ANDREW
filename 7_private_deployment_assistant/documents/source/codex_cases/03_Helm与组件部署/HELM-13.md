# HELM-13：Nacos3健康检查端口和URL前缀不兼容

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-08-04, 2026-08-12, 2026-08-31（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-13 问题与表现

KK等待Nacos(/1)，旧健康URL410/500，PodRunning但未Ready。

## HELM-13 最终根因或已确认边界

Nacos3 Console接口在8080/v3/...，旧/nacos/v3/...或把console按8848检查不正确；(/1)也可能只是readyReplicas为空，不足以确认根因。

## HELM-13 处理方案

按实际容器探针使用/v3/console/health/readiness和liveness，核对MODE、数据库及readyReplicas；Seata发布流程适配8080console与8848配置API。

## HELM-13 验证证据与限制

6a9090d修复，3/3Ready、鉴权/配置API通过；后续standalone专项也通过。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-13 来源定位

- Codex 会话 `019fca60-203c-77e3-aede-263fd60b5a7a`；始于 2026-08-04。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a055af-6e48-7d72-b584-626a5f397ba7`；始于 2026-08-31。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019ff49e-b946-72a0-8913-0ab2764c18ca`；始于 2026-08-12。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
