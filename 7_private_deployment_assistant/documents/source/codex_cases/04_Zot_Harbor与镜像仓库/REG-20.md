# REG-20：集群Pod通过CoreDNS解析离线仓库域名

项目：g_kube_installer。记录日期：2026-10-20。记录状态：代码已验证并合并，未部署。代码基线为 `test` 分支提交 `a2dc3127a6559d791b7092c802585aa2c05c2a94`，实现提交为 `d8fcb72eeb1673846a862ff9c7b262986cacadca`，已通过 PR #66 合并至中央仓库 `test`；没有连接目标集群或执行发布。

适用环境：离线部署、通过 `roleGroups.registry` 指定仓库节点；Kubernetes 和操作系统具体版本未由本轮需求限定，仍需匹配目标 CoreDNS 版本与网络配置。本节围绕当前使用的 `digiwin.gkubeinstaller.local:444` 讨论，示例 IP 不是现场配置。

## REG-20 问题与需求

希望集群各命名空间的服务 Pod 能将 `digiwin.gkubeinstaller.local` 解析为 registry 节点 IP，并通过 `https://digiwin.gkubeinstaller.local:444` 访问离线仓库。用户确认复用泛域名配置阶段后，要求实现代码优化；本轮没有提供 Pod DNS 失败、TLS 或 HTTP 的现场报错。

DNS 查询中只有主机名，端口 `444` 由 HTTPS/镜像客户端使用，不能把 `digiwin.gkubeinstaller.local:444` 整体写成 DNS 记录名称。

## REG-20 已确认边界与源码证据

- `cmd/kk/pkg/bootstrap/os/templates/init_script.go:209`、`:268` 将配置中的仓库主机名映射至第一个 registry 节点内网地址，并写入节点 `/etc/hosts`。
- `cmd/kk/pkg/bootstrap/registry/module.go:366` 的 `UpdateLocalHosts` 是本地任务；`tasks.go:295` 修改的是执行 KK 的主机或容器内 `/etc/hosts`。这些操作没有给普通 Pod 建立集群 DNS 记录，普通 Pod 也不会自动继承节点 hosts。
- 基线代码中的业务泛域名任务读取 `spec.system.domain`，为空直接返回；新建泛域名规则的地址来自 `GetMasterIP()`。本轮将任务扩为统一配置入口，仓库 DNS 使用 registry 节点地址，并独立于业务域名开关。
- `cmd/kk/apis/g_kube_installer/v1alpha2/cluster_types.go:364` 的 `Registry.GetHostname()` 已用于提取不含端口的主机名；`runtime.GetHostsByRole(common.Registry)[0].GetInternalIPv4Address()` 是当前节点 hosts 与本机 hosts 共用的 registry IPv4 来源。
- `cmd/kk/pkg/pipelines/init_registry.go:41` 的仓库初始化链路不要求 Kubernetes 已存在，因此不能只在 `kk init registry` 阶段操作 CoreDNS。标准创建集群链路在 `create_cluster.go:112` 已有单独的 DNS 配置任务，可以在 CoreDNS 可用后接入仓库 DNS。
- 标准创建流程中的完整 `ClusterDNSModule` 被注释；仅修改 `plugins/dns/templates/coredns_configmap.go` 或依赖它渲染 hosts 字段，不能证明标准入口会实际应用该变更。
- 当前 NodeLocalDNS 模板的根区块在 `plugins/dns/templates/nodelocaldns_configmap.go:98` 向 `/etc/resolv.conf` 转发外部域名。若目标启用了该配置，只改集群 CoreDNS 可能仍无法覆盖这条查询路径；这属于源码发现，没有确认目标环境是否启用 NodeLocalDNS。

本需求与 [KK-C05](../02_集群运行时与网络/KK-C05.md) 的业务泛域名 AAAA 修复、[REG-01](REG-01.md) 的 KK 本机 hosts 写入、[REG-04](REG-04.md) 的 HTTP/HTTPS 协议问题分别记录，避免混为同一根因。

## REG-20 实现方案

### CoreDNS 固定主机记录

最终采用独立的仓库精确域名区块，追加到集群 `kube-system/coredns` ConfigMap 的原 Corefile 前面。它与其他 server block 的 `hosts` 插件分开，且不会被上级业务泛域名区块遮蔽。假设 registry 节点内网 IP 为文档示例地址 `192.0.2.20`：

```text
digiwin.gkubeinstaller.local:53 {
  # g_kube_installer managed registry DNS
  hosts /dev/null {
    192.0.2.20 digiwin.gkubeinstaller.local
    ttl 60
    no_reverse
  }
  cache 30
}
```

