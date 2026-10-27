# KK-O16：KK基于Docker与Compose的Linux主机应用安装功能设计

项目：g_kube_installer。记录日期：2026-10-16。记录状态：方案设计（未实现）。

适用环境：本地 KK test 分支 HEAD `9094b52` 的源码分析；拟新增的 Linux 主机应用安装能力。Docker Engine / Compose 的具体支持版本、OS 与 CPU 架构矩阵尚待确定；功能不要求已有 Kubernetes 集群。在线、内网仓库、完全离线均属于设计目标，不代表已经可用。

## KK-O16 问题与表现

用户希望类似 `kk install component` 新增通用应用安装，使用现有镜像，通过 Docker 或 Docker Compose 在 Linux 主机部署，支持在线、离线仓库与多服务器。集成到 KK 的目的是复用 Pipeline、SSH、远程文件分发和多主机任务。本轮先讨论常见功能，不改业务代码。没有现场故障和运行报错。

## KK-O16 最终根因或已确认边界

本条是能力设计，非故障根因结论。

1. 当前 `install component` 入口调用 `common.NewKubeRuntime`，再执行 `InstallComponentsPipeline` 与 `DeployComponentModule`；组件选择包含按名称编排的数据库、中间件及 Helm 任务，不是现成的通用主机应用安装入口。
2. 可复用的底层接口为 `connector.Runtime`、`BaseRuntime`、`Pipeline`、`Module`、`RemoteTask`、SSH Runner 和 Scp。RemoteTask 已有目标主机、并行、重试、超时等字段；新增功能仍须设计应用依赖、批次、状态持久化和精确失败重跑，不能把它们描述为已有完整能力。
3. 当前 KubeRuntime 加载 ClusterSpec 并应用 Kubernetes 默认配置；建议新增应用配置与 Host/App Runtime，组合 BaseRuntime，避免普通主机安装要求 master/worker、kubeconfig、Helm 或 Kubernetes 网络配置。
4. 现有 Docker 安装属于 Kubernetes 容器运行时路径，涉及全局服务、配置和 CRI；仅选择可复用动作，不整段复用集群 OS 初始化或默认重写既有 Docker daemon 配置。
5. TaskModule 在任务失败时调用当前任务的 ExecuteRollback；不意味着会回滚此前全部成功任务，更不代表跨服务器、数据库及迁移可事务回滚。
6. Compose 项目部署在单个 Docker 主机上。KK 可在多机编排多个项目；跨机服务发现、负载均衡、主从、选举、复制和故障切换需要明确的应用模板及拓扑设计。批量部署相同容器不代表组成数据库集群。

## KK-O16 处理方案

以下都是建议功能，尚未实现或发布。

### 通用模型和输入

管理对象为应用实例：实例名、应用版本、包格式版本、目标主机/主机组、运行方式、镜像引用、配置与数据路径、健康检查及部署策略。区分包的默认值、环境参数和主机覆盖值，严格校验未知字段与缺失变量。支持同一应用在同主机部署多个实例。

应用定义应优先引用标准 `compose.yaml`；单容器支持简洁 Docker 声明。避免重新定义全部 Compose 配置，也不把“通用”实现为按 Redis/MySQL/Nginx 名称增加 switch 分支。保留原生配置入口并定义 KK 管理字段的覆盖次序。

### 功能清单

