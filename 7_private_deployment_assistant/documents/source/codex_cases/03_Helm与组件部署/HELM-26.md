# HELM-26：Pinpoint HBase后台进程退出但Pod仍Running

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-07-29（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-26 问题与表现

HMaster/RegionServer后台进程可能退出，PID1是tail，Pod显示Running；堆和容器内存不匹配。

## HELM-26 最终根因或已确认边界

没有业务进程探针，容器存活不等于HBase可用；两个Java进程共用容器，需要计算总堆及native开销。

## HELM-26 处理方案

按启动/就绪/存活职责配置探针，检查PID文件及进程；启动窗口上限不是固定等待。最终历史配置HBASE_HEAPSIZE=1024、request2Gi/limit6Gi，以最后对齐运维值为准，不沿用早期2G草稿。

## HELM-26 验证证据与限制

包内断言/归档一致性通过；未进行真实故障注入或OOM恢复验证。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-26 来源定位

- Codex 会话 `019fabf4-d087-7020-ba90-77a51c8c3b7b`；始于 2026-07-29。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
