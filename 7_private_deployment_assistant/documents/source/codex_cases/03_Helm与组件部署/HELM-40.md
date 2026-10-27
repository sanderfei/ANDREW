# HELM-40：新增StarRocks 3.5组件、PVC密码初始化与私有镜像准备

项目：g_web_installer / g_kube_installer。记录日期：2026-10-21。记录状态：初版KK/Web已发布121；API登录凭据校验未通过，组件任务未启动；本地补充未提交发布。

适用环境：本地 Web release、KK test 工作区；基于官方 `starrocks/kube-starrocks` Chart 1.11.4 / appVersion 3.5-latest。模板按 Kubernetes 1.23.10、1.32.8 核对。后续按用户授权，在 214 集群手动 Helm 安装：master 10.40.46.214、worker 10.40.46.215，Kubernetes 1.32.8，默认存储类 nfs-default，linux/amd64。实际 FE/BE 构建为 3.5.21-85fccf8；SELECT VERSION() 返回的 8.0.33 是 MySQL 协议兼容版本，数据库构建以 current_version() 和 SHOW BACKENDS 为准。121 提供已有镜像缓存及 MySQL 8.0.26 客户端，没有发布或重启 Web/KK。

## HELM-40 问题与表现

用户要求在组件安装中新增 StarRocks 3.5，使用 kube-starrocks 包；密码、CPU/内存与持久化沿用其他组件的配置方式。官方默认镜像需在 121 拉取后重新打标签，推送到 `registry.digiwincloud.com.cn`，安装包引用推送后的私有地址。

## HELM-40 已确认边界与实现

- Web 新增 `starrocks` 组件目录项、安装参数校验、安装优先级、命名空间分类和镜像版本识别。初始账号固定 root，密码必填；CPU/内存分别应用于 FE 和 BE。版本识别优先 FE，避免把 Operator v1.11.4 当成数据库版本。没有修改前端。
- KK 增加组件常量、Module 分支、归档释放/同步、安装和已部署检查，`tasks.go` 的 go:embed 增加 `starrocks.tgz`。命名空间、release、StarRocksCluster 名称均为 starrocks。
- 包含 Operator、1 FE、1 BE；CN 和 FE Proxy 默认关闭。Operator 只监控 starrocks 命名空间，并读取实际集群 DNS 后缀配置。单 BE 配置默认建表副本数为 1。
- 原始 Chart 的 FE/BE `storageSpec.name` 为空，不会声明数据 PVC。新包开启 FE 元数据/日志与 BE 数据/日志/spill 的 PVC，使用默认 StorageClass，与现有 NFS 配置衔接。未配置存储类时，CR 模板省略 storageClassName，避免生成 null 或显式空串。已核对 Operator v1.11.4 的 StorageVolume 使用字符串指针，PVCList 原样传给 PVC；显式空串会禁用默认存储类，省略字段才保留 nil。指定存储类及日志/spill 单独覆盖时仍保留配置值。
- 默认每个 FE/BE CPU request 500m、limit 2000m，内存 request 2Gi、limit 4Gi；FE JVM 堆上限按容器内存 50% 设置，避免保留原 Chart 的固定 8Gi 堆。
- 初始密码使用权限 0600 的临时 values 文件传给 Helm，结束后清理，不拼接到命令参数。原脚本把部分认证/SQL 错误当成功，已改为先核对配置密码、按需初始化、再次认证；SQL/认证失败返回非零，错误输出不包含密码。
- 初始化 Job 改为 post-install/post-upgrade hook，失败重试时可重新执行；Helm 等待资源和 Job。以上仍不能替代实际数据库读写验证。
- 数据目录与容量通过 Chart 的 storageSpec 配置；Web 沿用现有 username/password 和资源入参，没有新增数据目录、端口入参。KK 原有 port 字段可覆盖 SQL NodePort。安装后密码修改接口未新增 StarRocks 支持，不能通过重复安装宣称已改掉既有密码。
- 文件组织调整（2026-10-21）：初版将 DeployStarRocks.Execute 及相关逻辑集中在 starrocks.go，仅是文件组织选择，没有 Go 或 StarRocks 的技术要求。用户随后要求放入 tasks.go，现已将归档释放、同步、部署前检查、values 生成、安装及辅助函数整体迁入 tasks.go，在 Neo4j 与 RabbitMQ 实现之间放置，并补齐 strconv import、删除独立 starrocks.go。迁移后的代码正文与原文件逐字节一致，调用仍由 module.go 的 deployStarRocks 组织，沿用现有组件文件结构。