| 功能 | 建议范围 |
|---|---|
| 主机清单与选择 | SSH 地址、端口、用户、现有密钥机制、sudo、主机组；按应用/主机筛选；本机可作为一种执行目标 |
| 安装预检查 | SSH/sudo、OS/架构、Docker/Compose 支持版本、Daemon 可用、磁盘内存、端口和路径冲突、仓库连通性与配置完整性 |
| 运行时准备 | 优先复用已有 Docker/Compose；缺失时显式选择安装及版本；在线包源或离线依赖包；独立操作，不默认升级或重启承载其他应用的 Docker |
| 镜像准备 | 目标机已有镜像、控制机镜像导出分发、离线 tar 导入、在线/内网仓库拉取；解析完整镜像引用、平台与拉取策略 |
| 仓库支持 | 多仓库、认证、地址映射、CA/HTTPS、显式 HTTP 仓库；在实际执行 Docker 的身份下配置认证，日志脱敏；全局 daemon 变更须显式授权 |
| 配置与文件 | env/env_file、配置/证书/初始化文件分发、模板变量和逐主机覆盖、目录权限、相对路径基准、敏感文件权限、变更对比 |
| 容器运行参数 | command/entrypoint、端口、bind/named volume、网络、hostname/DNS、运行用户、资源限制、日志轮转、重启及优雅停止策略；特殊设备/GPU通过原生配置按需支持 |
| 依赖与初始化 | 同主机 Compose 依赖、跨应用依赖、跨主机健康屏障、外部服务依赖；首次初始化与每次部署脚本分开，明确执行范围、重试和重复执行规则 |
| 多主机执行 | 串行/并行、并发上限、按批次部署、失败停止或继续策略、按主机/应用汇总结果；跨应用依赖检查环路 |
| 健康与验收 | 容器状态、Docker HEALTHCHECK、TCP/HTTP/自定义协议检查、超时重试、一次性任务退出码；报告状态级别和真实服务端点 |
| 生命周期 | install/start/stop/restart/status/logs/uninstall；同配置重跑收敛；配置更新及镜像版本升级；只处理本实例受管资源 |
| 状态与恢复 | 实例归属标识、期望配置摘要、实际镜像标识、逐主机执行阶段、失败原因、互斥锁；失败重跑前重新检查真实状态 |
| 离线应用包 | 应用描述、Compose/容器定义、配置模板、脚本、镜像清单/归档、可选运行时依赖、版本/平台和校验信息；支持生成、校验、分发和导入 |
| 预览与结果输出 | 只读展示目标主机、实例、镜像来源、端口/目录及计划变更；人可读输出与结构化结果，便于后续其他调用方使用 |

### 镜像来源与联网策略分别设计

“本地已有镜像”必须说明是在运行 KK 的控制机，还是目标主机 Docker daemon。控制机镜像不能被其他主机自动看到，需导出分发或经仓库转发；已有 containerd 镜像也不能直接假定在 Docker 中可用。

- 已有镜像：按目标主机逐一检查；禁止拉取策略下缺失即明确失败。
- 离线镜像包：校验包后分发并 `docker load`，验证镜像引用及架构；不是容器根文件系统的 `docker import`。
- 仓库拉取：在线公私仓或内网隔离仓库，本质均为目标机 Docker 可访问的 Registry，目标地址与原镜像引用允许显式映射。
- 完全离线：镜像、Docker/Compose、OS 依赖、脚本及初始化材料全部可在本地/内网取得；禁止暗中回退公网下载、构建或远程拉取。离线来源可以是包，也可以是内网仓库；不要求为每次安装创建新仓库。

镜像拉取策略至少明确 always、if-missing、never 的产品语义，并映射/校验对应运行后端能力；支持固定 tag，条件满足时支持 digest。安装记录同时保留用户引用和实际部署镜像标识。

### 多主机和可靠性边界

- 同一应用部署至三台机器是三个实例，可并行执行；应用分角色拓扑则由模板声明，例如数据库在 db 主机、后端在 app 主机，后端启动前检查数据库协议就绪。
- Compose 网络和服务名称解析按单机项目处理，跨机使用明确的主机内网地址、DNS 和发布端口。需要 HA/VIP/复制时单独设计，不从副本数推断。
- 应用实例使用稳定的 Compose project name 或 Docker labels 标识归属，避免多个实例冲突及误接管已有容器。已经存在的非受管同名资源应报告冲突，接管必须单独指定。
- 同配置再次安装应跳过或收敛，不能每次无条件重建。新配置先校验，再执行；记录失败和部分完成结果，不把单台失败报告为整体成功。
- 非幂等初始化和迁移不套用普通命令的自动重试；中断后根据实际结果判断是否再次执行。数据库迁移和数据回滚需要应用明确支持。
- 卸载默认保留持久数据与共享资源；删除数据和清理镜像是独立显式选项，限定本实例归属。升级失败不承诺自动恢复数据库。
- 主机重启恢复以 Docker 服务自启与容器 restart 策略等明确配置实现；一次部署阶段的依赖检查不能被宣传为运行期持续编排。

