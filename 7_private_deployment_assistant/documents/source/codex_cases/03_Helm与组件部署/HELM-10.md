# HELM-10：Nacos Pending因PVC storageClassName为空或local错配

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-04-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-10 问题与表现

Nacos pod has unbound immediate PersistentVolumeClaims。

## HELM-10 最终根因或已确认边界

历史Chart显式storageClassName=""禁止使用默认动态StorageClass；指定local又不等于集群的nfs-default。

## HELM-10 处理方案

确认实际StorageClass/provisioner，按目标Chart字段使PVC使用正确动态存储类，重新打包nacos.tgz。已创建PVC字段不可随意原地变更，保留数据时制定迁移/重建计划。先解决绑定，再排数据库问题。

## HELM-10 验证证据与限制

nacos包修复提交b6dafe0；后续问题进入数据库schema阶段，不能单据PVC Bound证明Nacos健康。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-10 来源定位

- Codex 会话 `019da8b7-4fb6-7c53-9418-182a68ec00e3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
