# HELM-24：Milvus升级的Woodpecker与StorageV2兼容

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-08-04（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-24 问题与表现

从旧Milvus包升级后存储/消息配置不一致，重启后担心丢数据。

## HELM-24 最终根因或已确认边界

新版本Woodpecker、MinIO、Kafka和StorageV2组合与旧包不相同，组件配置不能简单整包覆盖后默认正确。

## HELM-24 处理方案

按项目最终策略使用Woodpecker+MinIO、关闭Kafka及milvus.extraConfig.common.storage.enablev2=false，保留PVC及明确认证。按目标版本验证业务写查搜和重启后的数据，不直接把早期Kafka依赖解释作为当前部署策略。

## HELM-24 验证证据与限制

历史insert/upsert/query/search/drop及etcd/MinIO重启后数据保留、PVCUID不变通过。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-24 来源定位

- Codex 会话 `019fca60-203c-77e3-aede-263fd60b5a7a`；始于 2026-08-04。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