## HELM-40 数据与端口配置

| 用途 | 容器目录 | 默认 PVC 容量 |
|---|---|---|
| FE 元数据 | /opt/starrocks/fe/meta | 10Gi |
| FE 日志 | /opt/starrocks/fe/log | 5Gi |
| BE 数据 | /opt/starrocks/be/storage | 50Gi |
| BE 日志 | /opt/starrocks/be/log | 5Gi |
| BE spill | /opt/starrocks/be/spill | 5Gi |

默认 NodePort：FE SQL 30390→9030，FE HTTP 30380→8030，BE HTTP 30480→8040。
默认集群内 FE SQL 地址为 `starrocks-fe-service.starrocks.svc:9030`；本次已通过 Pod 内客户端访问，并通过 121 客户端实测 `10.40.46.214:30390`。宿主机并不自动具有集群域名解析能力，HTTP 导入的重定向边界见后文。
PVC 的 whenDeleted 为 Retain；现有 Web 卸载还会删除命名空间，其中 PVC 仍会被删除，后端文件由实际存储回收策略决定，不能将此配置描述为任何卸载方式都能保留数据。

## HELM-40 镜像准备与现场证据

| 官方默认镜像 | 私库地址 |
|---|---|
| starrocks/operator:v1.11.4 | registry.digiwincloud.com.cn/bitnami/starrocks-operator:v1.11.4 |
| starrocks/fe-ubuntu:3.5-latest | registry.digiwincloud.com.cn/bitnami/starrocks-fe-ubuntu:3.5-latest |
| starrocks/be-ubuntu:3.5-latest | registry.digiwincloud.com.cn/bitnami/starrocks-be-ubuntu:3.5-latest |

最初推送到 starrocks 项目收到 `unauthorized: project starrocks not found`。沿用其他组件已有的 bitnami 项目，修改上述仓库名，并同步调整父/子 values、KK 自定义 registry 覆盖、Web 版本识别及三个离线 manifest。未创建新的 Harbor 项目，未查看或归档登录凭据，推送客户端复用已有登录状态。

Operator 在 121 从 Docker Hub 拉取。FE/BE 直连拉取部分镜像层持续重试；先从官方 Registry 核对默认标签对应的 linux/amd64 manifest digest，再经 DaoCloud 加速源按该 digest 拉取，并在 121 补齐官方名称标签和私库标签：

| 官方 linux/amd64 镜像 | 本轮固定的源 manifest digest |
|---|---|
| Operator v1.11.4 | sha256:ed8b6082a47383f7043461f401eb6728517ea693c3bc03912e8c4d38d4a72d64 |
| FE 3.5-latest | sha256:26dc37ab626dbf9257d20ea7862932803709502451fcf3d9eb5d5a4ac4ba2c27 |
| BE 3.5-latest | sha256:292faab4956f98247921547d4827bcf5bb8213d22ac5dd4477839141cfddb603 |

三个镜像均已推送成功，并通过私库 manifest 读取核对返回的 digest：

| 镜像 | 私库 manifest digest |
|---|---|
| Operator v1.11.4 | sha256:38e852ab34bc7caa79d87860d422425c58dbce5318d6dbbb6c1baaab37191c82 |
| FE 3.5-latest | sha256:e74a1d91d7c469b6d2e19f889491104f8a68a8682cd7ff1e718622ec62ee6321 |
| BE 3.5-latest | sha256:a34e5cff9729eae0d2725ea0836e94fedb2479c44d67986c8fc93ca24ee49a47 |

BE 在 121 直推时连接存在 TCP 重传且速率低，已中止本轮直推；改为在 121 导出已打标签的本地镜像，由临时 go-containerregistry v0.20.4 客户端通过仅通向该私库的 TLS 转发通道上传，最终推送命令退出 0。上传计数达到 100% 后继续等待提交成功，随后读取私库 manifest 验证。未修改 Docker daemon 或全局网络配置；本轮临时导出、传输客户端/脚本/日志及转发通道均已清理。

已从官方 Registry 校验上述三个源 manifest 与 image config 的 SHA-256，并取得文件系统层 diff_ids。三个私库 manifest 引用的 image config digest 均与官方一致；121 上官方名称标签、私库标签对应的本地 Image ID 和 RootFS diff_ids 也逐一匹配。推送会重新编码部分压缩层，manifest/压缩层 digest 可能变化，不将压缩层 digest 相等作为必要条件。镜像仍使用官方默认 3.5-latest 标签，不能把该标签当成固定补丁版本；本轮同步不代表其他架构镜像已准备。