### 建议分期

首期完成已有 Docker/Compose 环境下的安装闭环：应用包与实例定义、目标主机选择、预检查、三类镜像来源及联网策略、标准配置与卷/网络/资源参数、基础依赖与初始化、串并行执行、健康检查、幂等重跑、状态日志、启停重启和保留数据卸载。预览、资源归属、失败汇总与脱敏作为首期基础要求。

第二期补齐运行时自动离线安装、多 OS/架构包矩阵、应用包自动导出、升级计划与历史版本、分批升级、断点恢复和可选备份/恢复。首期运行时已安装的前提需明确，不能宣传为任意裸机全自动离线安装。

第三期再按实际应用扩展数据库主从/集群模板、VIP/负载均衡、应用特定数据迁移和复杂回滚。保留模板能力不等于现在承诺通用 HA。

### 预期流程与命令

建议流程：解析/校验应用与主机 → 预检查 → 准备运行时（按策略）→ 镜像准备 → 渲染分发配置 → 准备目录及初始化 → 启动 → 健康/功能检查 → 持久化逐实例结果。

可讨论的新命令示意为 `kk install app`、`kk status app`、`kk logs app`、`kk uninstall app`；最终命令树、YAML schema 及与现有 flags 的兼容方式待后续设计，当前命令并不存在。

## KK-O16 验证证据与限制

本轮核对当前源码和 Docker 官方文档，未修改 KK 业务代码、未新增测试、未构建、未连接服务器、未安装或重启服务。原有 pinpoint.tgz 工作区改动保留。以上清单是建议方案，无实现或功能验证，metadata 为 unverified。

后续实施验收至少覆盖：目标机已有镜像且不拉取、离线包分发导入、认证仓库拉取、完全断公网、双机成功与单机失败、端口冲突、重复安装及初始化不重复、主机重启后恢复、健康检查失败、卸载保留数据，以及不影响既有其他应用。升级/回滚另按应用的数据兼容性验收。

## KK-O16 来源定位

- `g_kube_installer/cmd/kk/cmd/install/install_component.go`：NewCmdInstallComponents / Run。
- `g_kube_installer/cmd/kk/pkg/pipelines/install_components.go:11`：InstallComponents / NewInstallComponentsPipeline。
- `g_kube_installer/cmd/kk/pkg/component/module.go:50`：DeployComponentModule.Init。
- `g_kube_installer/cmd/kk/pkg/common/kube_runtime.go:64`：NewKubeRuntime。
- `g_kube_installer/cmd/kk/pkg/core/connector/runtime.go:31`：BaseRuntime。
- `g_kube_installer/cmd/kk/pkg/core/connector/interface.go:62`：Runtime。
- `g_kube_installer/cmd/kk/pkg/core/connector/runner.go`：SudoCmd / Scp / SudoScp。
- `g_kube_installer/cmd/kk/pkg/core/task/remote_task.go:37`：RemoteTask。
- `g_kube_installer/cmd/kk/pkg/core/module/task_module.go:70`：当前任务失败时 ExecuteRollback。
- `g_kube_installer/cmd/kk/pkg/container/module.go:62` 与 `docker.go`：现有 Kubernetes Docker 安装路径。
- [Docker Compose 服务参数](https://docs.docker.com/reference/compose-file/services/)：原生容器与服务配置。
- [Compose 启动顺序](https://docs.docker.com/compose/how-tos/startup-order/)：启动不等于就绪，healthcheck 与依赖条件。
- [docker image load](https://docs.docker.com/reference/cli/docker/image/load/)：镜像归档加载与标签恢复。
- [Docker 容器重启策略](https://docs.docker.com/engine/containers/start-containers-automatically/)：重启和自启行为。

[返回案例索引](../README.md)
