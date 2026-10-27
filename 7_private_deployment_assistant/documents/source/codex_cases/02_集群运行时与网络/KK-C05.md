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

## KK-C05 2026-10-20 当前泛域名逻辑复核

记录日期：2026-10-20。适用环境：本地 `g_kube_installer` 的 `test` 分支，提交 `a2dc3127a6559d791b7092c802585aa2c05c2a94`；本节核对标准 Kubernetes 的 `kk create cluster` 路径，在线、离线均适用。本轮问题是确认当前实现，没有新增现场故障或 DNS 查询结果。

### 入口、配置与解析行为

- 调用链：`cmd/kk/cmd/create/cluster.go:136` → `pipelines.CreateCluster` → 标准 Kubernetes 的 `NewCreateClusterPipeline` → `dns.ConfigureWildcardDNSModule` → `ConfigureWildcardDNS.Execute` → `reconcileWildcardDNS`。独立模块位于 `PostInstall` 脚本之后、基础组件安装之前；源码中的完整 `ClusterDNSModule` 虽被注释，该独立模块仍会执行。K3s/K8e 分支未接入这个独立模块。
- 任务通过 SSH/sudo 在首个 Master 上调用 `/usr/local/bin/kubectl`，修改集群 `kube-system/coredns` ConfigMap 的 `data.Corefile`；这段任务没有显式指定 kubeconfig，具体身份与权限取决于远端执行环境。
- 域名来自 `spec.system.domain`，去首尾空白、转小写、去一个末尾点；为空直接跳过。当前没有在线/离线或 `nip.io` 的跳过条件。
- 没有对应 zone 时，新建 A 和 AAAA 模板。匹配域名本身及任意层级子域名；A 模板地址取 `GetMasterIP()`，即按 `spec.hosts` 顺序找到的第一个属于 `roleGroups.control-plane` 的节点的 `internalAddress`。未填 `internalAddress` 时，默认化流程会从 `address` 补齐；新建规则要求最终地址能解析为 IPv4。
- AAAA 返回 `NOERROR`、空 Answer，表示没有 IPv6 地址。它用于解决本案例的 A-only zone 导致 AAAA `SERVFAIL` 的问题；没有新增 IPv6 地址或任意类型记录。

例如，域名为 `demo.example.com`、选中的 Master 地址为文档示例地址 `192.0.2.10`，新建区块为：

```text
demo.example.com:53 {
  template IN A {
    match "^(.*\.)?demo\.example\.com\.?$"
    answer "{{ .Name }} 60 IN A 192.0.2.10"
  }
  template IN AAAA {
    match "^(.*\.)?demo\.example\.com\.?$"
    rcode NOERROR
  }
  cache 30
}
```

`demo.example.com`、`dashboard.demo.example.com`、`a.b.demo.example.com` 的 A 查询均匹配此模板。上述内容是根据当前格式化源码整理的示例，没有连接集群生成或执行。

### 已有规则与生效边界

- 已有同域名 zone 时，只对严格符合安装器旧格式的 A-only 区块补 AAAA；保留原 A 地址、TTL 和其他原始文本。已经含 AAAA/ANY、`forward`、`hosts`、`file` 或其他自定义规则的区块原样保留，因此自定义 A-only 区块也不会被自动修复。
- 此逻辑不持续同步 Master IP：即使 Master 地址变化，已有 A 地址仍会保留。域名为空或切换到新域名时，这段逻辑没有删除旧 zone 的步骤。重复目标 zone、无法解析的括号或不支持的目标区块布局会报错。
- 新区块加在原 Corefile 前面，其他内容保留。CoreDNS 按最长域名后缀选择 server block，所以该业务后缀优先于根 `.` 区块；若另有更具体的子域名区块，那个区块优先。已选中的业务区块未配置根区块的转发链；未处理的查询类型不能假定自动回落到根区块。
- 配置未变化时直接返回；变化时 patch ConfigMap，执行 `rollout restart deploy/coredns`，再等待 `rollout status deploy/coredns --timeout=120s`。失败直接报错，不批量删除 DNS Pod。
- 这条规则作用于送到该 CoreDNS 的查询。宿主机、浏览器或其他客户端是否使用该 CoreDNS，应分别检查其 DNS 配置；本段任务不修改这些客户端的解析器。
- 组件域名另由 `component/tasks.go:1885` 的 `getServerHostUrl` 拼接。`spec.system.domain` 为空时，组件仍可能使用 `<组件名>.<远端address>.nip.io`，但本泛域名任务已跳过，不会为这个兜底域名自动建 zone。

### 核验与后续操作

本轮完成当前入口、模块、任务、默认地址和 Corefile 合并逻辑的源码核对，并参考 [CoreDNS 查询路由手册](https://coredns.io/manual/toc/#plugins) 与 [template 插件文档](https://coredns.io/plugins/template/) 核对最长后缀匹配、空 Answer 和 `rcode` 语义。未改业务代码，未构建、部署、重启或执行实时 DNS/HTTP 请求；本节属于源码结论，不新增功能验证证据。

现场需要核验时，先确认最终配置中的 `spec.system.domain` 和选中的 Master `internalAddress`，执行 `kubectl -n kube-system get configmap coredns -o jsonpath='{.data.Corefile}'` 检查对应 zone，再在真实业务 Pod 中对实际业务域名分别执行 `dig 域名 A`、`dig 域名 AAAA`。预期新建模板的 A 为选中的 IPv4，AAAA 为 `NOERROR` 且 `ANSWER: 0`；若原 zone 保留了已有 A，应按该配置中的地址核验。之后还需验证实际业务请求。已有自定义规则或地址不符合当前业务目标时，应先确认其用途，再按目标配置制定修改，不能把重新执行安装器视为自动覆盖已有规则。

源码依据：`cmd/kk/pkg/pipelines/create_cluster.go:112`、`cmd/kk/pkg/plugins/dns/wildcard_module.go:17`、`cmd/kk/pkg/plugins/dns/tasks.go:144`、`cmd/kk/pkg/plugins/dns/wildcard.go:14`、`cmd/kk/apis/g_kube_installer/v1alpha2/cluster_types.go:373`、`cmd/kk/apis/g_kube_installer/v1alpha2/default.go:164`、`cmd/kk/pkg/component/tasks.go:1885`。

## KK-C05 来源定位

- Codex 会话 `01a0b396-9930-75e1-8954-874cb2cd724e`；始于 2026-09-18。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a0b290-5667-7b52-8ce3-9d3425d0a83b`；始于 2026-09-18。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
