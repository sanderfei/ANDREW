# HELM-44：组件安装在Greetings阶段因角色主机SSH地址为空失败

项目：g_web_installer、g_kube_installer。记录日期：2026-10-30。记录状态：实际任务与121源配置已核对，用户授权后已从源配置清理误填 `ssdf` 主机及其全部角色引用；写后结构和权限复核通过。未重跑安装，Neo4j安装功能仍待新任务验证。

适用环境：用户从121安装 Neo4j，日志为 `InstallComponentsPipeline` / `GreetingsModule`，后续授权检查确认实际集群 `k8s_test` 指向214/215，任务与路径见同日后续节。Web/KK二进制版本、Neo4j镜像/Chart版本、OS及Kubernetes版本未在本次证据中确认，不能由其他测试环境推定。

## HELM-44 问题表现

本次实际日志显示 `k8s-master` 与 `k8s-worker` 的 Greetings 成功，另一个主机失败：

```text
[ssdf] failed to connect to : Failed to validate ssh connection parameters:
No address specified for SSH connection
```

错误中 `connect to` 后没有地址，与 SSH 参数校验的空地址错误一致。此次尚未进入 Neo4j 的 Helm 部署，不是 APOC、Neo4j密码或备份配置错误。两个节点 Greetings 成功只证明它们当时的 SSH 连接通过，不能证明其余节点或组件安装通过。

## HELM-44 问题原因与源码证据

Web `InstallComponentJob()` 读取 `<Web工作目录>/data/cluster/<cluster>/config.yaml`，合并组件配置后将完整配置写入任务执行目录，随后调用：

```text
kk install component -f <任务执行目录>/config.yaml -y
```

KK 的 `InstallComponentsPipeline` 先执行 `GreetingsModule`，再执行 `DeployComponentModule`。Runtime 从 `roleGroups` 引用的主机中按名称去重建立实际主机集合，Greetings 遍历 `Runtime.GetAllHosts()`；因此，其他角色中引用的主机也会参加 SSH 检查，并非只检查计划部署 Neo4j 的一个节点，也不是无条件检查 `spec.hosts` 中所有未被引用的行。

连接器对有效 `Cfg.Address` 为空明确返回本次 `No address specified for SSH connection`。默认化会在 `address` 为空但 `internalAddress` 非空时进行回退，所以不能仅凭原始 `address` 字段为空就解释此次错误：日志确认的是当次 KK 最终用于 SSH 的地址为空，通常对应 `address` 与可回退的 `internalAddress` 都未提供。若角色引用的名字根本不存在于 `spec.hosts`，则会更早被主机校验以 `is in group but not in hosts list` 拒绝，不会走到当前 Greetings 错误。

因此，本次直接原因已定位为 `ssdf` 对应运行主机的有效 SSH 地址为空。初始分析时尚未读取实际任务快照和源配置；后续授权检查已核对同一任务及源配置，并修正相关条目，详见同日后续节。

## HELM-44 处理方向

本轮只给出定位和处理步骤，未代为执行：

1. 先确认真正运行该任务的 Web 工作目录、集群名和PID，核对任务快照 `<Web工作目录>/data/cluster/<cluster>/history/<PID>/config.yaml`，再对照源文件 `<Web工作目录>/data/cluster/<cluster>/config.yaml`。只核对 `ssdf` 的 `name/address/internalAddress` 及全部 `roleGroups` 引用，不输出或记录任何密码、私钥或Token。
2. 若 `ssdf` 是误添加的占位主机，从源配置的 `spec.hosts` 与所有 `roleGroups` 中一致清理引用；不能只删主机行而遗留角色引用，也不能未确认用途就直接删掉真实角色节点。
3. 若 `ssdf` 是实际节点，补充正确可达的 SSH `address`，核对 `internalAddress` 和既有身份配置。无需因本次空地址错误去重置已成功节点的密码或改 Neo4j 的数据库参数。
4. 修正实际源配置后发起新任务，让 Web 重新生成快照；只改旧任务快照不能保证下一次任务采用新配置。核对新日志中所有角色主机 Greetings 通过，再分别检查组件部署及 Neo4j实际功能。后续配置修改和重试应在相应授权范围内执行。