## HELM-40 操作与验证

1. 在 Web 组件安装请求或 KK 完整 config.yaml 的 `spec.system.components` 中选择 name=starrocks，填写 root 初始密码及 CPU/内存参数。字段以 KK 的 Component 模型与 tasks.go 的 buildStarRocksValues 为准，本案例不保存实际密码或客户配置。
2. 三个镜像已准备完成；KK test 与 Web release 的代码已按后续“提交starrocks代码”请求完成提交、推送和 PR 合并。Web/KK 二进制尚未发布，发布后再按现有流程执行组件安装；手工 Helm 成功不等于目标 Web/KK 入口已具备新能力。
3. 使用目标集群的实际 StorageClass、资源和端口配置；自定义数据挂载目录时，同步修改 FE meta_dir / BE storage_root_path。修改解压目录后，必须重新打包最终 tgz 并构建 KK。
4. 安装后分别检查 Operator、FE/BE、PVC、密码初始化结果，再通过实际账号进行建库/建表、写入、查询及需要时的导入导出测试。本次已在 214 完成这些手工 Helm 路径的现场检查与 SQL/JSON 数据核对，Web 组件接口和 KK 安装命令链仍待发布后验证。

已完成的开发验证：

- Web、KK 组件相关 Go 定向测试通过，包括账号/密码校验、特殊字符序列化、资源和私库覆盖、NodePort 校验、实际内嵌归档及 FE 版本识别。临时 Go 测试文件跑通后已删除。
- 密码脚本 bash 语法和模拟客户端检查通过，覆盖引号/反斜杠/换行、已初始化重试、SQL/认证/最终认证失败、命令替换不执行及密码不进入输出。模拟通过不等于真实 StarRocks 认证通过。
- 最终包 helm lint 通过；Kubernetes 1.23.10 和 1.32.8 的 helm template 均得到 13 个对象，CR 按随包 CRD schema 校验通过；实际启用镜像集合恰好为上述三个私库地址，初始化 Job 复用 FE 镜像。
- 对其他 26 个实际内嵌归档及组件 Go 安装器检查，未发现三个默认 NodePort 的重复固定值；这不代表目标集群的动态端口分配已检查。
- 将两个 Kubernetes 版本和自定义存储类/双数据盘场景的渲染 CR 交给官方 Operator v1.11.4 的真实 PVCList 函数检查：默认 5 个 PVC 的 StorageClassName 均为 nil，自定义场景的 6 个 PVC 保留各自配置值。检查通过后自动删除临时 Go 验证文件及源码夹具；该检查不代表现场 PVC 已绑定。
- 最终 tgz 与同级 kube-starrocks 解压目录的 36 个文件逐字节一致。当前归档 SHA-256 为 `7241321e2913bfcd71375dc7137f9cbf67eae3a26a201b9d271dba2111629c15`。
- Web 和 KK 编译通过。KK make kk 有原有 `hack/version.sh: GIT_MAJOR: unbound variable` 版本元数据告警，实际 Go 构建命令仍退出 0；未修改版本脚本来掩盖该告警。
- 文件迁移后再次核对：tasks.go 仅合入原代码并增加 import，迁移正文及其他 8 个已有改动/安装包文件的 SHA-256 保持一致；gofmt 和 git diff --check 通过。带项目构建标签的 go test ./cmd/kk/pkg/component 退出 0，输出为 no test files，仅证明包编译成功；make kk 退出 0，保留上述原有版本脚本告警。本次未新增测试文件，也未重跑 Helm 或现场数据库验证。
- 开发时 root swag.json 在用户已有工作稿上增加组件目录、安装与集群状态说明。本次提交进一步隔离：以仓库 HEAD 的完整 Swagger 为基础，仅增加 2 条组件路径与 5 个定义，共增加 238 行、删除 0 行；原有 OBS 接口和全部其他内容保留。用户原有 swag.json 工作稿及 pinpoint.tgz 的文件内容均未改变。

前序开发阶段尚未执行现场安装；后续 214 手动验证结果如下。再后续已完成源码 commit/push/merge，详见末尾交付记录；仍未发布或重启 Web/KK，未验证 Web/KK 安装入口、PVC 故障恢复或完整离线制品分发。metadata 的 verified 对应安装包的手工 Helm、认证与实际数据功能，不代表上述未执行路径已通过。

## HELM-40 214手动安装与功能验证（2026-10-21）

