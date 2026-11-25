# HELM-48：StarRocks 安装时 Helm 提示另一项操作进行中

记录日期：2026-11-11。环境：Web 触发 KK 组件安装，集群标识 `k8s-100`，release 和命名空间均为 `starrocks`；实际 Kubernetes、Helm、StarRocks 版本和机器未核实。状态：安装失败原因中的操作冲突已见日志，现场状态与恢复待验证。

## 问题表现

用户截图显示 KK 在目标主机执行 `helm upgrade --install starrocks`，使用 `--wait --wait-for-jobs --timeout 15m`，返回：

```text
Error: UPGRADE FAILED: another operation (install/upgrade/rollback) is in progress
```

KK 重试后仍报相同错误，`InstallComponentsPipeline` 的 `DeployStarRocks` 失败，组件安装任务以状态码 1 结束。

## 已确认边界和证据

报错说明 Helm 拒绝对同一 release 发起当前操作；可能存在其他真实运行中的 Helm 任务，也可能已有未结束的 pending 修订。截图不足以区分二者，也没有前一次操作及其失败原因，不应推断镜像、PVC 或数据损坏。相关旧 nginx 案例见 [HELM-01](HELM-01.md)，不同现场不能直接套用其修订号或处理结果。

当前本地 KK 源码 `cmd/kk/pkg/component/tasks.go` 中 `DeployStarRocks` 通过 `helm upgrade --install` 部署；截图可证明这次命令和失败结果，不能证明现场二进制与本机源码完全一致。

## 排查和处理

在对应集群的管理节点执行以下只读命令，确认连接目标正确：

```bash
helm status starrocks -n starrocks
helm history starrocks -n starrocks
kubectl get pods,pvc -n starrocks
kubectl get events -n starrocks --sort-by=.lastTimestamp
```

同时核对 Web/KK、人工终端或自动化系统是否仍有针对该 release 的安装、升级或回滚任务在运行；有正在运行的任务应等待其结束，避免并发重试。若最新修订停在 pending，且确认没有相关活动任务，先结合历史修订、部署资源与原任务日志判断处理路径；存在可用的历史成功修订时可评估回滚，但回滚会改变资源，须结合现有数据和状态执行。若是首次安装或无可用修订，不得假定能回滚。不要直接批量删除 Helm Secret、卸载 release 或删除 PVC。

## 验证结果与遗留事项

仅据用户截图分析；未连接客户集群，未核实状态、执行回滚、清理、重试或验证 StarRocks 业务。需要取得 history/status、其他任务及首次失败日志后再判断具体处理和验证路径。

[返回案例索引](../README.md)
