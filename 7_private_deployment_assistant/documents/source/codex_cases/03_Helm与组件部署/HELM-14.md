# HELM-14：MariaDB探针报Access denied后排除密码确认连接数耗尽

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-04-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-14 问题与表现

数据库ready for connections但探针失败，Too many connections/1040，反复恢复和重启。

## HELM-14 最终根因或已确认边界

早期怀疑旧PVC密码，后续socket与TCP认证成功排除此项，Threads103及1040指向连接耗尽。持续重试依赖应用是可疑连接源，需要PROCESSLIST确认。

## HELM-14 处理方案

用运行配置受控登录检查max_connections、Threads_connected与PROCESSLIST。先稳定数据库再按依赖顺序恢复上层，调连接池/连接回收和合理容量；勿在认证已通过后继续反复换Secret或删除数据。

## HELM-14 验证证据与限制

最终历史MariaDB1/1、select1成功；连接占用来源没有完整归因量测。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-14 来源定位

- Codex 会话 `019da8b7-4fb6-7c53-9418-182a68ec00e3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