用户要求用本安装包在 214 集群模拟安装，再验证 MySQL 导入导出工具。安装前检查确认没有既有 StarRocks release、命名空间和 CRD，三个默认 NodePort 没有占用；通过明确的 /etc/kubernetes/admin.conf 核对目标 API 与 RBAC。

使用的实际归档未修改，SHA-256 仍为 `7241321e2913bfcd71375dc7137f9cbf67eae3a26a201b9d271dba2111629c15`。214 上的工作目录为 `/root/starrocks-validation-20261021-rcfdlp`。初始密码在目标机随机生成，以权限 0600 的 values.private.yaml 传给 Helm；密码未写入命令参数、案例或报告。

手工 values 配置初始密码与实际 DNS 后缀 cluster.local。私库下载缓慢，最初 Operator 启动后，FE 和初始化 Job 长时间处于 Pulling/ContainerCreating，首轮 post-install 等待超时。随后从 121 导出已经核对的同名 FE、BE、MySQL 8.4.2 镜像，使用内网直传，在 worker01 的 containerd k8s.io 命名空间导入；包内私库地址保持原值。工作节点 CRI 的 FE/BE/Operator image config ID 分别与 121 的 55278d3c…、59cd4bc2…、08c6b3e8…一致。此路径验证的是同内容镜像缓存安装，未将 FE/BE 的完整私库冷拉取记为通过。

镜像导入后，原先未启动的 Pod 仍停在拉取/终止流程。仅重建本次新增且确认没有启动过容器的 Pod，保留全部 PVC。重试手工 values 将 `operator.starrocksOperator.imagePullPolicy` 设为 IfNotPresent，沿用缓存启动新 Operator。归档默认 Operator 拉取策略仍是 Always，本次没有重打包或修改业务代码。

现场还记录到 12:00:33 Operator 因 `etcdserver: request timed out`、`leader election lost` 退出一次；之后 API `/readyz?verbose` 的 etcd 和其他检查恢复通过，新 Operator 成功工作。该短暂控制面超时的底层原因未定位，不能将安装成功写成整个集群该问题已修复。旧 Operator 确认容器已退出后清理，未重启 etcd、kubelet、containerd 或现有组件。

实际重试命令如下；values 文件含新生成的密码，仅在目标机 root 权限下保存：

```bash
export KUBECONFIG=/etc/kubernetes/admin.conf
helm upgrade starrocks /root/starrocks-validation-20261021-rcfdlp/starrocks.tgz \
  --namespace starrocks --wait --wait-for-jobs --timeout 15m \
  -f /root/starrocks-validation-20261021-rcfdlp/values.private.yaml
```

结果：命令退出 0，release revision 2 为 deployed；revision 1 的 history 保留 post-install 超时记录，当前显示 superseded。密码 Job 在 FE 启动期间重试后 Completed，并按 hook-succeeded 策略删除。最终 Operator、FE、BE 三个 Pod 均 1/1 Running、重启数 0，StarRocksCluster 的 phase/FE/BE 状态均 running；5 个 PVC 均 Bound 到 nfs-default，容量与上述表格一致。

实际功能证据：

- root 使用配置密码通过 SQL 查询，空密码连接返回 1045 Access denied。SQL NodePort 10.40.46.214:30390 同时通过集群内测试容器和 121 主机客户端访问。
- 代表性测试表含 BIGINT、VARCHAR、DECIMAL(18,2)、DATETIME、BOOLEAN、NULL，10 行覆盖中文、emoji、引号、反斜杠、制表符、换行、空字符串、大数精度和日期。
- MySQL 8.4.2 源表与 StarRocks 源表的排序规范输出逐字节一致；MySQL 纯数据 SQL 回灌和 JSON/Stream Load 回灌各 10 行，规范输出 SHA-256 均为 `9cbc75b7d2f055d987e928c238ac89735d258f92072466d2cddc1080a1a00f6a`。
- Stream Load 通过 BE NodePort 30480 直接调用，Status=Success、NumberTotalRows=10、NumberLoadedRows=10、NumberFilteredRows=0。通过 FE NodePort 30380 走重定向时，宿主机无法解析返回的 BE 集群 FQDN；本轮未修改宿主机 DNS，用 BE 端口完成验证。
- 标准 mysqldump 8.0.26、8.4.2 对当前构建直接导出均在注释式初始化 SET 处失败；完整 MySQL dump 直接重放同样失败，纯数据 SQL 经预建 StarRocks 表后可回灌。详细命令、错误与边界见 [BK-33](../06_Web备份恢复与导入/BK-33.md)。

