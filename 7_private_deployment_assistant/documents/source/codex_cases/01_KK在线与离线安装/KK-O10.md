# KK-O10：add nodes未先安装socat和conntrack依赖

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-05-12（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-O10 问题与表现

create cluster 会装基础依赖，新增干净节点却在 NodePreCheck 失败。

## KK-O10 最终根因或已确认边界

旧普通 Kubernetes 新增节点流水线未复用相同的 OS 依赖安装路径。

## KK-O10 处理方案

历史增加 StatusModule 后的 RepositoryOnlineModule/RepositoryModule，限定到尚未加入集群的新节点，然后执行 NodePreCheck。按是否带 artifact 选择源；安装的是 OS 基础包，不是应用组件。k3s/k8e 不在这次修复范围。

## KK-O10 验证证据与限制

相关包带构建标签编译通过；没有记录此项完整新增节点实装闭环。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-O10 来源定位

- Codex 会话 `019e1afd-83f9-7fc1-98dc-f16372a318bd`；始于 2026-05-12。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