该区块前置于原配置，原有业务泛域名、根区块及其 hosts、forward 等内容保留。`hosts /dev/null` 仅使用这条内联记录，不读取 CoreDNS 容器自身的 hosts；标记用于区分安装器管理的区块。新建区块沿用原根区块的 `bind` 选项，使 NodeLocalDNS 的监听地址保持一致。

CoreDNS 1.11.3 的 hosts 插件对该 IPv4 记录的 AAAA 查询返回成功空应答，本轮已执行本地协议验证。已有同名自定义区块，或适用区块的内联 hosts 中存在不同目标地址时，返回冲突错误并保留配置；已标记但改变了解析方式的受管区块也会报错。已有外部 hosts 文件、import 文件和其他自定义 DNS 入口仍需现场核对。

解析结果返回后，Pod 直接建立到 registry IP 的 TCP 444 / HTTPS 连接，CoreDNS 不代理这段仓库流量。

### KK 集成实现

1. 将原 `ConfigureWildcardDNSModule` 调整为 `ConfigureCoreDNSModule`，任务为 `ConfigureCoreDNS`。在标准创建集群的相同阶段统一处理两类记录，内部保留 `reconcileWildcardDNS`，新增独立的 `reconcileRegistryDNS`；完整 `ClusterDNSModule` 中也复用该任务，并安排在 NodeLocalDNS 配置任务之后。
2. 两类记录各自判断配置条件：业务泛域名读取 `spec.system.domain` 并使用现有 Master IP 规则；仓库记录从实际 `spec.registry.privateRegistry` 提取主机名，从 registry 角色取内网地址。没有受管 registry 节点、主机名为空或配置本身已为 IP 时，按配置边界跳过仓库记录。整体任务只在两类记录均无需处理时提前返回。
3. 读取一次实时 Corefile，依次合并业务泛域名和仓库固定记录，再统一比较最终结果；变化时执行一次 patch 和一次 CoreDNS rollout。原有业务域名为空或泛域名未变化的提前返回已调整，仓库记录不再被漏掉。内部合并函数处理自身无需变更时仅返回传入配置，让后续合并仍可执行。
4. 对安装器管理的仓库记录去重、支持 registry IP 更新，保留其他记录和规则；若有用户自定义的冲突记录，应明确报出冲突和处理选项，不能静默覆盖。两类配置先在内存中合并成功再提交，解析或校验失败时不写入部分结果。仅修改业务泛域名函数自身的匹配规则不能实现这些职责。
5. 该阶段位于标准创建集群后期、基础组件安装前。本轮没有新增独立 DNS 子命令；现有集群应按本节记录进行专项配置，或经授权选择合适的流程入口，不能把本地构建当成旧集群已更新。
6. 仓库记录启用时，通过 `--ignore-not-found` 读取项目现有 `kube-system/nodelocaldns` ConfigMap。存在 Corefile 时，同步受管的精确仓库记录；只有其配置变化时，才 patch 并滚动更新 `daemonset/nodelocaldns`，等待最多 120 秒。未发现该 ConfigMap 时不创建、不重启 NodeLocalDNS。其他名称的第三方 NodeLocalDNS、自定义 nameserver 需匹配实际查询路径。
7. 保留节点 hosts 和 containerd 的仓库设置：kubelet/运行时在节点上拉取 Pod 镜像，这发生在容器启动之前；不能把节点的启动依赖改为只靠集群 CoreDNS。

以上已在本地源码实现；没有执行现场配置、重启或部署。每个变更的 ConfigMap 分别提交，其对应工作负载分别滚动更新；两个 Kubernetes API 写入不具备跨对象事务保证。提交前的合并/校验错误不会写入部分配置，提交阶段的外部错误仍需按直接报错处理。

### Pod 访问条件

- 默认 `dnsPolicy: ClusterFirst` 的普通 Pod 使用集群 DNS；Linux `hostNetwork: true` 的 Pod 应设置 `ClusterFirstWithHostNet`。使用 `Default`、`None`、自定义 nameserver 或应用内独立解析器的 Pod，需要确认该域名的查询实际进入集群 DNS。
- Pod 到 DNS 的查询以及到 registry 节点 TCP 444 的流量需可达；若有 NetworkPolicy、防火墙或代理配置，应按实际路径检查。
- 当前受管 Zot 配置在 `bootstrap/registry/zot.go:68` 使用 TLS。Pod 内的 HTTPS 客户端需信任仓库 CA，证书应匹配域名；节点 containerd 的 CA/跳过校验配置不会自动变成 Pod 应用的信任配置。认证和仓库读写权限按实际接口检查，DNS 不授予权限。

