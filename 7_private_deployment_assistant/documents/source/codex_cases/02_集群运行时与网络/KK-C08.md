# KK-C08：scheduler和controller-manager因续租超时重启

项目：g_kube_installer。记录状态：待验证。来源会话起始日期：2026-04-15（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes 1.32.8；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-C08 问题与表现

controller-manager / scheduler 重启，日志 failed to renew lease 和 leaderelection lost。

## KK-C08 最终根因或已确认边界

同一时点 apiserver Handler timeout、etcd request timed out/apply request took too long，形成 etcd 延迟→API lease 更新超时→主动退出链。历史未发现 OOM/满盘/时钟跳变，etcd 约4.4MB 且无 alarm。

## KK-C08 处理方案

围绕时间窗口检查控制面 CPU 调度/虚拟化抖动及磁盘延迟，观测 etcd/API 请求延迟。2vCPU 控制面是容量风险，但缺少最终资源瓶颈量测，不能仅据规格认定唯一原因；不要在小库上盲目 defrag 或修改 leader lease 参数掩盖延迟。

## KK-C08 验证证据与限制

现场日志及排除项已核实；性能原因与扩容后结果待验证。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-C08 来源定位

- Codex 会话 `019d9001-85fa-74e1-8139-e17f1bfb9e81`；始于 2026-04-15。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
