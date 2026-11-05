# HELM-46：Neo4j Helm 升级时缺少 neo4j 配置导致模板渲染失败

项目：g_web_installer、g_kube_installer。记录日期：2026-11-04；更新日期：2026-11-05。记录状态：214 测试集群已复现相同 Helm 模板错误；客户现场修复、备份和恢复待验证。

适用环境：用户说明这是另一个环境。现场 Helm release 为 `neo4j`、命名空间为 `neo4j`。用户回传截图显示 Pod `neo4j-0` 使用 `digiwin.gkubeinstaller.local:444/bitnami/neo4j:5.26.11`，状态为 `1/1 Running`、重启次数为 0；PVC `data-neo4j-0` 为 `Bound`，绑定 PV `pvc-36272ae5-1ef7-41dd-9194-26c89a2e6db9`，容量 8Gi、访问模式 RWO、StorageClass 为 `nfs-default`。用户确认 Windows 桌面根目录的 `neo4j.tgz` 是客户安装包，包内 Chart 为 0.4.14、appVersion 为 5.26.11；现场 release 的完整 manifest、有效参数和 Secret 所有权尚未核实。用户后续截图已确认 PVC 挂载和容器运行身份，但数据库及事务日志的运行时有效路径、Helm 版本和业务数据状态仍未确认。不能沿用 BK-41 中另一客户环境的 Chart、PVC 或 NFS 信息。

## 问题表现

用户用本地 Neo4j Chart 对 `neo4j` release 执行 `helm upgrade --reuse-values` 并补充 APOC 配置，Helm 报模板渲染错误：`neo4j/templates/neo4j-svc.yaml` 中访问 `.Values.neo4j.edition` 时发生 `nil pointer evaluating interface {}.edition`。执行结果为 `UPGRADE FAILED`；这不是数据库认证、APOC 导出或数据恢复阶段的错误。

2026-11-05 客户从 master 使用 `kubectl exec -it` 直接启动 Pod 内的 `cypher-shell` 并连接 `system` 数据库，截图仅显示 `Error from server:`，没有后续错误详情，也未显示成功进入客户端。此输出不足以判断是 exec 通道、交互终端、客户端启动还是数据库认证问题；需要分阶段检查。未读取或记录密码。

后续截图中，指定或不指定容器执行 `/bin/bash` 均仅显示空的 `Error from server:`，执行 `/sh` 也返回同样提示；其中 `/sh` 不是常见的 `/bin/sh` 路径。执行 `/bin/ash` 时，容器运行时明确报告该文件不存在并退出码为 126，这仅证明该次 exec 请求到达容器运行时，不能推断其他请求的通道正常。当前尚未确认 `/bin/bash` 的实际存在性，也不能据此断定 TTY、网络、认证或客户端故障的具体原因。

## 原因与证据边界

错误直接表明本次渲染中取不到 `.Values.neo4j.edition` 的父级配置。本地 KK 实际内嵌 `cmd/kk/pkg/component/neo4j.tgz` 的 `neo4j/templates/neo4j-svc.yaml` 第一行要求读取 `neo4j.edition`；包内默认 values 含 `neo4j.edition=community`。截图只提供文件路径和模板报错，并不证明客户执行的文件内容与本地内嵌包一致。

`--reuse-values` 复用旧 release 的 Helm values。旧版与新版 Chart 的 values 结构不同时，复用的配置可能无法满足新模板；旧配置为缺少 `neo4j` 的 null 或其他覆盖方式也可能触发该错误。客户提供安装包的 Chart 版本已核对，但现场有效 values 结构及完整 manifest 未核实，不能仅凭包版本将跨 Chart 或某个缺失原因写成现场已确认根因。截图确认查询时原名 PVC 处于 Bound，但不证明该 PVC 的历史身份、数据是否完好或业务是否可用。

