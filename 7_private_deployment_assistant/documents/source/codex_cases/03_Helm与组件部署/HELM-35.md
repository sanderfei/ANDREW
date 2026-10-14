# HELM-35：Elasticsearch deployed但内存requests满导致无Endpoint

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-08-31（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-35 问题与表现

KK报告组件安装成功，ES StatefulSet0/1、Pending/Unschedulable，Service无Endpoint。

## HELM-35 最终根因或已确认边界

历史两节点内存requests约98%，ES请求2Gi无法调度，PVC30Gi已Bound。KK该路径没有--wait，成功只表示资源提交。

## HELM-35 处理方案

检查节点requests账本和调度events，增加或释放可调度容量。历史临时降request到256Mi验证服务能运行，但实用内存约1.375GB，不能把低request当合理长期配置。最终在用户授权的测试环境清理其他业务后按2Gi默认重装验证；不照搬清理业务数据到客户现场。

## HELM-35 验证证据与限制

后续121新KK安装、2Gi request/5Gi limit/1Gi JVM、PodReady0重启、green及4插件通过；之前58业务namespace与PVC清理是授权测试操作，不作为通用修复命令。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-35 来源定位

- Codex 会话 `01a056e4-c464-7211-92f1-7361bdbc24c0`；始于 2026-08-31。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