## REG-20 验证步骤与结果

现场部署后按以下顺序验证，本轮尚未执行这些现场步骤：

1. 核对最终 `privateRegistry`、registry 节点内网 IP、Pod `dnsPolicy`、是否启用 NodeLocalDNS，以及实际 Corefile 的区块路由。
2. 在真实业务 Pod 中执行 `getent hosts digiwin.gkubeinstaller.local`，使用现有 DNS 工具分别查 A 和 AAAA；预期 A 返回 registry 节点 IPv4，未配置 IPv6 时 AAAA 成功且为空。至少覆盖不同工作节点和命名空间，hostNetwork 或自定义 DNS 的工作负载另行核验。
3. 使用 Pod 内现有 HTTPS 客户端、正确的 CA 与必要认证访问 `https://digiwin.gkubeinstaller.local:444/v2/`。例如已有 curl 和 CA 文件时使用 `curl --cacert /实际CA文件路径 https://digiwin.gkubeinstaller.local:444/v2/`。`200` 或认证挑战只能证明基础协议响应，仍需读取一个已知存在镜像的 manifest/blob，或完成真实应用所需的仓库操作，才能确认功能。
4. 节点镜像拉取另用该节点现有 CRI 客户端验证，保留成功所需的认证参数且不记录明文；Pod 内 HTTPS 正常不能替代节点拉取验证。

本轮本地验证结果：

- 运行带项目构建标签的 DNS 包聚焦测试，覆盖业务域名为空、泛域名已存在且未变化、两类记录同时变化、只有泛域名、无记录、无 registry 角色、IP 端点跳过、重复执行、registry IP 更新、注释保留、非法配置和自定义规则冲突。
- 通过模拟 Runner 验证主 CoreDNS 只读取一次、两类规则合并时只提交和重启一次，以及 NodeLocalDNS 同步、只有 NodeLocalDNS 变化、校验失败不写入、patch 失败清理临时文件和重启错误传播。
- 使用官方 CoreDNS 1.11.3 二进制，在本机 loopback 的动态端口实际加载生成的 Corefile 并以 dig 查询：`digiwin.gkubeinstaller.local A` 返回示例 registry IP `192.0.2.20`；AAAA 返回 `NOERROR` 且 `ANSWER: 0`；上级业务泛域名中的 `dashboard.gkubeinstaller.local A` 仍返回示例 Master IP `192.0.2.10`；原 hosts 的 `other.local A` 仍返回 `198.51.100.7`。
- 最终聚焦测试命令为 `CGO_ENABLED=0 REGISTRY_DNS_TEST_BINARY=<本轮临时CoreDNS路径> go test -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./cmd/kk/pkg/plugins/dns -v`，通过。按用户约定，临时测试文件在通过后已删除。
- `make kk` 退出 0，生成 `bin/kk`。构建仍显示既有 `hack/version.sh: line 99: GIT_MAJOR: unbound variable` 警告，未修订版本脚本。格式与差异检查通过。

本轮没有在真实 Pod 或 registry 节点验证 DNS、TLS、镜像仓库 API 或镜像拉取，也没有部署、重启现场服务。`verification_status` 仍为 `unverified`，本地 DNS 协议与构建证据不代表现场仓库访问已恢复。用户原有的 `cmd/kk/pkg/component/pinpoint.tgz` 修改保持不变。

## REG-20 2026-10-20 命令依赖与执行位置审计

用户追问本次改动是否调用了 Web 容器中可能缺失的命令，或是否完全由 Go 实现。本轮只读审计 KK 业务代码，未改代码、重建镜像或连接现场容器。

结论：新增的域名/IP 校验、Corefile 解析、记录合并、冲突检查和补丁编码是 Go 实现；应用配置仍沿用原泛域名流程的远端命令调用，不是全流程直接用 Go Kubernetes 客户端访问 API。本次没有新增 Web 容器内必须安装的外部命令种类。

