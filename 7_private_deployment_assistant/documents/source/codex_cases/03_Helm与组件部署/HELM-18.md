# HELM-18：Seata store.db键及MySQL8驱动超时不兼容

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-08-04（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-18 问题与表现

Seata分布式锁配置错误、数据库通信失败、Socket超时或无法发布Nacos配置。

## HELM-18 最终根因或已确认边界

升级后配置键应为store.db.*，distributedLockTable缺失；旧驱动类/连接参数不适配当前数据库。

## HELM-18 处理方案

修正store.db.distributedLockTable=distributed_lock等键，使用com.mysql.cj.jdbc.Driver，历史connectTimeout10s/socketTimeout60s及rewriteBatchedStatements=true；发布Nacos后逐项核对配置。参数应随目标Seata/驱动版本确认。

## HELM-18 验证证据与限制

a1a4919/6d9203f；现场Ready0重启、8091/9091、控制台登录、Nacos健康实例和Ingress200通过，合并版本最终复测。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-18 来源定位

- Codex 会话 `019fca60-203c-77e3-aede-263fd60b5a7a`；始于 2026-08-04。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
