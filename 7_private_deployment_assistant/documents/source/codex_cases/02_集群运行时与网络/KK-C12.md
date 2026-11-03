# KK-C12：KK与Web的GPU节点隔离及模型服务调度设计

项目：g_kube_installer / g_web_installer。记录日期：2026-10-28。更新日期：2026-10-29。记录状态：方案设计（未实现；配置支持范围已复核）。

适用环境：本地 KK `test` / `9a73986`、Web `release` / `39f55cd` 的源码分析；Kubernetes 节点与服务安装调度。官方语义参考 Kubernetes v1.32 文档，不代表已验证当前项目全部支持版本。首期可按 Linux/NVIDIA 设计，其他厂商、GPU 共享、MIG 等资源模型另行适配。在线和离线均属拟支持范围，尚未实现、发布或进行集群功能验证。

## KK-C12 问题与表现

用户提出：KK 和 Web 检测主机有 GPU 后给节点添加 GPU 污点，服务安装时普通服务与模型服务采用不同调度策略。

用户随后明确实际需求：同一个集群有 1～2 台 GPU 机器专门部署 AI 服务，其余均为普通节点。普通业务不进入 GPU 专用节点，AI 服务固定进入专用节点。当前按这一混合集群需求收敛设计，不增加单机、全 GPU 集群或专用/混用切换功能。当前为方案讨论，没有现场故障或关键运行报错。

## KK-C12 最终根因或已确认边界

本条记录能力设计，不作故障根因结论。

