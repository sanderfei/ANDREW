# KK-C05：通配域名A正常但AAAA返回SERVFAIL

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-09-18（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-C05 问题与表现

xxx.<master-ip>.nip.io 在某些双栈客户端解析失败，手动改 CoreDNS 后恢复。

## KK-C05 最终根因或已确认边界

最具体的自定义 zone 只有 template IN A，捕获 AAAA 查询却无法匹配，也不能自动回落到根 zone forward，导致 SERVFAIL。

## KK-C05 处理方案

对安装器生成的 A 通配块补 AAAA 的 NOERROR 空答，让 IPv4 回退正常。reconcile 只更新安装器规则并保留用户已有规则；后续历史统一在线/离线，不再使用旧在线 nip.io 跳过策略。更新 Corefile 后 rollout restart/status，再从真实 Pod 同测 A、AAAA。

## KK-C05 验证证据与限制

本地 CoreDNS 1.11.3 验证 SERVFAIL→NOERROR/ANSWER0，A 保持 IP；PR #50 合并。180 的后续只读检查确认相关规则及 Pod 解析正常，非新部署操作。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-C05 来源定位

- Codex 会话 `01a0b396-9930-75e1-8954-874cb2cd724e`；始于 2026-09-18。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a0b290-5667-7b52-8ce3-9d3425d0a83b`；始于 2026-09-18。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
