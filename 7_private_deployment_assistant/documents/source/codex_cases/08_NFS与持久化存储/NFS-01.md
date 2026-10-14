# NFS-01：多个roleGroups nfs节点不等于HA

项目：g_kube_installer / g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-06-29, 2026-09-10（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## NFS-01 问题与表现

把两个Master都标nfs，希望一个挂了自动续用另一个；担心数据拆成两份。

## NFS-01 最终根因或已确认边界

旧流程每节点导出各自本地目录，生成重复hosts映射，但Chart仅消费一个nfs.server。缺数据同步/VIP/failover/fencing，不是HA。

## NFS-01 处理方案

历史引入single/external：single仅一个nfs角色，external无本地nfs角色且指定稳定nfsServer VIP/FQDN。外部HA仍由用户已有存储实现，安装器不编排DRBD/Pacemaker。预检在SSH变更前拒多节点/危险路径。

## NFS-01 验证证据与限制

配置校验/包测试及构建通过，没有HA故障切换演练；早期建议多角色可安装不应当成后续支持策略。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## NFS-01 来源定位

- Codex 会话 `019f128d-bfb8-72f3-9dcd-d4da9f6f5aa0`；始于 2026-06-29。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a08a42-c807-7e93-aac6-15b78272d1d0`；始于 2026-09-10。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