| 部分 | 实现与执行位置 |
|---|---|
| `reconcileRegistryDNS`、`reconcileWildcardDNS`、JSON/Base64 编码 | KK 进程内的 Go 逻辑，没有调用本机命令 |
| SSH 连接 | `connector` 使用 `golang.org/x/crypto/ssh`，此任务不启动本机 `ssh` 或 `sshpass` 程序 |
| 查询/修改 ConfigMap、rollout restart/status | 通过 SSH 在首个 Master 主机运行 `/usr/local/bin/kubectl` |
| 写补丁、清理补丁 | 同一 Master 上通过 shell 执行 `echo`、`base64 -d`、重定向和 `rm -f`；echo 是 Bash 内置命令 |
| 提权与 shell | `Runner.SudoCmd` 包装为 `sudo -E /bin/bash -c`，也在远端 Master 执行 |
| `hosts /dev/null`、`bind`、`ttl`、`no_reverse` | CoreDNS/NodeLocalDNS 插件配置及文件路径，不是 shell 命令 |

依据：`coredns_module.go:17` 声明 `RemoteTask`，仅选择首个 Master；`core/task/remote_task.go:161` 连接目标主机并设置其 Runner；`core/connector/runner.go:42` 将命令交给连接；`core/connector/ssh.go:327` 通过 SSH session 执行，`:605` 包装 sudo 和 Bash。`plugins/dns/tasks.go:162`、`:182`、`:218`、`:223`、`:226`、`:232`、`:235` 是当前命令调用点。与基线 `a2dc312` 的旧 `ConfigureWildcardDNS.Execute` 对比，命令种类相同，新增的是 NodeLocalDNS 查询、更新及等待对象。

Web 的 `internal/kk/client.go:66` 通过 Go `exec.Command` 启动 `/g_web_installer/kk`；这不使后续 RemoteTask 中的 sudo/kubectl/base64 在 Web 容器本地执行。此次没有修改该 Web 代码。

上轮 `dig`、curl 下载和本地 CoreDNS 二进制仅用于开发验证，没有加入 KK 运行时命令调用，临时测试及验证工具均已删除。目标 Master 仍需要原流程的 sudo、Bash、kubectl、base64、rm，并具备相应 kubeconfig/RBAC；本轮没有现场核验这些命令、权限或实际容器镜像，不能以 Dockerfile 或源码代替运行时可用性证明。

## REG-20 2026-10-20 提交与合并结果

- 仅提交本次 DNS 改动：统一任务、独立仓库记录合并和流程接入，共 5 个文件变更，包含模块文件重命名。没有提交 `pinpoint.tgz`、测试文件、构建二进制或 andrew 仓库其他改动。
- 实现提交：`d8fcb72eeb1673846a862ff9c7b262986cacadca`，已推送到个人仓库 `wangfei/g_kube_installer` 的 `test`。
- [PR #66](http://192.168.3.34/Installation-package/g_kube_installer/pulls/66) 从 `wangfei:test` 合并到中央仓库 `Installation-package/g_kube_installer:test`，合并提交为 `b35e7db45aea46b209ddfc4bfb4a82a5e4bad32f`。未强推、未绕过保护、未删除个人分支。
- 合并后通过 API 确认 `merged=true`，再 fetch 中央 `test` 并将本地分支快进，核对本地 HEAD 与 `upstream/test` 均为上述合并提交，且包含实现提交。
- 本轮沿用已完成的聚焦测试、本地 DNS 协议和构建结果，没有重复运行测试或构建，没有部署、重启或验证现场功能。原有 `pinpoint.tgz` 本地修改保持不变；本案例及索引只更新本地文档。

## REG-20 来源定位

- 当前源码：`cmd/kk/pkg/bootstrap/os/templates/init_script.go:268`、`cmd/kk/pkg/bootstrap/registry/tasks.go:295`、`cmd/kk/pkg/bootstrap/registry/module.go:366`、`cmd/kk/pkg/pipelines/init_registry.go:41`。
- DNS 接入：`cmd/kk/pkg/pipelines/create_cluster.go:112`、`cmd/kk/pkg/plugins/dns/coredns_module.go:13`、`cmd/kk/pkg/plugins/dns/tasks.go:145`、`cmd/kk/pkg/plugins/dns/registry.go:16`。NodeLocalDNS 原根区块见 `cmd/kk/pkg/plugins/dns/templates/nodelocaldns_configmap.go:98`。
- [CoreDNS hosts 插件说明](https://coredns.io/plugins/hosts/)；[CoreDNS 1.11.3 hosts 应答实现](https://github.com/coredns/coredns/blob/v1.11.3/plugin/hosts/hosts.go)。
- [Kubernetes Pod DNS 策略](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/#pod-s-dns-policy)；[Kubernetes 镜像拉取](https://kubernetes.io/docs/concepts/containers/images/)。

[返回案例索引](../README.md)
