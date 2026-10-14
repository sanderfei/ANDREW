# HELM-16：Apollo Helm覆盖hosts数组导致http paths缺失

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-04-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-16 问题与表现

Ingress校验spec.rules[0].http.paths: Required value。

## HELM-16 最终根因或已确认边界

hosts是对象数组，单独--set-string hosts[0].host可能替换数组元素并丢失paths。

## HELM-16 处理方案

覆盖configService/adminService/Portal host时同时提供对应paths[0]=/，用真实--set参数渲染完整Ingress；不是回退sed字符串替换。

## HELM-16 验证证据与限制

组件包测试通过，未记录这一参数修改单独现场验证。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-16 来源定位

- Codex 会话 `019da8b7-4fb6-7c53-9418-182a68ec00e3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