用户确认 Windows 桌面根目录的 `neo4j.tgz` 为客户安装包；只读校验结果的 SHA-256 为 `63c5ef5b5195cf56948bd1d09bf0f645d084ff895749ad68d512b8195863039e`，与 Web 仓库根目录旧包一致。该包的 StatefulSet 卷声明模板名为 `data`，其中 `kind: PersistentVolumeClaim` 缩进 6 列，与现场 grep 结果高度一致。这支持该命中属于嵌套卷声明的判断，但不能单独证明线上实际 values、完整渲染 manifest 或不存在独立顶层 PVC。

## PVC 所属关系补充证据

2026-11-05 用户回传 `data-neo4j-0` 当前 PVC UID 为 `36272ae5-1ef7-41dd-9194-26c89a2e6db9`，其 ownerReferences 和所查询的 Helm 注解为空；StatefulSet 的 PVC retention 字段查询为空。以上是查询时的现场结果，不能单独证明 Helm 删除或 StatefulSet 变更后 PVC 一定保留，也不证明历史身份和数据完好。

用户提供的 `helm get manifest` 过滤结果包含有嵌套缩进的 `kind: PersistentVolumeClaim`。该文本与客户安装包中的 StatefulSet 卷声明模板高度一致，仅凭 grep 命中不能认定它是 Helm 直接管理的顶层 PVC；需要按 YAML 对象层级进一步确认。尚未执行卸载或其他删除操作，也未确认存在可恢复备份。

## 客户现场挂载、权限与服务信息

用户回传截图确认，Pod 的 `data` 卷引用 PVC `data-neo4j-0`，将 PVC 根目录挂载到 `/bitnami/neo4j`，未设置 `subPath` 或 `subPathExpr`。容器内 `id` 显示 UID、GID 和组均为 `1001`；`stat` 显示 `/bitnami/neo4j` 属主为 `0:0`、权限为 `777`，`/bitnami/neo4j/data` 和 `/bitnami/neo4j/data/transactions` 属主均为 `1001:1001`、权限均为 `755`。这些结果证明上述目录存在和当前命令身份，不能单凭它们确认数据库和事务日志的运行时有效目录或业务数据完整性。

客户 PV 显示 NFS 服务为 `nfs.cluster.local`，目录为 `/fs_zsk/neo4j-data-neo4j-0-pvc-36272ae5-1ef7-41dd-9194-26c89a2e6db9`，回收策略为 `Delete`。该策略意味着 PVC 被删除后可能触发底层 PV 回收，不能为升级删除原 PVC/PV。该地址和路径仅属于本客户现场。

现场 `neo4j` Service 为 NodePort，ClusterIP 为 `10.233.38.81`；Bolt 为 `7687:30032`，HTTP 为 `7474:30030`，HTTPS 为 `7477:30031`。Pod 中 `neo4j-secrets` 和 `https-certs` 卷分别引用名为 `neo4j` 和 `neo4j-https-certs` 的 Secret；只记录名称，没有读取、保存认证值。Secret 所有权、原业务访问配置、备份和恢复能力仍待核实，不能仅凭这些名称假定卸载后会保留或可直接用于新 Chart。

## 历史配置方案线索

2026-11-04 用户提供另一环境的手工配置方案，称当时备份失败、镜像可能也是 5.26.11。所示方案使用 `/bitnami/neo4j/conf` 持久配置、`/opt/bitnami/neo4j/labs` 加载 APOC，并补 Pod 标签；它与 [BK-35](../06_Web备份恢复与导入/BK-35.md) 的旧 Bitnami 场景相似，但不能据此认定是同一现场或说明当前 Helm 错误的根因。

历史 BK-35 的测试库曾验证 APOC 注册和手工导出；另在 [BK-37](../06_Web备份恢复与导入/BK-37.md) 的 5.26.11 同款测试中，非空图实际导出报 `ClassNotFoundException: com.google.common.collect.Iterables`。二者是不同阶段及验证范围，不能推断当前环境也存在该错误；当前场景尚未核实线上完整 Chart 渲染结果、插件目录、配置来源或实际导出结果。

