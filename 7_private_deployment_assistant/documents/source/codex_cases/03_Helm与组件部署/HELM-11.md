# HELM-11：Nacos3初始化数据库缺config_info_gray等表

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-04-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-11 问题与表现

config_gray namespace migrate pre check failed，升级后缺列/缺表。

## HELM-11 最终根因或已确认边界

新Nacos服务器与内嵌MariaDB/MySQL初始化schema版本不匹配。独立sql源文件和tgz内真实initdbScripts可能不同。

## HELM-11 处理方案

同步目标版本官方schema与项目初始化数据到实际两个数据库包，包含config_info_gray等所需结构。只改SQL源文件不影响go:embed包。旧PVC不会重新执行首启初始化，应单独做备份与增量迁移。

## HELM-11 验证证据与限制

历史更新归档并c254d9d提交，后续启动问题转为模式配置；旧业务数据库迁移未作为已验证事项。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-11 来源定位

- Codex 会话 `019da8b7-4fb6-7c53-9418-182a68ec00e3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
