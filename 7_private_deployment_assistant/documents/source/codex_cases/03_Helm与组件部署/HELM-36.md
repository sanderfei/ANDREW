# HELM-36：PostgreSQL镜像含扩展文件不等于每个数据库启用vector

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-08-12（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-36 问题与表现

PG17.9/pgvector0.8.3版本不匹配；以为pgvectorJob会启动另一套数据库或扩展文件自动生效。

## HELM-36 最终根因或已确认边界

部分公网pgvector标签实际内含PG17.10而非所需17.9。扩展文件在PG容器镜像内，CREATE EXTENSION在每个数据库执行；一次性Job只是连接既有Service。

## HELM-36 处理方案

历史纯PG镜像单独安装，pgvector阶段切换原PGrelease到17.9+0.8.3组合镜像并--reuse-values保留PVC/连接设置，再Job检查版本、创建/升级extension。该Job等待可用是安装路径，不与Web导入一次尝试策略矛盾。重复Job及已有凭据需保持一致。

## HELM-36 验证证据与限制

121组合镜像构建push，214/215实际安装、保留PVC及向量写入/相似度/索引验证通过；JobComplete是正常最终状态。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-36 来源定位

- Codex 会话 `019ff49e-b946-72a0-8913-0ab2764c18ca`；始于 2026-08-12。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