## 只读排查与处理方向

先确认现场实际部署和旧 Helm values 的结构，只输出必要字段，不输出完整配置或账密：

```bash
helm list -n neo4j
kubectl -n neo4j get pod,pvc
helm get values neo4j -n neo4j --all -o json | jq -r '.neo4j | type'
```

`jq` 输出 `null` 表示原 release 的合并后 values 中 `neo4j` 为 null 或不存在；`object` 表示它是对象，还需继续检查字段及新旧 Chart 是否兼容。字段类型本身不验证数据库状态。

补充核对客户现场 Pod 实际卷挂载、values、Secret 的引用与现网参数、新旧 Chart 差异及可恢复备份后，再制定复用原 PVC 的操作。不要仅因缺少 edition 就追加参数后重试；新旧 Chart 的卷模板、镜像路径和身份配置可能不同。未完成核查前，不对客户现场删除 PVC、卸载原 release 或无条件使用 `--reset-values` / `--force`。

## 2026-11-05：214 使用客户原包复现

用户明确要求卸载 214 原 Neo4j 服务，使用桌面客户原包还原并比较。操作前原 release 为 Chart 5.3.0 / Neo4j 5.26.28；原 PVC `data-neo4j-0` 包含由 5.26.28 使用的数据，因此没有让 5.26.11 挂载或写入该卷。

- 已卸载原 `neo4j` release 并保留 Helm 历史；原 release 管理的认证 Secret `neo4j-auth` 随卸载删除，旧 release 修订仍在历史中。未读取或记录认证值。
- 原 PVC `data-neo4j-0` 卸载后仍为 `Bound`，UID `13c0482c-770a-44c7-bfd0-00e32b10d8ef`，PV `pvc-13c0482c-770a-44c7-bfd0-00e32b10d8ef`，与操作前一致。
- 新建隔离测试 PVC `neo4j-legacy-repro-20261105`，UID `9e95ec8e-64fe-4ec6-96f2-07977bf68d46`，8Gi、RWO、StorageClass `nfs-default`。使用客户桌面原包，通过 `persistence.existingClaim` 指向该测试卷安装 `neo4j`，release revision 2、Chart 0.4.14、appVersion 5.26.11。
- 测试 Pod `neo4j-0` 在 `worker01` 为 Running / Ready，使用 `registry.digiwincloud.com.cn/bitnami/neo4j:5.26.11`，测试卷挂载到 `/bitnami/neo4j`；HTTP NodePort 请求返回 200。
- 对新 KK 包使用客户相同的 `--reuse-values` 和三项 APOC 参数执行 `helm upgrade --dry-run=client`，退出码 1，实际报错与截图一致：`neo4j/templates/neo4j-svc.yaml` 访问 `.Values.neo4j.edition` 时出现 `nil pointer evaluating interface {}.edition`。该命令只模拟渲染，没有执行实际升级或更新 Kubernetes 资源；测试 release 仍为 5.26.11。

这次用独立 PVC 避免覆盖 214 现有数据，因此测试 release 设置了 `persistence.existingClaim`，没有走客户原包默认的 `volumeClaimTemplates` 创建路径。测试镜像仓库前缀与客户现场不同，尚未核对两侧镜像摘要；HTTP 200 和 Pod Ready 不证明认证、客户真实数据、APOC 导出或 Web 备份成功。此前的 PVC 内容复制与文件比对也不能替代可恢复备份和隔离恢复验证。

## 2026-11-05：客户 PVC 查询与旧版 APOC 配置复现

