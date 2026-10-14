# HELM-06：MySQL首启探针过短与Pinpoint初始化SQL失败

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-04-15（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-06 问题与表现

MySQL初始化中startupProbe失败，后续persisted data/redo异常；另有ERROR1007库已存在及外键建表顺序错误。

## HELM-06 最终根因或已确认边界

该长会话有三次不同阻塞：首启窗口不足、CREATE DATABASE非幂等、BATCH_JOB_EXECUTION先于被引用的BATCH_JOB_INSTANCE创建。不能只靠放宽探针解释SQL主动退出。

## HELM-06 处理方案

给予符合初始化耗时的startupProbe，SQL使用IF NOT EXISTS并先创建被引用表。历史73821ab重新打包mysql.tgz并推送。已有数据先判断是否完整并备份，不能为通过安装直接删除业务PVC；新初始化脚本不自动迁移旧卷。

## HELM-06 验证证据与限制

lint/template与SQL修复有记录；该会话没有完整MySQL业务恢复闭环，保留待现场确认。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-06 来源定位

- Codex 会话 `019d9001-85fa-74e1-8139-e17f1bfb9e81`；始于 2026-04-15。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
