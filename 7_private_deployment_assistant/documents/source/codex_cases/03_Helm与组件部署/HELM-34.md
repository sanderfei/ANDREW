# HELM-34：多release数据库端口和资源名称冲突

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-07-29, 2026-07-30（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-34 问题与表现

不同版本MySQL/MSSQL同一集群是否端口冲突；去掉timeout后部署超时。

## HELM-34 最终根因或已确认边界

Pod内部3306/1433可重复，冲突由hostNetwork/hostPort、固定NodePort和资源名称/namespace决定。不同namespace不能隔离集群级NodePort。--wait不写timeout仍有默认5分钟。

## HELM-34 处理方案

多版本测试用不同release/namespace且ClusterIP，模板检查资源名与PVC；真要对外暴露则不同NodePort/负载均衡入口。首次拉镜像/初始化按实际时间给wait窗口，勿把timeout20m理解为必须等20分钟。

## HELM-34 验证证据与限制

历史214/215多数据库逐个安装及SQL访问通过，非所有组件同时常驻容量证明。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-34 来源定位

- Codex 会话 `019fb1d7-4e6f-7b62-822e-4bb10959cc3e`；始于 2026-07-30。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019fabf4-d087-7020-ba90-77a51c8c3b7b`；始于 2026-07-29。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
