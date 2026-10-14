# HELM-03：Redis包缺common子Chart

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-04-15（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-03 问题与表现

Chart.yaml有common依赖但charts目录为空，helm模板提示依赖缺失。

## HELM-03 最终根因或已确认边界

下载/重打包只带主Chart，离线安装不能临时依赖公网dependency update。

## HELM-03 处理方案

按Chart.lock/依赖版本将common子包放入charts后重新打包实际redis.tgz。历史Redis23.1.0补common2.31.4，lint/template验证；真实依赖版本以目标包为准。

## HELM-03 验证证据与限制

最终redis.tgz包含依赖，helm lint/template通过；未记录该次现场Redis功能验证。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-03 来源定位

- Codex 会话 `019d9001-85fa-74e1-8139-e17f1bfb9e81`；始于 2026-04-15。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
