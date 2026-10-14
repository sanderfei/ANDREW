# HELM-25：Pinpoint HBase等待ZooKeeper端口不能证明quorum就绪

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-07-29（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-25 问题与表现

HBase在ZK选举完成前启动，等待端口通过仍可能初始化失败。

## HELM-25 最终根因或已确认边界

publishNotReadyAddresses可提前提供地址，原init只检查TCP；ZooKeeperreadiness与HBase等待条件彼此独立。

## HELM-25 处理方案

ZK srvr检查leader/follower，liveness用ruok/imok；HBase启动门槛检查可用quorum，历史方案要求至少leader+follower。给出有界重试，失败让初始化明确退出。

## HELM-25 验证证据与限制

修改解压Chart后已打包pinpoint.tgz、关键断言及编译通过；历史现场当时未复现故障，不把预测风险标为现场修复。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-25 来源定位

- Codex 会话 `019fabf4-d087-7020-ba90-77a51c8c3b7b`；始于 2026-07-29。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
