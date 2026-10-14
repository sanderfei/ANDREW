# REG-14：Harbor数据库dirty82导致core与jobservice重启

项目：g_kube_installer / g_web_installer。记录状态：历史状态验证。来源会话起始日期：2026-04-15（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-14 问题与表现

harbor-core Dirty database version 82，jobservice连不上core并CrashLoop。

## REG-14 最终根因或已确认边界

之前迁移中断/复用旧PVC留下dirty状态；缺/etc/harbor/ssl提示不是本条主因。

## REG-14 处理方案

保留数据场景先备份和核对迁移版本/失败SQL，按对应Harbor恢复流程处理；不能随意force版本。无保留数据的测试环境可明确授权后清理release及相关PVC/底层目录重装，只删namespace不保证干净。

## REG-14 验证证据与限制

历史后续Pod/StatefulSet状态符合启动成功；没有完整业务镜像读写验证，也没有证明生产库迁移恢复安全。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-14 来源定位

- Codex 会话 `019d9001-85fa-74e1-8139-e17f1bfb9e81`；始于 2026-04-15。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
