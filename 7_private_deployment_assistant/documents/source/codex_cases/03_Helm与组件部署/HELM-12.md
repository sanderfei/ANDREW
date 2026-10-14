# HELM-12：Nacos单副本cluster模式导致Distro未Ready和Seata503

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-04-20, 2026-08-31（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-12 问题与表现

Seata NacosException503/server is DOWN now，Nacos Distro snapshot load failed。

## HELM-12 最终根因或已确认边界

历史Nacos1副本仍为cluster模式，naming模块未就绪。后续3.2.2正式方案为standalone，保留外部MariaDB。

## HELM-12 处理方案

单例明确MODE=standalone及replicaCount=1，cluster模式才配置多节点；新Chart仅cluster生成peer变量。检查实际env、8080/v3/console健康接口及8848业务接口，保留MariaDB数据，勿把改replicas视为无需配置模式。

## HELM-12 验证证据与限制

4月现场Nacos/Seata恢复；后续3.2.2专项确认1/1、外部mysql状态、探针code0及原MariaDB13表保留，370a64b/79be534交付。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-12 来源定位

- Codex 会话 `019da8b7-4fb6-7c53-9418-182a68ec00e3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a055af-6e48-7d72-b584-626a5f397ba7`；始于 2026-08-31。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