最初验证脚本误向 mysqldump 传入了该工具不支持的 connect-timeout 参数；已移除并完整重跑，最终报告不使用该参数错误作为兼容性依据。该选项仅用于 mysql 客户端，导出子进程用外部超时约束。

临时 MySQL Pod、测试 Secret、121/214 临时 Python 脚本及 121 临时客户端配置已清理；121 两次 Docker 导出临时目录已自动清理，镜像接收进程退出 0。StarRocks、合成测试库、SQL/JSON 文件及两版客户端报告保留在 214；8.0 报告已复制到该目录的 client80/，10 个文件的 SHA-256 复制前后一致。清理测试容器后，通过 FE 自带客户端再次确认构建版本与两个成功回灌表的行数分别为 10、10。

凭据仅保存在 214 上权限 0600 的 starrocks-root-password、values.private.yaml、starrocks-client.cnf、stream-load.curl.conf 中，不归档文件内容。

| 交付检查 | 结果 |
|---|---|
| 范围与无关改动 | PASS：独立 StarRocks 安装与合成测试，已有工作区改动保留 |
| 敏感信息 | PASS：使用受限文件/Secret，案例与报告无实际密码 |
| 格式与测试 | PASS：文档/索引检查；认证、SQL 与两种数据回灌完成，mysqldump 失败已复现 |
| 构建与制品 | PASS：同一归档哈希、36 文件与解包目录一致；后续精确提交在隔离工作树构建 KK/Web 成功 |
| Git 交付 | PASS：KK PR #67、Web PR #418 均 merged，中央分支与预先构建的目录树一致 |
| 现场部署与功能 | PASS：手动 Helm 与 SQL/数据功能；Web/KK 发布及入口验证 NOT RUN |

## HELM-40 StarRocks代码提交、推送与合并（2026-10-21）

用户明确要求“提交starrocks代码”，按本次会话约定完成 Web 与 KK 的 scoped commit、push、PR 和 merge。Git 认证复用现有 credential helper，仅在进程内使用；未读取服务器凭据。两次使用普通 PR 合并接口，force_merge=false，均返回成功，随后读取 PR 确认 merged=true。

