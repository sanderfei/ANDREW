# HELM-04：Bitnami非标准私库镜像被allowInsecureImages拦截

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-04-15（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-04 问题与表现

Redis/Milvus/MinIO NOTES阶段拒绝自定义registry镜像，提示非标准镜像。

## HELM-04 最终根因或已确认边界

Chart镜像来源校验，与pull的TLS证书/HTTP策略不同；子Chart也可能独立执行校验。

## HELM-04 处理方案

确认镜像符合部署需求后，在消费该值的Chart层级设置global.security.allowInsecureImages=true，渲染实际子Chart参数并重新打包。该值不表示registry跳过TLS，也不会补仓库权限。

## HELM-04 验证证据与限制

Redislint/template通过；Milvus曾发现单补父值未完全覆盖，因此需最终嵌包验证，历史随后提交 সংশ应修复。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-04 来源定位

- Codex 会话 `019d9001-85fa-74e1-8139-e17f1bfb9e81`；始于 2026-04-15。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