用户追问前述 PVC 查询和历史手工配置命令是否也已复现。为保留 214 已有 PVC 和正在运行的 `neo4j` 命名空间，另在隔离命名空间 `neo4j-legacy-check` 安装客户提供的 Chart 0.4.14 / Neo4j 5.26.11，release 仍为 `neo4j`。默认 `volumeClaimTemplates` 创建 PVC `data-neo4j-0`，UID 为 `20b21eeb-493a-4fbe-bfda-f9f8e676bed8`，8Gi、RWO，StorageClass 为 `nfs-default`。Service 使用 `ClusterIP` 避免与原 NodePort 冲突，Pod 固定在 `worker01` 以使用该节点缓存的 `registry.digiwincloud.com.cn/bitnami/neo4j:5.26.11` 镜像；测试命名空间和镜像仓库与客户现场不同，双方镜像摘要未比较。

- 隔离 PVC 的 ownerReferences 和 Helm release 注解为空；旧包使用的 `volumeClaimTemplates` 中包含缩进的 `kind: PersistentVolumeClaim`，与客户过滤输出一致，不表示 Helm 直接管理独立 PVC。214 的 StatefulSet retention 实际显示 `whenDeleted: Retain`、`whenScaled: Retain`，与客户查询字段为空存在差异；不能推断差异成因或由此保证客户卸载安全。
- 测试 Pod 将该 PVC 挂到 `/bitnami/neo4j`，`/opt/bitnami/neo4j/conf` 使用临时卷。确认新测试 PVC 不含同名文件后，按用户给出的流程初始化持久配置，设置 `server.directories.plugins=/opt/bitnami/neo4j/labs`、`apoc.export.file.enabled=true` 和 `apoc.import.file.use_neo4j_config=true`，并执行标签 patch 与 rollout restart。
- 重启日志出现 `Copying mounted configuration` 和 `Found mounted ... conf`；启动脚本的 skip 描述是跳过默认配置生成，不是跳过复制。重启后仅筛选运行配置的上述三项，结果与 PVC 中一致。这证明测试中配置复制及落盘，不单独证明客户现场配置生效。
- 隔离测试期间未获取、输出或保存账号密码。为验证非空导出，仅在该测试 PVC 临时添加关闭认证的设置并重启；确认 `apoc.export.cypher.all` 已注册后创建两个合成节点及一条关系，直接调用该过程，实际退出码为 1，报 `ClassNotFoundException: com.google.common.collect.Iterables`，与历史 BK-37 的 Guava 缺类现象一致。该调用不是 Web 异步备份任务，也不能据此认定客户当前环境出现同一错误。
- 测试后已删除本次合成节点和临时导出文件，节点计数复查为 0；从 PVC 删除临时关闭认证的设置后，Pod 重启完成且 Ready，运行配置仍保留上述三项 APOC 设置。空密码执行只读查询返回 unauthorized、退出码 1，证明该测试实例已重新启用认证；未读取账号密码。主命名空间 `neo4j` 的 Pod 仍 Ready，原 PVC UID `13c0482c-770a-44c7-bfd0-00e32b10d8ef` 仍为 Bound。

无条件复制配置文件只在预先确认目标文件不存在的新测试卷执行；不能在客户已有 PVC 上照搬，否则会覆盖原配置。标签 patch 若已触发滚动，紧接着再次 rollout restart 可能引起重复重启。

## 验证与遗留

客户现场部分仅依据用户回传结果和本地 Chart 分析，未访问或修改客户环境。214 已按用户授权卸载原 Neo4j 并安装客户原包；Helm 客户端模拟复现模板错误，另一个隔离环境复现 PVC 模板查询、旧版配置及非空 APOC 导出的 Guava 缺类。临时关闭认证的设置已移除，重启后通过空密码拒绝验证认证已恢复。客户现场已确认 PVC 挂载、容器执行用户、目录属主、NFS 路径、Service 端口和 Secret 引用名称；完整 manifest、数据库与事务日志运行时有效路径、Secret 所有权、可恢复备份及业务数据仍未核实。客户修复、真实 Web 备份及恢复仍未验证。

[返回案例索引](../README.md)
