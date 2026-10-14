# NFS-12：immutable手动删除限制历史被明确移除

项目：g_kube_installer / g_web_installer。记录状态：历史功能验证。来源会话起始日期：2026-07-23（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## NFS-12 问题与表现

DELETE备份报不可变保留期，误认为NFS权限故障；旧建议修改immutablefalse。

## NFS-12 最终根因或已确认边界

旧策略按records.created_at与retention_days拒删，用户后来要求手动删除不受immutable/retention限制。

## NFS-12 处理方案

以目标版本确认合同：后续手动删除直接删本地/NFS并更新记录，自动retention只处理过期项。不要将旧保护错误作为现行必然行为；实际删除属于明确的数据操作。

## NFS-12 验证证据与限制

历史immutabletrue仍可手删的临时测试及后续真实API检查通过。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## NFS-12 来源定位

- Codex 会话 `019f8c93-8796-7c53-8ef4-c07f7c0baddf`；始于 2026-07-23。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
