# HELM-26：Pinpoint HBase后台进程退出、锁超时与启动探针修复

项目：g_kube_installer。记录日期：2026-10-15。记录状态：代码已验证，现场升级待验证。历史来源会话起始日期：2026-07-29；本次补充 2026-10-14 现场修复记录及 2026-10-15 Chart 实现，保留历史来源，不计入历史扫描新增案例。

适用环境：Pinpoint 2.5.1、镜像内 HBase 1.2.6，单个 StatefulSet Pod 内同时运行 HMaster、RegionServer，使用外部 ZooKeeper 和原有 PVC。本次本地 Chart 从 0.1.1 更新到 0.1.2，镜像及 appVersion 不变。Kubernetes、操作系统版本未取得现场证据，标 any；安装模式支持 KK 在线/离线嵌入 Chart，存量 release 需单独升级。

## HELM-26 问题与表现

Web 的 `/applications.pinpoint` 查询和 Collector 写入出现：

```text
org.apache.hadoop.hbase.exceptions.LockTimeoutException:
Failed to get user region lock in10000 ms. for accessing meta region server.
```

用户提供的现场记录显示：HBase Pod 只有 HMaster，在线 RegionServer 为 0，旧 RegionServer 的 16201 端口连接被拒绝；stderr 有 `Killed`，日志停在 2026-09-15。容器仍运行 `tail -f /dev/null`，旧现场模板没有健康探针，Pod 持续显示 Running/1/1。

## HELM-26 最终根因或已确认边界

1. 现场直接故障是 RegionServer 停止，缺少承载元数据和业务区域、执行 WAL 恢复的 RegionServer，导致客户端读写受阻并报锁超时。
2. 旧现场没有探针，容器主进程 tail 存活掩盖了内部 Java 进程死亡。当前仓库 0.1.1 包已经有三个 PID 探针，与旧现场存在配置差异，不能称当前代码“没有探针”。
3. 用户现场记录还确认：分布式启动脚本依赖 SSH，而镜像没有 SSH，容器重建存在启动 RegionServer 失败的隐患。此隐患与最初进程被杀的触发原因需要分别定位。
4. `Killed` 不足以确认 OOM；本轮未取得内核 OOM 日志、退出状态等证据。历史内存建议保留 HBASE_HEAPSIZE=1024、request=2Gi/limit=6Gi，不能据此断定本次故障由内存不足导致。
5. 仓库不包含镜像内三个初始化脚本的实现；本轮沿用用户已现场验证的直接启动、configure、check-table 顺序，未对实际镜像重新执行验证。

## HELM-26 处理方案

**已实现、未发布：**

- 将容器启动命令改为 `/bin/bash -ec`，清除旧初始化标记，分别执行 `${HBASE_HOME}/bin/hbase-daemon.sh --config "${HBASE_HOME}/conf" start master`、`start regionserver`，绕开 SSH 启动路径。
- 继续执行 `configure-hbase.sh` 和 `check-table.sh`，均成功后才写入 `/tmp/hbase-initialized`，随后执行 tail。前台启动步骤失败时不继续写成功标记；后台 Java 进程退出由探针发现。
- startup/readiness 同时要求初始化标记和 60000、60020 两个 RPC 端口可连接；liveness 检查两个端口。通过 `${HOSTNAME}` 访问 Pod IP，不依赖 localhost 或固定 PID 文件名。
- startup 每 10 秒检查，连续失败阈值 90，提供约 15 分钟启动窗口，覆盖初始化检查阶段；通过后才启用 readiness/liveness。readiness 每 10 秒检查、失败阈值 3；liveness 每 20 秒检查、失败阈值 3。
- 保留镜像、环境变量、资源限制、端口、挂载、PVC 和 ZooKeeper 配置；更新 Chart 版本并重新打包实际被 go:embed 使用的 `pinpoint.tgz`，刷新相邻解压目录。

**发布步骤，尚未执行：**

在具备目标集群权限的环境中指定原生产 values；保留数据卷及环境差异。以下命令从 KK 仓库根目录执行：

```bash
# PINPOINT_VALUES 指向原环境 values 文件，先在环境中设置该变量。
test -f "$PINPOINT_VALUES"
helm template pinpoint cmd/kk/pkg/component/pinpoint.tgz \
  -n pinpoint -f "$PINPOINT_VALUES" > /tmp/pinpoint-rendered.yaml
# 审核渲染结果后执行升级；20 分钟为启动、调度和挂载留出余量。
helm upgrade pinpoint cmd/kk/pkg/component/pinpoint.tgz \
  -n pinpoint -f "$PINPOINT_VALUES" --wait --timeout 20m
kubectl rollout status statefulset/pinpoint-hbase -n pinpoint --timeout=20m
kubectl exec -n pinpoint pinpoint-hbase-0 -c hbase -- jps -l
```

