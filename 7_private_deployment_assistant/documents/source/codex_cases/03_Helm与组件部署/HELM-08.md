# HELM-08：数据库依赖配置bothDB导致Apollo和Cadence传空参数

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-04-15, 2026-08-04（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-08 问题与表现

Helm required数据库host/user为空；Apollo/Cadence依赖库已安装仍失败。

## HELM-08 最终根因或已确认边界

旧bothDB分支只查部分数据库；Cadence甚至仅bothDB=true才取值，实际配置与分支不符。

## HELM-08 处理方案

最终历史设计Apollo/Cadence等统一依赖独立MariaDB，从保存组件配置取连接信息并校验缺项。历史代码统计5项MariaDB消费者：Apollo、Nacos、Cadence、Pinpoint、Seata；mysql.external命名不代表依赖MySQL组件。按版本核对，不沿用早期双库回退草稿。

## HELM-08 验证证据与限制

代码已修改/提交，后续组件专项实装另见对应案例；此统计属于历史源码快照。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-08 来源定位

- Codex 会话 `019d9001-85fa-74e1-8139-e17f1bfb9e81`；始于 2026-04-15。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019fca60-203c-77e3-aede-263fd60b5a7a`；始于 2026-08-04。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
