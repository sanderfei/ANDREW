# HELM-21：Milvus Pending因CPU requests预约满而非镜像缺失

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-08-12（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-21 问题与表现

Milvus升级超时，PodPending；节点实际CPU使用不高。

## HELM-21 最终根因或已确认边界

历史worker可分配8CPU，requests7980m，只余20m；Master带NoSchedule且Pod不容忍。调度看requests，不看瞬时usage。

## HELM-21 处理方案

检查describe节点分配requests和Pod FailedScheduling，调整过大requests/可用容量与有意的节点调度，不盲目清PVC/换镜像。Hook等待超时也可由调度无法启动引起。

## HELM-21 验证证据与限制

历史调整后Milvus各核心服务全部1/1、HookComplete、healthzOK；不用重新安装已恢复release。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-21 来源定位

- Codex 会话 `019ff49e-b946-72a0-8913-0ab2764c18ca`；始于 2026-08-12。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
