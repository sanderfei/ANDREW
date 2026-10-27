# HELM-38：Neo4j安装无外部中间件依赖但需要持久化存储

项目：g_web_installer / g_kube_installer。记录日期：2026-10-16。记录状态：源码结论。

适用环境：本地 KK test 分支 HEAD `9094b52` 的实际内嵌 `cmd/kk/pkg/component/neo4j.tgz`，Chart version 5.3.0、appVersion / 镜像 tag 5.26.28；Community 单副本。适用于消费此包的在线/离线组件安装。Kubernetes/OS 的现场版本未指定，不能据此推断旧 KK 二进制或已有 release 的配置。

## HELM-38 问题与表现

用户询问 Neo4j 安装是否依赖其他组件。本轮没有提供安装报错，也未观察到现场故障。

## HELM-38 最终根因或已确认边界

- 当前安装链路没有要求先安装 MySQL、MariaDB、PostgreSQL、Redis、Nacos、ZooKeeper 等其他中间件。Web 的显式组件依赖校验只有 pgvector 对 PostgreSQL 的要求；Neo4j 是优先级 0 的数据组件。
- KK 的 Neo4j 任务为释放内嵌归档、同步归档、执行 Helm 安装，没有其他数据库初始化任务；包内 Chart.yaml 未声明子 Chart 依赖，未包含 charts 子目录。
- 基础条件是可用的 Kubernetes、容器运行时/网络、Helm/kubectl、可拉取的 Neo4j 镜像，以及可用的持久化存储。
- 当前包 `volumes.data.mode=defaultStorageClass`，默认申请 `10Gi`、`ReadWriteOnce` PVC，使用集群默认 StorageClass。values 中 dynamic 分支的 `storageClassName: neo4j` 和 100Gi 未被当前模式选中。
- 项目创建集群时基础模块包含 NFS provisioner；其实际内嵌包创建 `nfs-default` 且 `defaultClass=true`。因此沿用项目默认集群配置时，Neo4j 的存储间接依赖 NFS 服务和 provisioner。Neo4j 本身没有写死必须使用 NFS，其他可用默认 StorageClass 也可承接其默认 PVC。
- 单独执行组件安装的 Pipeline 不安装 NFS 基础模块；已有集群须预先具备存储。缺少可供绑定的存储可能使 PVC/Pod Pending，这属于存储条件，不是缺少外部数据库。
- 日志、导入、备份等目录默认共享 data 卷；这不代表自动备份已开启。APOC 为 Pod 内插件能力，不是需要独立部署的服务；本轮只核对包内 APOC 配置，不声称验证插件加载或在线备份功能。

## HELM-38 处理方案

无需为 Neo4j 额外选择数据库、缓存或注册中心。安装前在目标集群按需核对：

```bash
kubectl get storageclass
kubectl get pods -A -o wide
# 安装后检查数据卷及实际调度状态
kubectl get pvc,pods -n neo4j
kubectl describe pvc data-neo4j-0 -n neo4j
```

上述 PVC 名称适用于本项目默认 release/name；自定义时以实际列表为准。若沿用 NFS 默认存储，确认 NFS/provisioner 可用和节点具备挂载能力；若使用已有其他存储，确认默认 StorageClass 正确。若无默认存储，应先配置可用默认类，或按实际 Chart volumes 模式明确指定可用存储。不要为了排查而删除现有 PVC 或数据。

## HELM-38 验证证据与限制

本轮已读取 Web/KK 源码、实际归档中的 Chart.yaml、values.yaml、StatefulSet/卷/Hook 模板及 NFS Chart 存储配置。Neo4j 归档大小 40459 字节，SHA-256 为 `bd7d30a4c698ca67ebe719cc083895b86a4b6acac1c3f710173ed6091e497543`。未修改业务代码或安装包，未连接服务器、未安装或重启组件，未执行以上现场检查命令；没有数据库功能验证，因此 metadata 保持 unverified。

## HELM-38 补充：集群内 Service 连接地址（2026-10-16）

用户继续询问 Neo4j svc 内部连接地址。已核对实际内嵌包 `templates/neo4j-svc.yaml`、`templates/_helpers.tpl` 和 `values.yaml`：Service 默认名称取 Helm release 名称；KK 使用 release=neo4j、namespace=neo4j，且未覆盖 Service 名称。

在集群 DNS 后缀为 `cluster.local` 的默认环境，业务程序使用：