## HELM-44 历史关联与证据边界

[HELM-40](HELM-40.md) 的2026-10-21记录曾发现121某集群配置中存在名为 `ssdf`、地址未填写且有角色引用的条目；当时安装请求未通过认证，没有产生真实安装任务，因此原记录明确不能认定其导致安装失败。本次用户提供的是相同类型的真实 Greetings 失败证据，但尚无当前集群名或实际配置路径，不能将历史文件当作本次已重新核实的源配置，也不将本案合并为StarRocks鉴权问题。

初始源码分析能解释日志，不证明121部署二进制与所查源码逐字一致；该阶段未连接远端或修改配置。后续授权检查和配置修正见下节，仍未触发新安装、部署或重启。元数据保持 `unverified`，需要新任务最终结果。

## HELM-44 同日后续：授权核对并修正121实际源配置

用户随后明确授权修复121保存的集群配置，目标为214/215。实际运行 Web 为 `/root/wfweb/g_web_installer/server`，工作目录为 `/root/wfweb/g_web_installer`；唯一集群为 `k8s_test`，实际源文件为 `/root/wfweb/g_web_installer/data/cluster/k8s_test/config.yaml`。用户日志的 `00:13:12` 精确对应任务 `history/2026-10-30_00-13-12.033_install_component/config.yaml`，该快照含同一误填主机和角色引用；对应 `execute.log` 确认 `ssdf` 的 `No address specified for SSH connection`。因此，上方分析阶段“未读取实际配置”的限制已由此次授权检查补齐；该历史快照没有修改。

实际处理仅修改源文件的三个文本范围：删除 `ssdf` 的主机块，以及 `control-plane`、`nfs` 中各一处 `ssdf` 引用。保留真实 Master 214、Worker 215，`nfs` 仍由215承担；`worker` 组保留两台主机，空 `registry` 组保持原样。其他配置及身份字段未改动，不记录凭据。

候选文件与原配置深复制后仅移除上述条目的预期结构完全一致；替换前以文件摘要检查防止覆盖并发变更，采用原子替换，保留原owner与0644权限。写后复核实际字节和配置结构均与候选一致，剩余角色引用有效。没有新建备份文件、改动旧任务快照、修改业务代码或二进制，也没有重启服务或重新触发安装。

当前可以确认源配置已修正，不能据此宣称Neo4j安装成功。下一步由新任务读取修正后的源配置，分别确认所有主机Greetings通过、组件部署终态和实际Neo4j功能；旧失败任务保留原始快照。元数据继续为 `unverified`。

## HELM-44 来源定位

- 用户本轮121安装 Neo4j 的关键任务日志；仅记录脱敏后的阶段、主机名及空地址错误，不复制完整配置或凭据。
- `g_web_installer/internal/service/component/component.go:17`、`:62`、`:65`：读取集群源配置，构造 KK 命令，写入任务配置。
- `g_kube_installer/cmd/kk/pkg/pipelines/install_components.go:28`：Greetings 在组件部署之前。
- `g_kube_installer/cmd/kk/pkg/bootstrap/precheck/module.go:44`：Greetings 使用 Runtime 主机集合。
- `g_kube_installer/cmd/kk/pkg/common/kube_runtime.go:80`：从角色组去重加入运行主机。
- `g_kube_installer/cmd/kk/apis/g_kube_installer/v1alpha2/default.go:161`：主机默认化及地址回退。
- `g_kube_installer/cmd/kk/apis/g_kube_installer/v1alpha2/cluster_types.go:286`：角色引用主机的存在性校验。
- `g_kube_installer/cmd/kk/pkg/core/connector/dialer.go:48`、`core/connector/ssh.go:180`：构造连接参数和空SSH地址校验。

[返回案例索引](../README.md)
