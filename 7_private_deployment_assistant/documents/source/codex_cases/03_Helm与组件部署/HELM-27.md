# HELM-27：Pinpoint内置MySQL初始化表缺失与依赖分支变动

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-07-29, 2026-08-04（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-27 问题与表现

PinpointWeb/Batch连接不到所需表；以为同级mysql.tgz负责创建表。

## HELM-27 最终根因或已确认边界

历史不同分支一个用Pinpoint内置MySQL，一个用独立MariaDB；同级数据库包不是自动共享。升级漏了17表及连接参数。

## HELM-27 处理方案

先确认目标分支tasks.go/Chart真实依赖。内置MySQL方案补17表initSQL、max_connections500/wait_timeout300；最终sastscan/test同步方案保留独立MariaDB，初始化应进入该归档。不要将两套历史方案同时应用。

## HELM-27 验证证据与限制

Pinpoint归档打包验证；后续分支MariaDB方案实装通过。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-27 来源定位

- Codex 会话 `019fabf4-d087-7020-ba90-77a51c8c3b7b`；始于 2026-07-29。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019fca60-203c-77e3-aede-263fd60b5a7a`；始于 2026-08-04。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