```text
bolt://neo4j.neo4j.svc.cluster.local:7687
```

HTTP 入口为 `http://neo4j.neo4j.svc.cluster.local:7474`。同一命名空间的 Pod 可用 `bolt://neo4j:7687`；其他命名空间通常可用 `bolt://neo4j.neo4j:7687`。两个连续 neo4j 分别为 Service 名称和命名空间。自定义集群域时替换 `cluster.local`，自定义 release/namespace 时按实际对象调整。

此处使用 Service 端口 7687/7474；30032/30030 是 NodePort，供节点 IP 入口使用。包中另有 neo4j-admin 管理 Service，普通应用连接使用上述 neo4j Service 即可。

上述为当前源码和归档配置推导的默认地址，本轮未连接现场或执行 DNS/认证/读写验证，不声称现场可达。索引编号、案例数量及 metadata 的 unverified 状态不变。

## HELM-38 214 现场核对尝试（2026-10-16）

用户说明已安装，并授权直接查看 214。使用固定别名 `ssh codex-test-214`，以 BatchMode 和 10 秒连接超时尝试只读获取 neo4j Service、Endpoints、Pod 及 CoreDNS 集群域。SSH 在认证阶段返回 `Permission denied (publickey,password)`，退出码 255；远端检查命令均未执行。

本轮只能确认当前授权 SSH 路径无法登录，不能确认 214 的实际 Service、端点、Pod 或连接可用性，也不能用历史现场结果代替本次验证。`bolt://neo4j.neo4j.svc.cluster.local:7687` 仍是当前包的默认地址。需恢复此 SSH 别名的现有密钥授权后再核对；没有查找或记录密码、私钥。metadata 保持 unverified。

## HELM-38 用户提供的 214 Service 现场证据（2026-10-16）

来源：用户在目标集群执行 `kubectl get svc,endpoints -n neo4j` 后提供的命令输出；不是本助手通过 SSH 获取。

已确认 Service/neo4j 位于 neo4j 命名空间，类型 NodePort，ClusterIP 为 10.233.23.21；端口映射为 Bolt 7687→30032、HTTP 7474→30030、HTTPS Service 端口 7477→30031。其 Endpoints 包含 10.233.84.9 的 7687、7474、7473 端口，当前 Service 有后端端点。另有 ClusterIP 类型的 neo4j-admin 管理 Service。

集群内应用可填写 `bolt://neo4j.neo4j.svc.cluster.local:7687`（前提是集群 DNS 后缀为 cluster.local）；同 namespace 可简写 `bolt://neo4j:7687`，跨 namespace 可简写 `bolt://neo4j.neo4j:7687`。当前 Service IP 形式为 `bolt://10.233.23.21:7687`。HTTP 入口为 `http://neo4j.neo4j.svc.cluster.local:7474`。应用应使用 Service DNS，避免依赖会随 Pod 重建变化的 10.233.84.9。

该证据确认了实际 Service 名称、命名空间、端口和已发布的后端端点；尚未验证集群 DNS 后缀/解析、网络可达、数据库认证及读写功能。不能将 Endpoints 非空描述为数据库功能已验证，metadata 保持 unverified。此前 SSH 认证失败是独立的访问限制，用户提供的新证据补足了 Service 层面的信息。

## HELM-38 来源定位

- `g_web_installer/internal/service/component/component.go`：InstallComponentJob / validateInstallComponentDependencies。
- `g_web_installer/internal/service/component/component_order.go`：Neo4j 安装优先级。
- `g_kube_installer/cmd/kk/pkg/component/tasks.go`：go:embed、ReleaseNeo4jChart、SyncNeo4jChart、DeployNeo4j、DeployNfs。
- `g_kube_installer/cmd/kk/pkg/component/module.go`：DeployClusterBaseModule / deployNeo4j。
- `g_kube_installer/cmd/kk/pkg/pipelines/install_components.go`：组件安装 Pipeline。
- `g_kube_installer/cmd/kk/pkg/component/neo4j.tgz`：包内 Chart.yaml、values.yaml、templates/neo4j-statefulset.yaml、templates/_volumeTemplate.tpl、templates/delete-loadbalancer-hook.yaml、templates/neo4j-svc.yaml、templates/_helpers.tpl。
- `g_kube_installer/cmd/kk/pkg/component/nfs-subdir-external-provisioner.tgz`：包内 values.yaml 的 storageClass 配置。

[返回案例索引](../README.md)
