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

以上功能验证为历史归档结论，不能替代具体目标集群的当前验证。

## KK-C05 2026-10-15 源码复核

用户再次确认 `192.168.1.27.nip.io:53` 内补 `template IN AAAA { rcode NOERROR }` 的问题是否已经修复。本轮核对本地 `test` 分支：修复提交 `32b1b47`、PR #50 的合并提交 `3da15e7` 均存在，且合并提交是当前 HEAD 的祖先。

- `cmd/kk/pkg/plugins/dns/wildcard.go:21` 仍生成带域名匹配的 AAAA `NOERROR` 空应答；新规则同时生成 A，符合安装器旧格式的 A-only 规则仅补 AAAA，保留原 A 地址。已有自定义规则不会强制覆盖。
- `cmd/kk/pkg/plugins/dns/tasks.go:158` 调用该修复逻辑，配置变化后 patch CoreDNS ConfigMap，并执行 rollout restart/status。源码存在不代表旧集群已经执行过此步骤。
- 本轮未连接 `192.168.1.27`，未检查目标 KK 二进制或实际 Corefile，也未执行部署、重启或 DNS 功能测试。该目标的当前生效情况待验证。

如目标仍出现同类现象，先在目标集群执行 `kubectl -n kube-system get configmap coredns -o yaml` 核对对应 zone；若缺少 AAAA 空答，在该 zone 中补充上述模板，再执行 `kubectl -n kube-system rollout restart deploy/coredns` 和 `kubectl -n kube-system rollout status deploy/coredns --timeout=120s`。最后从真实业务 Pod 查询实际业务域名的 A、AAAA，预期 A 保持 IPv4 地址，AAAA 返回 `NOERROR` 且无地址，并验证原业务请求恢复。本轮仅记录此排查/处理步骤，未执行。

## KK-C05 来源定位

- Codex 会话 `01a0b396-9930-75e1-8954-874cb2cd724e`；始于 2026-09-18。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a0b290-5667-7b52-8ce3-9d3425d0a83b`；始于 2026-09-18。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