GPU 专用节点是 Kubernetes 官方列出的典型污点用途。[v1.32 的 Example Use Cases](https://v1-32.docs.kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/#example-use-cases) 分别说明 Dedicated Nodes（专用节点）与 Nodes with Special Hardware（特殊硬件节点），后者明确以 GPU 为例。因此，本轮“1～2 台 GPU 节点专门部署 AI，其余节点承载普通业务”是在使用污点的标准调度语义：taint 表达节点拒绝哪些 Pod，toleration 允许通过对应拒绝规则；标签与 `nodeSelector`/required 节点亲和性表达 AI 固定选址，GPU `limits` 表达实际设备分配。污点本身不识别 AI 业务，AI 分类由安装包清单及 Web 配置契约表达。

此处污点表达节点的资源预留策略，健康的 GPU 节点也可使用；官方同时还有节点状态污点等用途。本项目新增的是 GPU 检测与这套调度策略的自动配置，仍沿用 Kubernetes 既有机制。

1. GPU 节点配置 `NoSchedule` 污点，可以阻止没有匹配容忍的新 Pod 由正常调度流程放入该节点；已有 Pod 不会因此被驱逐。它不按服务名称区分模型与普通服务，已有空 key、`operator: Exists` 等宽泛容忍的普通 Pod 仍可能被放行，需审查已有 Chart/YAML。必要时普通业务可使用 required nodeAffinity 排除专用 GPU 标签，与既有约束正确合并；首期不因这一需求增加重型准入组件，全平台强制策略以后另行设计。
2. `tolerations` 只允许 Pod 通过对应污点检查，不会强制 Pod 去 GPU 节点，也不会分配 GPU。本次 AI 服务固定进入专用节点，因此同时设置专用节点标签与 `nodeSelector` 或 required 节点亲和性；实际使用 GPU 的容器还须申请 GPU 扩展资源，例如 `nvidia.com/gpu`。GPU 资源申请本身即可排除不提供足够资源的普通节点，但不能代替本轮 AI 专用节点的业务分类与配置契约。
3. AI 专用节点的选址与 GPU 设备分配分开表达。明确归为 AI 的工作负载设置选址及容忍；其中实际使用 GPU 的容器才申请 GPU。AI 的 CPU 辅助服务按显式业务分类决定部署位置，不自动当作普通业务，也不因为同属一个安装包就把数据库、缓存、网关等全部放入 GPU 节点。
4. 主机发现 GPU 硬件、驱动可用、Kubernetes Node 注册了可分配 GPU 资源，是三个不同状态。`nvidia-smi` 失败可能是命令或驱动缺失，不能直接判定机器没有 GPU；仅凭“显示控制器”也会误识别 BMC 显示卡等非目标设备。Node 的 `allocatable` 表示总可分配量，不能把 `allocatable > 0` 当成当前还有空闲 GPU；容量预检查还须结合已有 GPU 资源申请及实际共享模型。
5. 当前已明确 GPU 节点专用、其余节点承载普通业务。普通节点容量不足时普通业务保持 Pending 并报告原因；AI 节点不可用或容量不足时 AI 服务保持 Pending，不回退普通节点。本轮不增加混用模式，不静默取消污点。
6. GPU 驱动、容器运行时 GPU 支持、设备插件及其镜像/离线依赖，是让容器真正获得 GPU 的前提；检测硬件、打标签或添加容忍不代表这条链已完成。

## KK-C12 当前源码证据

| 层次 | 已确认行为 | 对新增功能的含义 |
|---|---|---|
| KK 主机模型 | `cluster_types.go:58-73` 的 `HostCfg` 提供 `Labels`，未提供节点 `Taints` 字段 | 要设计 GPU 状态与污点策略的配置表达及传递，不可宣称现有配置已支持 |
| KK 创建与扩容 | `create_cluster.go:67,87-105` 与 `add_nodes.go:53,71-76` 均包含 `ConfigureKubernetesModule` | 创建、添加节点和重复执行均须覆盖，不能只补首次创建 |
| KK 节点配置 | `kubernetes/module.go:711-730` 在首个 master 侧执行配置；`tasks.go:1220-1233` 当前遍历节点 labels | 现有节点标签应用可作接入线索，未发现这段包含 GPU 污点逻辑 |
| KK NFD | `plugins/modules.go:32-33` 有可选 NFD 模块 | NFD 的存在不证明 GPU 驱动、设备插件、GPU 资源申请和隔离策略已闭环 |
| Web 主机信息 | `ssh_service/service.go:116` 的主机信息路径未提供 GPU 信息 | 展示和预检查需增加明确的硬件/驱动/资源状态，不能仅使用一个模糊布尔值 |
| Web 集群操作 | `cluster/cluster.go:453`、`offline/offline.go:128` 调用 `create cluster`；`cluster/node.go:58` 调用 `add nodes` | Web 负责策略输入、提示和透传，KK 承担主机/节点侧执行 |
| Web 应用安装 | `app/app.go:56` 进入 `app/appV2.go`；该文件 `:12,94` 处理解压后将 `deploy.yaml` 原样 `kubectl apply` | 不会自动为所有模型服务注入 GPU 调度规则，需要给实际 GPU 工作负载定义配置与清单契约 |
| Web 组件安装 | `component/component.go:17` 调用 `kk install component` | 与应用 `deploy.yaml` 链路不同，需要分别核对组件 Chart 的实际调度值 |

### 2026-10-29：当前配置支持范围复核

本轮在 KK `test` / `9a73986` 复核配置入口，结论须区分原生逐主机配置与其他间接途径：

- 原生 `hosts[].taints` 不支持。`HostCfg` 只有 `Labels`、没有 `Taints`，`ConfigureKubernetes` 也只应用 labels；`docs/roadmap.md:13-14` 的 labels 已勾选、taints 尚未勾选。`common/loader.go:210-215` 使用普通 `json.Unmarshal`，未知的 `hosts[].taints` 会被忽略，写入该字段不会使污点生效。
- 标准 kubeadm 安装链路中，全局 `kubernetes.kubeletArgs` 可以传入 `--register-with-taints=dedicated=ai:NoSchedule`。`kubernetes_types.go:47` 的 `KubeletArgs` 经 `kubernetes/tasks.go:235-244` 写入 `templates/kubelet_env.go:35-37` 的 `KUBELET_EXTRA_ARGS`；`InstallKubeBinariesModule` 的 `module.go:114-121` 将这项任务用于尚未入群的 `common.K8s` 主机。这是所有目标主机共用的集群级值，作用于节点注册阶段，不能按本轮需求仅选择 1～2 台 GPU 机器，也不是修改已有 Node 污点的机制；不将该参数格式泛化到 K3s 等其他安装类型。
- `system.postInstall` 自定义脚本可以间接执行 `kubectl taint nodes <GPU节点名> dedicated=ai:NoSchedule --overwrite`，该阶段同时出现在 create 与 add-nodes 链路；`system.postClusterInstall` 仅在 create 链路，不能单独覆盖扩容。`cluster_types.go:108-109` 定义脚本字段；`bootstrap/customscripts/module.go:38-57` 的 role 选择执行脚本的机器，`tasks.go:99-103` 通过 `SudoCmd` 执行。在有 kubeconfig 与相应 Kubernetes 权限的 master 上调用时，命令中的节点名决定加污点对象；role 并不自动表示“GPU 节点选择器”。后置打污点存在调度窗口，且 `NoSchedule` 不驱逐存量 Pod。

首 master 的 `GenerateNewKubeadmConfig` 在 `kubernetes/tasks.go:329` 注释了 `KubeletConfiguration` 传入项，Join 模板 `templates/kubeadm_config.go:162-191` 也不渲染对应配置文档，因此不能凭 RawExtension 等配置类型承诺 `kubeletConfiguration.registerWithTaints` 生效或已有完整逐节点污点支持。综上，现有入口具有全局注册参数和自定义脚本能力，GPU 检测与原生逐主机污点配置仍需新增。以上是只读源码及官方注册语义复核，未执行上述示例命令，也未验证实际注册或调度。

## KK-C12 处理方案

以下均为建议，尚未实现或发布。

### 节点与工作负载职责

KK 在集群创建、扩容前识别目标 GPU 硬件并记录状态，按本轮专用策略对对应节点维护标签和本功能拥有的污点。建议标签 `workload=ai`、污点 `dedicated=ai:NoSchedule`，将节点用途与具体 GPU 厂商分开。应让污点在节点注册时即生效，避免先加入普通可调度节点、稍后才加污点的窗口；具体 kubeadm/kubelet 配置入口在实现时核对支持版本。不能仅在集群尾部补打一遍污点。

只增量维护本功能对应的标签/污点，不清空其他污点，不覆盖控制平面、维护或第三方策略。创建、添加节点与重跑应幂等；硬件识别失败应报告明确状态，不凭一次失败移除既有 GPU 策略。对存量节点启用 `NoSchedule` 不驱逐现有普通 Pod，迁移和重建应另行安排，避免将其替换成会驱逐 Pod 的 `NoExecute` 来追求自动清空。

Web 展示 GPU 硬件、驱动以及集群资源状态，支持 AI/普通业务的明确分类与容量提示。AI 工作负载的最终 PodSpec 应具有精准容忍和专用节点选址；其中实际使用 GPU 的容器还需 GPU 扩展资源申请。首期可由应用包的 `deploy.yaml` 声明、Web 在安装前校验；是否进一步统一注入尚未决定，不应把分类字段写成已实现的 API。普通业务还须校验既有宽泛容忍，避免绕过专用节点隔离，基础节点组件按明确例外处理。组件安装经另一条 KK/Helm 链路，应核对最终 Chart 模板与 values，不能假设应用清单处理自动覆盖全部安装入口。

### NVIDIA 独占整卡示例

节点策略示例：1～2 台 GPU 节点添加标签 `workload=ai` 和污点 `dedicated=ai:NoSchedule`，普通节点不添加这条污点。以下是使用 NVIDIA GPU 的 AI 应用 PodSpec 节选，适用于普通独占整卡申请，不替代现有 GPU 共享或 MIG 资源方案，也不是已实现的 Web 输入格式。

```yaml
spec:
  nodeSelector:
    workload: ai
  tolerations:
    - key: dedicated
      operator: Equal
      value: ai
      effect: NoSchedule
  containers:
    - name: inference
      image: example.invalid/inference:version
      resources:
        limits:
          nvidia.com/gpu: 1
```

本次 AI 服务保留示例中的 `nodeSelector`，确保固定进入 AI 专用节点，多个符合条件的节点由调度器按资源等约束选择，不写死节点名称。明确放入专用节点的 CPU 辅助服务保留选址和容忍，省略 GPU 设备申请。普通业务不增加这条容忍；GPU Pod 申请后若驱动、设备插件或 GPU 资源不足，应明确等待或失败，不能静默退到普通节点冒充 GPU 部署成功。

### 基础组件与部署条件

GPU 节点仍需要 CNI、存储、监控和 GPU 设备插件等必要节点组件。按各组件职责给其配置必要容忍，不能机械地阻断所有非模型 Pod。NVIDIA 链路需准备驱动、Container Toolkit 与对应容器运行时配置、device plugin，再确认资源注册；离线环境同时补齐匹配的驱动包、运行时依赖、插件及其他必需镜像，不能只修改业务 YAML。

本轮混合集群在安装前检查普通节点与 GPU 专用节点各自容量。普通节点不足时提示增加普通节点或调整普通业务资源，GPU 专用节点不足时提示调整 GPU/CPU/内存申请或增加专用节点，不自动绕过隔离。单机、全 GPU 集群及节点混用不属于当前需求。

### 实施及验收顺序

1. 按已明确的“1～2 台 GPU 节点专用部署 AI，其余节点部署普通业务”实现；进一步核对 GPU 厂商、哪些工作负载归为 AI，以及已有 GPU 共享或 MIG 设备分配模型。
2. 明确主机硬件检测、驱动检测与 Node GPU 资源检查的结构化状态、失败输出和离线依赖。
3. 在 KK 创建、扩容和重跑入口实现节点注册时的策略及受管字段幂等合并。
4. 为 Web 应用 YAML 与 KK/Helm 组件两条安装链路分别建立逐工作负载 AI 分类、专用节点选址及 GPU 设备需求配置，不对整包无差别加容忍。
5. 验证 1 台及 2 台 GPU 专用节点混合集群中的普通服务、GPU 推理、明确分类的 CPU 辅助服务、必要基础组件、驱动缺失、扩容及重跑、两类节点各自容量不足等场景；检查已有宽泛容忍是否影响隔离预期。
6. 对存量节点单独验证 `NoSchedule` 不驱逐现有 Pod，再按授权迁移业务；以实际 GPU 可见性、资源分配与业务推理验证完成闭环。

## KK-C12 验证证据与限制

首次评估已核对当前源码；本次需求澄清后复核 Kubernetes v1.32 官方资料，并将方案收敛为 GPU 专用节点混合集群。未修改 KK/Web 业务代码、未新增或执行测试、未构建、未连接服务器，未实测污点、调度、GPU 容器或推理功能，也未提交、发布或重启服务。仅维护本地案例与索引，保留既有工作区改动。

2026-10-29 追加当前配置支持范围的源码复核，区分未知字段被忽略、全局 kubelet 注册参数与自定义脚本；未进行测试、构建、服务器连接或外部操作。元数据仍为 `unverified`。

“方案合理”仅指污点隔离、GPU 资源申请及逐工作负载配置的设计关系成立，不代表目前项目具备完整能力。硬件识别方法、节点注册参数的版本兼容、现有安装包/Chart 的实际字段、GPU 可用性与端到端安装仍待实现及现场验证，元数据保持 `unverified`。

## KK-C12 来源定位

- `g_kube_installer/cmd/kk/apis/g_kube_installer/v1alpha2/cluster_types.go:58-73`：主机 Labels 字段。
- `g_kube_installer/cmd/kk/pkg/pipelines/create_cluster.go:67,87-105`、`add_nodes.go:53,71-76`：创建及扩容配置模块。
- `g_kube_installer/cmd/kk/pkg/kubernetes/module.go:711-730`、`tasks.go:1220-1233`：首 master 配置与节点 Labels 应用。
- `g_kube_installer/cmd/kk/pkg/plugins/modules.go:32-33`：可选 NFD。
- `g_kube_installer/docs/roadmap.md:13-14`、`cmd/kk/pkg/common/loader.go:210-215`：原生逐主机污点进度与普通 JSON 反序列化。
- `g_kube_installer/cmd/kk/apis/g_kube_installer/v1alpha2/kubernetes_types.go:47`、`cmd/kk/pkg/kubernetes/tasks.go:235-244`、`templates/kubelet_env.go:35-37`、`module.go:114-121`：全局 kubelet 参数传递与未入群主机执行范围；`tasks.go:329`：首 master 配置传入项边界。
- `g_kube_installer/cmd/kk/apis/g_kube_installer/v1alpha2/cluster_types.go:108-109`、`cmd/kk/pkg/bootstrap/customscripts/module.go:38-57`、`tasks.go:99-103`：后置脚本字段、执行主机与 SudoCmd。
- `g_web_installer/internal/service/ssh_service/service.go:116`：主机信息；`cluster/cluster.go:453`、`offline/offline.go:128`、`cluster/node.go:58`：KK 调用入口。
- `g_web_installer/internal/service/app/app.go:56`、`app/appV2.go:12,94`：应用包清单 apply；`component/component.go:17`：独立 KK 组件安装链路。
- [Kubernetes v1.32 污点与容忍](https://v1-32.docs.kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)：`NoSchedule` 与容忍语义；[Example Use Cases](https://v1-32.docs.kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/#example-use-cases) 明确列举专用节点与 GPU 等特殊硬件节点。
- [Kubernetes v1.32 GPU 调度](https://v1-32.docs.kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)：设备插件、扩展资源申请与 GPU 标签选择。
- [NVIDIA Kubernetes device plugin](https://github.com/NVIDIA/k8s-device-plugin)：驱动、Container Toolkit、容器运行时配置与设备插件前提。
- [Kubernetes v1.32 节点自注册](https://v1-32.docs.kubernetes.io/docs/concepts/architecture/nodes/#self-registration-of-nodes)、[kubelet 参数参考](https://v1-32.docs.kubernetes.io/docs/reference/command-line-tools-reference/kubelet/)：`--register-with-taints` 的注册阶段语义。

[返回案例索引](../README.md)