| 仓库与中央目标 | 实现提交 | PR | 合并提交 |
|---|---|---|---|
| g_kube_installer / upstream/test | bbbc5d79126d555eb4ba8d97f27adbbd34f1b54b | [#67](http://192.168.3.34/Installation-package/g_kube_installer/pulls/67) | 9a73986d8382ce2830273c2c01ba7f404598b5fc |
| g_web_installer / upstream/release | 373f3cbcc01bbbddefc95305029b8b100f6d8747 | [#418](http://192.168.3.34/Installation-package/g_web_installer/pulls/418) | 132955179ae4e494f984e4b615d7b293d9d4ee44 |

KK 只提交 8 个 StarRocks 相关文件，Web 只提交 7 个相关文件，PR 文件列表与该范围逐项一致。未提交既有 Pinpoint 归档改动，也未提交 Swagger 中其他变动；没有修改前端代码。Swagger 采用单独生成的 Git blob 暂存组件增量，工作稿仍原样保留，未用工作稿覆盖仓库原有接口文档。

精确提交验证在两份临时工作树中执行，避免把无关 Pinpoint 归档编入待交付的 KK。KK 执行 make kk 退出 0；Web 先预合并中央 release 当时最新提交 3920f348b0fca7d11c531331a07682f0fea5add8，再执行带项目三项构建标签、CGO_ENABLED=0 的 go build 构建 ./cmd/server，退出 0。KK 保留原有版本脚本的 GIT_MAJOR 告警。本轮沿用已完成的聚焦行为测试与 214 功能证据，没有新增测试文件或重复执行现场安装。

合并后用 git ls-remote 核对中央目标分支和个人源分支，确认实现提交已包含在中央分支中，中央合并提交的目录树与对应构建候选逐一一致；本地两个分支均 fast-forward 到中央合并提交。对提交前后工作区文件做 SHA-256 比较，原有内容保持不变，最终 KK 只剩 cmd/kk/pkg/component/pinpoint.tgz 修改，Web 只剩 swag.json 修改。临时构建工作树及其二进制均已清理。

本次完成的是代码交付，未发布到 121、未重启 Web/KK，也未执行 StarRocks 的 Web/KK 自动安装或 Web 备份恢复 API 验证。此案例与索引仅在 andrew 本地更新，未随上述两个代码 PR 提交或向量入库。

## HELM-40 访问域名与Web改动范围核对（2026-10-21）

用户询问是否具有类似 registry.<IP>.nip.io 的访问地址，以及 Web 是否只修改组件列表。本轮只读核对已合并提交、实际内嵌归档和 214 集群，没有修改安装配置或 Kubernetes 对象。

当前包不自动配置 StarRocks 的 HTTP 域名入口。starrocks.tgz 的 SHA-256 仍为 7241321e2913bfcd71375dc7137f9cbf67eae3a26a201b9d271dba2111629c15；归档没有 Ingress 模板，FE Proxy 默认关闭，FE/BE 使用 NodePort。KK 的 DeployStarRocks 和 buildStarRocksValues 传递密码、资源、镜像和 SQL 端口，没有调用 getServerHostUrl 或设置 Ingress host；Harbor 的 registry.<domain> / registry.<MasterIP>.nip.io 逻辑属于单独分支，不能据此推断 StarRocks 也有对应入口。

通过 ssh codex-test-214，使用明确的 /etc/kubernetes/admin.conf 查询 starrocks 命名空间：Ingress 数量为 0，服务端口如下。214 上同哈希归档的 helm template 输出也没有 Ingress；该操作仅渲染，没有安装或更新 release。

| 用途 | Service 端口 | NodePort | 214 示例入口 |
|---|---|---|---|
| FE HTTP | 8030 | 30380 | http://10.40.46.214:30380/ |
| FE SQL / MySQL 协议 | 9030 | 30390 | 10.40.46.214:30390 |
| BE HTTP / Stream Load | 8040 | 30480 | http://10.40.46.214:30480 |

从 214 节点本机请求 http://127.0.0.1:30380/ 返回 HTTP 401，确认 HTTP 入口有响应且要求认证；未读取密码、未完成网页登录，也未把 401 描述为管理页面功能已验证。本轮没有验证用户电脑到这些端口的网络路径。

若后续要求 http://starrocks.<IP>.nip.io 这样的标准 HTTP 域名入口，应为 FE HTTP Service 的 8030 端口增加 Ingress，并沿用 spec.system.domain / nip.io 的命名方式与 nginx IngressClass。nip.io 提供域名解析，HTTP 路由仍需配置；普通 HTTP Ingress 不能直接替代 MySQL 协议的 SQL 连接端口。该方案当前未实现，也没有擅自修改现有包或现场对象。

Web 实现提交 373f3cb 涉及以下 7 个文件：

| 文件 | 本次作用 |
|---|---|
| internal/service/component/component_list.go | 新增 StarRocks 列表项、账号密码要求及默认资源参数 |
| internal/service/component/starrocks_icon.go | 内嵌组件图标 |
| internal/service/component/component.go | 未填账号时补 root，校验账号固定 root、初始密码必填 |
| internal/service/component/component_order.go | 将 StarRocks 纳入数据存储组件的安装优先级 |
| internal/service/component/component_version.go | 支持核心工作负载镜像版本识别，优先 FE，避免把 Operator 版本当成数据库版本 |
| internal/service/cluster/cluster.go | 将 starrocks 命名空间归入组件类别 |
| swag.json | 增补组件接口说明和相关定义，未修改后端 URL 或请求字段 |

组件状态列表复用已有的配置、Pod 状态与版本处理流程。Web 保存参数后，沿用 InstallComponentJob 调用 kk install component 的链路；实际 Helm 归档释放、同步、部署、PVC 与密码初始化在 KK 中实现。ComponentInfo / ClusterComponentInfo 当前没有专门的 StarRocks 访问 URL 字段，本次也未接入 StarRocks 数据备份、导入导出或网页访问链接功能。没有修改前端；本轮仅更新案例和索引，没有新增代码提交或发布。

## HELM-40 补充：替换用户图标与统一默认密码（2026-10-21）

用户提供 200×200 PNG 的 data URI，要求替换 StarRocks 图标，同时补充导入导出并保持默认密码与其他组件一致。本轮直接将提供的 PNG URI 写入 `internal/service/component/starrocks_icon.go`；验证 PNG 签名、尺寸及 URI 与附件一致，未重新生成或改变图片内容。前端没有修改。

原有 StarRocks 组件列表默认密码已经与 MariaDB/PostgreSQL 等组件一致。本轮将相同默认值集中为 `internal/common/cluster_types.go` 的 DefaultComponentPassword，组件目录使用该常量；新增 StarRocks 未传密码时补默认值，更新已有组件时保留其自定义密码。新增备份与 V2 导入同样优先使用组件配置、缺省时使用统一默认值，不修改已部署数据库密码。KK 仍从 Web 保存的组件配置接收密码，本轮无需修改 Chart 或 KK。

默认密码/自定义密码保留的临时 Go 验证通过，测试文件按要求删除；Web 实际 `cmd/server` 构建成功。新增数据流程与 214 上生成脚本的真实回环验证详见 [BK-33](../06_Web备份恢复与导入/BK-33.md)。本轮新增改动未提交或发布；原版组件安装提交已合并这一历史事实不代表新图标/数据功能已上线，也未执行 Web HTTP 入口的现场功能验证。

## HELM-40 补充：中央已合并KK与Web发布到121（2026-10-21）

用户明确要求“发布最新kk 和 web到121环境”。发布前按当前 AGENTS.md 核对中央远端分支：KK `test` 为 `9a73986d8382ce2830273c2c01ba7f404598b5fc`，Web `release` 为 `132955179ae4e494f984e4b615d7b293d9d4ee44`，均已包含初版 StarRocks 组件合并提交。最新图标、统一默认密码及数据导入导出补充仍为本地未提交工作区，未进入中央分支；在操作前已明确说明本次仅发布中央已合并版本，没有自动提交、推送或合并这些工作区改动。

固定使用 `ssh codex-test-121`，实际执行与结果：

| 项目 | 操作 | 直接结果 |
|---|---|---|
| KK源码 | `/root/wfkk/g_kube_installer` 切换 test，`git pull --ff-only origin test`，确认 HEAD 等于 origin/test | 从 9094b52 快进至 9a73986，命令成功 |
| KK程序 | 登录 Shell 执行 `make kk`，成功后 `cp -f bin/kk /g_web_installer/kk` | 构建与复制均退出 0；版本脚本输出 GIT_MAJOR unbound variable 警告，但 make 和最终复制仍成功 |
| Web源码 | `/root/wfweb/g_web_installer` 从 test 切回 release，`git pull --ff-only origin release`，确认 HEAD 等于 origin/release | release 从 00a0d61 快进至 1329551，命令成功 |
| Web本地状态 | 保留 `data`、`configs/users.json`；在最新 router.go 上重新应用移除 Vue import 与 vue.ServeVue 的两行后端调整 | users.json 内容保持不变；未覆盖运行数据 |
| Web程序 | `CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o server.next ./cmd/server`，成功后 `mv -f server.next server` | 构建与替换退出 0 |
| Web启动 | 两个程序准备完毕后，单次 ss 查询精确定位 8080 的 PID 776462，核对 cwd/exe 属于目标 Web 目录；kill -9 后立即执行 `/root/wfweb/web_start.sh` | 启动命令退出 0，直接输出 `server started, pid=2110256` |

本轮未要求同步 manifest，因此只覆盖 `/g_web_installer/kk`，没有额外覆盖 `/root/wfkk/manifest/kk`。本地无关 Pinpoint 包和 Swagger 工作稿保留。发布阶段遵循当前简化流程，没有重复测试、版本/哈希检查、接口探测、日志匹配、多轮进程/端口验证或自动回退。

结论边界：这些证据说明中央版本的拉取、构建、KK 复制、Web 替换及启动命令成功；未验证启动后的 HTTP 请求、StarRocks Web/KK 安装链或业务数据功能。本轮也未安装或升级 121/214 的 StarRocks 集群。新图标、默认密码补充及 BK-33 的 V2 数据流程仍未提交/发布，不能把本次 installer 发布当成这些工作区功能已上线。

## HELM-40 补充：121组件安装接口认证尚未通过（2026-10-21）

用户要求在发布后通过接口验证 StarRocks 组件安装。本轮确认 121 Web 源码为 release/1329551，KK 源码为 test/9a73986；Web 的唯一集群配置 `k8s_test` 指向 214/215。已按固定 SSH alias 查询当前配置与 Kubernetes 对象，没有修改集群配置、卸载/升级已有组件或重新发布程序。

实际请求 `GET /api/v1/components` 与 `POST /api/v1/components` 均返回 HTTP 401、code=10004，消息为 `authorization header or Cookie GWebInstallerToken can't be empty`。安装请求被认证中间件拦截，尚未创建安装任务或 PID，不能把它描述为组件安装逻辑失败或通过。首次检查时会话未提供 Web 登录凭据，也未发现预先配置的客户端认证机制，随后已请求并收到测试登录凭据；后续真实登录结果见下文。未读取 JWT 签名密钥、伪造 Token、修改账号或检索历史密码。

当前只读证据：214 的 release/starrocks 为 revision 2 deployed、Chart kube-starrocks-1.11.4；Operator、FE、BE 各 1/1 Ready，5 个 PVC Bound。KK 的 `StarRocksRun{Not:true}` 会在 release 已 deployed 时跳过 SyncStarRocksChart 和 DeployStarRocks，因此现有目标的接口重跑首先属于重复安装/跳过路径，不足以证明首次安装链路。没有为制造首次安装场景而删除已有 release 或数据。

另确认 Web 的 `k8s_test` 配置存在名为 `ssdf`、未填写 address 的节点，并被引用为 control-plane/nfs；这是当前配置事实，但尚未执行已认证任务，不能据此断言它已造成安装失败。后续应结合真实任务日志判断，不自动删除用户节点配置。当前 Web 配置尚未包含 starrocks 组件。

用户随后提供测试登录凭据，本轮通过 121 本机 `POST /api/login` 实际登录，返回 HTTP 500、消息 `Failed to authorize.`，没有取得 Token。当前 AuthHandler 中该消息来自账号存在但密码 MD5 比较未通过的分支；未读取实际账号密码或 JWT 签名密钥，也未猜测其他密码。已请求用户确认密码或提供有效 JWT，尚未发起已认证的组件安装请求，因此没有安装 PID、任务日志/WebSocket 或本轮 SQL 功能结果。

另已确认现有 Web 配置勾选 MariaDB、RabbitMQ、Nacos、Seata 等组件，而当前 Helm 列表只有 Neo4j、StarRocks 与基础组件。组件安装接口会合并并遍历完整组件列表，直接使用原配置可能触发其他组件安装；已准备使用仅包含 StarRocks、指向相同 214/215 的独立测试配置，原配置保持不变。该测试配置的创建安排在认证成功之后，本轮登录失败时尚未创建，未改变现有组件或数据。

待完成：真实登录或使用用户提供的有效 JWT，提交组件安装请求并记录 PID；通过任务日志/WebSocket 跟踪终态；区分首次安装与已安装跳过，再按执行结果核对组件状态、密码及 SQL 功能。此前手动 Helm 与 SQL 证据保留，不能替代本轮 API 验证。

## HELM-40 来源定位

- g_web_installer/internal/service/component/component_list.go、component.go、component_order.go、component_version.go、starrocks_icon.go。
- g_web_installer/internal/service/cluster/cluster.go；根目录 swag.json。
- g_kube_installer/cmd/kk/pkg/common/common.go；cmd/kk/pkg/component/module.go、tasks.go（StarRocks 实现已由原 starrocks.go 迁入）。
- g_kube_installer/cmd/kk/pkg/component/starrocks.tgz 与 kube-starrocks/ 下的父/子 values、CRD、starrockscluster.yaml、init-pwd 模板。
- g_kube_installer/cmd/kk/manifest-sample.yaml、manifest-sample-new.yaml、manifest-v1.32.8.yaml。
- 121 上本轮 docker pull/tag/push 的退出状态和输出摘要，以及本地 Go、Helm、schema、归档检查结果；不保存原始日志或凭据。
- 214 的 Helm history、Pod/PVC/StarRocksCluster 状态、认证及 SQL 返回；`/root/starrocks-validation-20261021-rcfdlp/` 下的 compatibility-84-report.json、client80/compatibility-80-report.json、stream-load-result.json 与合成数据规范输出；不归档凭据文件或完整日志。
- [官方 kube-starrocks 1.11.4 Chart](https://github.com/StarRocks/starrocks-kubernetes-operator/tree/v1.11.4/helm-charts/charts/kube-starrocks)：基础版本、子 Chart、配置与 CRD 来源。
- [Operator v1.11.4 PVCList](https://github.com/StarRocks/starrocks-kubernetes-operator/blob/v1.11.4/pkg/k8sutils/templates/statefulset/spec.go)：StorageClassName 传递及实际 PVC 构造检查；[官方持久化说明](https://github.com/StarRocks/starrocks-kubernetes-operator/blob/v1.11.4/doc/mount_persistent_volume_howto.md)。
- 上述两个 Gitea PR 的 merged 状态、PR 文件列表、远端 refs，以及本次隔离工作树构建退出状态和 Git tree 对比结果。
- 本轮实际 starrocks.tgz 的父/子 values、模板成员与 214 同哈希归档渲染；214 services/ingresses API 查询和 FE HTTP 401 响应；Web 提交 373f3cb 的 7 文件变更、ComponentInfo 定义和 InstallComponentJob 现有调用链。

[返回案例索引](../README.md)