`jps` 应同时有 HMaster 和 HRegionServer。随后检查在线 RegionServer、WAL 恢复和应用列表接口，存在采集流量时确认写入计数增长。端口探针不能证明全部区域、表读写或 Pinpoint 业务已恢复。

只有 HBase 健康后 Collector 仍持续报旧连接异常时，才执行：

```bash
kubectl rollout restart deployment/pinpoint-collector -n pinpoint
kubectl rollout status deployment/pinpoint-collector -n pinpoint --timeout=5m
```

KK 的 PinpointRun 通过 `pinpoint-web` Service 判断组件是否已安装，已存在时跳过同步和安装任务；仅更新 KK 二进制不会升级已有 release。本轮没有修改该安装门禁，也没有执行升级或重启。

## HELM-26 验证证据与限制

历史证据为包内断言和归档一致性通过，未做真实 OOM 恢复验证。

用户提供的 2026-10-14 现场修复记录包含：手动启动 RegionServer 后 WAL 开始恢复，应用列表返回 HTTP 200；直接启动与探针补丁重建后两个进程正常；重启仍异常的 Collector 后，RegionServer 写入计数在 15 秒内从 32004 增至 32895。以上为用户提供的功能证据，本轮未连接现场复验，不能视为当前 Chart 0.1.2 已发布验证。

2026-10-15 本地验证结果：

- Helm 3.16.4 对最终 `pinpoint.tgz` 执行 lint，通过，仅提示推荐添加 Chart icon；默认值及自定义 registry、PVC 容量、StorageClass 场景渲染通过。与旧包渲染对比，除 Chart 版本标签外，仅 HBase 容器 command、args、三个探针发生变化。
- 从最终渲染提取的启动和探针脚本通过 `bash -n`。使用临时替身脚本验证 Master、RegionServer、configure、check-table 的执行顺序及四个步骤各自失败时立即停止、不写初始化标记；旧标记会先清除。
- 使用本地 TCP 监听验证两个端口同时可连接时探针通过，任一端口关闭时三个探针均失败；缺少初始化标记时 startup/readiness 失败，liveness 仍按端口判断。此为本地行为验证，不是真实 HBase 镜像或 Kubernetes 故障注入。
- `CGO_ENABLED=0 go test -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./cmd/kk/pkg/component` 退出 0，包没有已有测试文件，该结果是组件包编译检查。
- `make kk` 退出 0，生成 `bin/kk`；`hack/version.sh` 仍有 `GIT_MAJOR: unbound variable` 提示，本轮未修改该脚本，构建命令实际使用空 ldflags。此构建不能证明业务恢复。
- 最终包与相邻 `pinpoint/` 解压目录逐文件内容一致，归档仅修改 Chart.yaml、README.md、templates/hbase.yaml。归档 SHA-256：`0ebdbf85cb14403270837a00856f2ddaffcb8f1c92b55af3daacc33d10763858`。
- 本轮未在仓库新增测试文件，临时行为验证目录已自动清理；Git 差异检查通过。

新归档尚未进行真实镜像启动、集群滚动重建和业务写入验证，metadata 继续使用 unverified。未执行 commit、push、merge、部署、重启或向量库录入。

遗留事项：定位进程最初被杀的触发原因；在授权发布后验证新 Chart。Collector 的独立 FlinkTcpDataSender 告警不属于本修复范围。

## HELM-26 来源定位

- Codex 会话 `019fabf4-d087-7020-ba90-77a51c8c3b7b`；始于 2026-07-29。可按本条标题及关键错误定位相关提问与后续结论。
- 用户提供的 2026-10-14《Pinpoint HBase 锁超时修复：开发修改指南》和现场修复摘要；仅保留脱敏结论，不复制原始会话、完整客户配置、地址或日志。
- `g_kube_installer/cmd/kk/pkg/component/tasks.go`：go:embed、ReleasePinpointChart、SyncPinpointChart、DeployPinpoint。
- `g_kube_installer/cmd/kk/pkg/component/module.go`：deployPinpoint；`prepares.go`：PinpointRun。
- `g_kube_installer/cmd/kk/pkg/component/pinpoint.tgz` 及相邻 `pinpoint/templates/hbase.yaml`、`hbase-configmap.yaml`、`Chart.yaml`、`README.md`。
- [HBase 1.2 WAL 恢复说明](https://hbase.apache.org/1.2/book.html#distributed.log.splitting)、[HBase 1.2.6 启动脚本](https://github.com/apache/hbase/blob/rel/1.2.6/bin/start-hbase.sh)、[Kubernetes 探针说明](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)。

[返回案例索引](../README.md)
