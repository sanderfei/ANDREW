# HELM-02：ingress admission证书not yet valid

项目：g_kube_installer。记录状态：待验证。来源会话起始日期：2026-04-29（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-02 问题与表现

pre-install/pre-upgrade hook失败；apiserver提示证书尚未生效。

## HELM-02 最终根因或已确认边界

webhook内部证书NotBefore晚于控制面当前UTC时间；与外部业务HTTPS证书不同，重点是节点真实时间而非显示时区。

## HELM-02 处理方案

比较所有相关节点UTC/NTP状态和证书有效期，先统一时间，再按实际Chart重建admission证书及create/patch Hook并重试。不要仅清pending锁或关闭webhook绕过根因。

### HELM-02 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
date -u
timedatectl status
chronyc tracking
kubectl -n ingress-nginx get jobs,pods
```

## HELM-02 验证证据与限制

日志时间差确认not yet valid；未记录重建后Hook成功。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-02 来源定位

- Codex 会话 `019dd6c2-058b-7663-9904-8e6f8f22861f`；始于 2026-04-29。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
