# HELM-15：Apollo数据库名大小写与DeletedAt schema问题

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-04-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-15 问题与表现

Hibernate DialectResolutionInfo异常、Unknown database apolloconfigdb，或ServerConfig.DeletedAt缺列。

## HELM-15 最终根因或已确认边界

初始化库ApolloConfigDB/ApolloPortalDB与JDBC小写名不一致；schema缺列是另一早期版本问题，不是Hibernate别名serverconf0_大小写。

## HELM-15 处理方案

统一初始化和连接为apolloconfigdb/apolloportaldb，同步sql及mysql/mariadb.tgz；旧数据单独备份迁移，脚本仅新初始化自动生效。核对最终schema再判断DeletedAt。

## HELM-15 验证证据与限制

历史214三个ApolloPod1/1，health200，Portal登录页200；f05eeb0修正库名。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-15 来源定位

- Codex 会话 `019da8b7-4fb6-7c53-9418-182a68ec00e3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
