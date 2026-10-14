# KK-C06：DNS域名配置和k8s地址网段混用

项目：g_kube_installer。记录状态：源码结论。来源会话起始日期：2026-07-22, 2026-09-10（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-C06 问题与表现

把 system.domain 当 API 地址或 cluster.local，或配置的 Pod/Service CIDR 与物理/Docker 网段重叠。

## KK-C06 最终根因或已确认边界

SSH address、节点 internalAddress、controlPlaneEndpoint、业务 Ingress 后缀、内部 dnsDomain 分属不同路径。历史 config 的 spec.k8s_cluster.vars 不属于 ClusterSpec，可能被忽略。

## KK-C06 处理方案

用 spec.system.domain 配组件域名后缀，spec.kubernetes.dnsDomain 配 Service DNS；API 入口用 controlPlaneEndpoint。安装前比较节点/Docker/VIP/Pod/Service 网段，避免重叠；确认字段实际被模板/模块消费，不能仅凭样例字段存在宣称功能。

## KK-C06 验证证据与限制

历史源码分析；未发生本条配置的实装或网段修复验证。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-C06 来源定位

- Codex 会话 `01a08a04-f13e-7191-b25f-90b77439398d`；始于 2026-09-10。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019f88b7-4948-7942-82aa-96119886cdbc`；始于 2026-07-22。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
