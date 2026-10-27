# HELM-41：KK安装Seata Server与业务分布式事务接入边界

项目：g_kube_installer。记录日期：2026-10-22。记录状态：源码结论与内嵌制品已核对，业务接入待验证。

适用环境：本地 KK test 分支 HEAD `9a73986d8382ce2830273c2c01ba7f404598b5fc`，实际内嵌 `cmd/kk/pkg/component/seata.tgz`；Chart 名称 seata-server、Chart version 1.1.0、appVersion 2.6.0，镜像 tag 2.6.0.jdk17。适用于消费该制品的在线/离线安装。未指定现场 Kubernetes/OS 版本，不能据此推断旧 KK 二进制、已有 release 或业务服务的接入状态。

## HELM-41 问题与表现

用户在学习 AT、XA、TCC、Saga 与 Seata 的关系后，询问 KK 组件列表中安装的是否就是 Seata 分布式事务框架。本轮是组件身份和安装边界核查，没有提供现场报错，也未观察到故障。

## HELM-41 最终根因或已确认边界

- 是同一个 Seata 项目。KK 的 Seata 组件部署的是 Seata Server 服务端，用于承担事务协调者 TC 的职责，管理全局事务、分支事务状态并协调提交或回滚。
- KK 安装链路释放并同步内嵌 `seata.tgz`，发布 Nacos 配置，再执行 Helm 安装。它不是把 KK 自身的安装任务自动变成 AT、XA、TCC 或 Saga 事务。
- 实际归档声明镜像 `registry.digiwincloud.com.cn/bitnami/dap-seata-server:2.6.0.jdk17`，Chart 默认 `STORE_MODE=db`，配置模板指向 MariaDB 的 seata 库保存协调端事务状态，并使用 Nacos 作为配置/注册中心。镜像仓库等值可由安装参数覆盖，实际运行对象仍需按现场核对。
- 服务端事务端口默认 8091，默认 NodePort 为 30091；Go 安装参数可以覆盖 NodePort。端口或 Pod 就绪只代表部署/连通层面的条件，不能证明分布式事务业务已生效。
- 业务服务还需要接入匹配的 Seata 客户端，承担事务管理者 TM、资源管理器 RM 的相关职责，配置事务服务组和事务边界，并选择适合业务的事务模式。TCC 仍需要实现业务的 Try、Confirm、Cancel。
- KK 会发布 `seataServer.properties` 和 `seata-client.properties`；后者包含 `vgroupMapping.default_tx_group=default`、`client.undo.logTable=undo_log`。发布这些配置不等于业务库已创建 undo_log，也不等于业务应用已经引入 SDK、透传事务上下文或参与了全局事务。

## HELM-41 关键源码与制品证据

| 位置 | 已核对事实 |
|---|---|
| `g_kube_installer/cmd/kk/pkg/component/tasks.go:39` | `go:embed` 包含 seata.tgz |
| `tasks.go:1243` 的 ReleaseSeataChart | 从嵌入文件系统打开 seata.tgz，释放安装包 |
| `tasks.go:1266` 的 SyncSeataChart | 将安装包复制到临时目录 |
| `tasks.go:1279` 的 DeploySeata | 执行 `helm upgrade --install seata ... --namespace seata`，传入安装参数 |
| `g_kube_installer/cmd/kk/pkg/component/module.go:724` | Seata 任务顺序为释放、同步、发布 Nacos 配置、部署 |
| `tasks.go:1319` | 渲染并发布服务端与客户端配置 |
| `g_kube_installer/cmd/kk/pkg/component/templates/nacos.go:9` | SeataServer 模板声明 `store.mode=db`，MariaDB 的 seata 库及 global_table、branch_table 等 TC 状态表 |
| `templates/nacos.go:60` | SeataClient 模板包含事务组到 default 集群的映射 |
| `seata.tgz` 内 `seata/Chart.yaml` | Chart 1.1.0、appVersion 2.6.0 与 Seata Server 镜像声明 |
| `seata.tgz` 内 `seata/values.yaml` | 镜像、数据库存储模式、8091 服务端口及 Nacos 相关配置 |

实际归档大小 37203 字节，SHA-256 为 `b8158fa15094d1ea3073cdcd8edabcd2a08cc2aa46a8b34cdcacba89b709059f`。这是本轮检查的本地制品身份，不是运行中容器镜像或现场配置的校验证据。

## HELM-41 处理方案与后续接入检查

本轮无需修改安装器。若目标是让业务使用分布式事务，应在业务服务侧继续检查：

1. 目标环境实际部署的 Seata Server 版本、可达地址、注册中心和事务存储是否符合配置。
2. 业务是否引入相匹配的客户端组件，是否能找到事务服务组对应的 TC。
3. 业务是否明确采用 AT、XA、TCC 或 Saga，并完成该模式要求的资源管理、事务边界和跨服务事务上下文传播。不能仅凭 Seata Server 已安装推断上述步骤已经完成。
4. 对采用的模式执行真实成功与失败场景，分别验证提交、回滚或补偿，以及重试后的业务数据结果。TCC 还需验证幂等、空回滚和防悬挂。

这些步骤是后续检查方案，本轮没有执行，也没有推断具体应用当前使用哪种模式。

## HELM-41 验证结果与遗留事项

已只读核对本地安装源码和实际内嵌归档，确认 KK 安装的 Seata 组件身份及其职责边界。没有修改业务代码或安装包，没有连接集群、部署、重启、执行事务测试或检查业务 SDK。不能据此确认任何现场应用的分布式事务功能已生效，metadata 保持 unverified。

本轮新增本案例及索引、元数据，仅完成本地文档归档；没有提交、推送、发布或写入向量库。现有其他工作区改动保持原样。

## HELM-41 来源定位

- 上述 KK 本地源码和 `cmd/kk/pkg/component/seata.tgz` 内的实际文件。
- [Seata 事务角色术语](https://seata.apache.org/docs/overview/terminology/)：TC、TM、RM 的职责。
- [Seata TCC 模式](https://seata.apache.org/docs/user/mode/tcc/)：业务参与者需要实现 Try、Confirm、Cancel。
- 历史 Nacos/Seata 部署故障分别参见 [HELM-12](HELM-12.md)、[HELM-17](HELM-17.md)、[HELM-18](HELM-18.md)、[HELM-19](HELM-19.md)。这些案例不能替代本轮业务事务接入验证。

[返回案例索引](../README.md)
