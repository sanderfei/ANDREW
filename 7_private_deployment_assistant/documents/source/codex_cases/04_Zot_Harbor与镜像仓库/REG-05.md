# REG-05：证书错误x509与no basic auth credentials是两件事

项目：g_kube_installer / g_web_installer。记录状态：待验证。来源会话起始日期：2026-09-18, 2026-09-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-05 问题与表现

crictl pull 报 x509 unknown authority，或 no basic auth credentials，或携带凭据401。

## REG-05 最终根因或已确认边界

证书信任、凭据缺失、凭据错误属于不同阶段。skip_verify/insecure_skip_verify 只影响证书验证，不提供认证。hosts.toml 目录必须包含实际 registry host:port。

## REG-05 处理方案

按完整错误分类。优先配置受信 CA；自签名排查时按运行时正确语法设置证书策略。认证核对实际客户端凭据来源；已预装 containerd 可能被 KK 跳过。不要只验证 HTTPS /v2/ 200 就认定节点 pull 成功。

## REG-05 验证证据与限制

历史确认旧配置跳过和目录名不匹配；这条客户链没有统一的最终pull成功证据。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-05 来源定位

- Codex 会话 `01a0b30c-04bf-7fc0-954b-f763a87a463e`；始于 2026-09-18。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a0bca9-a5c7-7c81-bf16-7ef6acbf6739`；始于 2026-09-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
