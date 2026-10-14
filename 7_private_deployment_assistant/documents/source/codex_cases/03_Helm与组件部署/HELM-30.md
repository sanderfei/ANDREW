# HELM-30：Neo4j对NAS只读snapshot递归chown失败

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-07-22（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-30 问题与表现

chown /data/.snapshot: Read-only file system，Neo4jCrashLoop。

## HELM-30 最终根因或已确认边界

旧3.5.28Chart直接挂PVC根目录，存储快照目录只读；入口脚本递归chown碰到.snapshot退出。

## HELM-30 处理方案

确保应用用户能写数据后，历史可用SECURE_FILE_PERMISSIONS=yes跳过递归chown，或挂干净可写subPath/调整存储快照可见性。该变量来自旧镜像入口脚本，不能默认适用于5.26 Bitnami；勿尝试chmod/chown只读.snapshot。

## HELM-30 验证证据与限制

日志和入口脚本根因核对、包修改记录；缺少本条最终现场写入验证。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-30 来源定位

- Codex 会话 `019f88d6-6fe9-7fe2-8e25-0a533e46b8f1`；始于 2026-07-22。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
