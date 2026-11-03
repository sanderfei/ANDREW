# HELM-45：pgvector 已完成 Job 检查的 JSONPath 引号丢失导致组件安装失败

项目：g_web_installer、g_kube_installer。记录日期：2026-11-03。记录状态：用户日志及本地源码分析；KK 源码已修复并通过隔离测试，现场交付与验证待完成。

适用环境：组件安装流水线 `InstallComponentsPipeline` / `DeployComponentModule`，执行节点为 Kubernetes master。日志未确认现场 Web、KK、Kubernetes、OS 版本及部署方式；本地源码不能作为现场二进制版本证明。

## 问题表现与证据

Elasticsearch Helm 输出 `STATUS: deployed`；随后进入 `Synchronize pgvector chart and values` 时，检查 Job 的 kubectl 命令报 `unrecognized identifier Complete`，重试后流水线失败。Helm deployed 仅是 release 状态，不能证明 Elasticsearch 工作负载已就绪或业务可用。

报错输出的实际 JSONPath 模板为 `{.status.conditions[?(@.type==Complete)].status}`：`Complete` 已无字符串引号。错误同时打印的 Job 显示历史 `Complete=True`、`succeeded=1`，完成时间为 10 月 30 日。它证明该 Job 当时完成，不证明本次检查通过，也不能证明当前目标数据库中的扩展版本和功能。

## 原因与源码边界

修复前，本地 KK `cmd/kk/pkg/component/prepares.go` 的 `PgvectorRun.PreCheck` 构造的 JSONPath 含 `"Complete"`；`cmd/kk/pkg/core/connector/ssh.go` 的 `SudoPrefix` 又以双引号包裹整个 `/bin/bash -c` 参数。内层双引号被外层 shell 消耗，kubectl 收到无引号的 `Complete`，导致 JSONPath 解析失败，而不是根据 Job 状态正常返回。`cmd/kk/pkg/component/module.go` 在同步任务及部署任务均使用该检查；同步任务在 prepare 阶段报错后失败。

这解释了日志直接原因，现场 KK 的版本和二进制与本地源码的对应关系尚未核实。不能根据这份日志认定 pgvector 本次被重新安装或 PostgreSQL 当前状态正常。

## 处理与验证步骤

1. 在实际集群控制节点只读检查现有 Job：

   ```bash
   kubectl get job -n pgvector pgvector -o 'jsonpath={.status.conditions[?(@.type=="Complete")].status}'
   ```

   输出 `True` 表示该 Job 完成；再结合 PostgreSQL 目标库只读检查扩展版本和 schema，不能把 Job 的历史完成状态直接等同当前数据库状态。
2. KK 源码已在 `PgvectorRun.PreCheck` 中为 JSONPath 字符串的双引号增加跨 shell 转义，保持 Job 不存在、未完成与完成时的判断语义。隔离测试通过真实 `PreCheck`、`SudoPrefix` 和两层 shell，模拟完成、未完成、失败、无条件及 NotFound 的 Job 状态。
3. 交付正确版本后按授权重试组件安装，检查最终任务日志，并分别验证 pgvector 扩展、Elasticsearch 工作负载及业务连接。不要为了绕过检查直接删除已有 Job 或数据库资源。

本轮使用 `CGO_ENABLED=0 go test -tags containers_image_openpgp ./cmd/kk/pkg/component -run '^TestTemporaryPgvectorShellAndJobState$' -count=1` 完成隔离测试，临时测试已删除；未连接集群，尚未构建发布或访问现场，实际功能和恢复未验证。

## 来源定位

- 用户提供的组件安装失败日志（仅记录脱敏后的关键状态与错误）。
- `g_kube_installer/cmd/kk/pkg/component/prepares.go:183`：pgvector Job 完成状态检查。
- `g_kube_installer/cmd/kk/pkg/component/module.go:418`：同步任务的预检查。
- `g_kube_installer/cmd/kk/pkg/core/connector/ssh.go:605`：sudo shell 命令包裹。

[返回案例索引](../README.md)
