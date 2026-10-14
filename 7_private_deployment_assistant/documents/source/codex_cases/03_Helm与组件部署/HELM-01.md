# HELM-01：another operation in progress与pending修订

项目：g_kube_installer。记录状态：历史状态验证。来源会话起始日期：2026-04-29, 2026-05-18（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-01 问题与表现

Helm install/upgrade/rollback提示another operation；nginx历史多条pending-upgrade/pending-rollback。

## HELM-01 最终根因或已确认边界

release元数据处于pending不一定仍有helm进程。历史nginx成功revision42、failed43、pending44/45/46；failed版本不是回滚基线。

## HELM-01 处理方案

先在各执行端确认没有活动Helm/KK任务，再查list/status/history及release存储。优先选择最后已成功修订恢复；若pending阻挡恢复，仅在备份对应元数据后精确清理故障pending记录，不批量删除。Secret后端适用，其他HELM_DRIVER需另查。锁解除后仍查admission Hook真正失败原因。

### HELM-01 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
helm list -A --pending
helm history nginx -n ingress-nginx
helm status nginx -n ingress-nginx
kubectl get secrets -n ingress-nginx -l owner=helm,name=nginx -o custom-columns=NAME:.metadata.name,STATUS:.metadata.labels.status,REV:.metadata.labels.version
```

## HELM-01 验证证据与限制

5月历史用户输出显示清理后42 deployed/43 failed，锁解除；Hook问题没有最终关闭证据。4月另一现场rev5待验证，不能照抄42。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-01 来源定位

- Codex 会话 `019dd6c2-058b-7663-9904-8e6f8f22861f`；始于 2026-04-29。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019e39d0-a474-7313-a050-2a1384c7ceda`；始于 2026-05-18。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
