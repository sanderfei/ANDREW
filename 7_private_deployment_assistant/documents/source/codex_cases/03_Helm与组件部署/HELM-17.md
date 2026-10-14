# HELM-17：Seata使用旧Nacos域名或写死namespace

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-04-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-17 问题与表现

UnknownHostException nacos-headless；替换地址后仍注册503。

## HELM-17 最终根因或已确认边界

旧包写死nacos-0.nacos-headless，而实际Service为nacos-cs/nacos-hs；另有写死namespace。现场ConfigMap可仍来自旧KK嵌包。后续503是Nacosnaming未Ready。

## HELM-17 处理方案

按实际Service修正nacos server-addr及默认公共namespace，重新打包/编译/部署，检查真实ConfigMap生效。域名修复后再排Nacos业务Ready，不能把所有错误归为DNS。

## HELM-17 验证证据与限制

历史Nacos/Seata最终均Ready；明确旧ConfigMap与新源码不同，需核实实际运行KK。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-17 来源定位

- Codex 会话 `019da8b7-4fb6-7c53-9418-182a68ec00e3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
