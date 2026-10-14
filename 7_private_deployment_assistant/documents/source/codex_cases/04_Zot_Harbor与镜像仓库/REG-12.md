# REG-12：PushAppImages对Zot误调用Harbor项目API

项目：g_kube_installer / g_web_installer。记录状态：历史功能验证。来源会话起始日期：2026-09-20, 2026-09-28（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-12 问题与表现

离线type=zot时应用镜像推送仍执行Harbor project检查/创建。

## REG-12 最终根因或已确认边界

Web把外部离线registry和集群内部Harbor组件的业务路径混用。

## REG-12 处理方案

按保存配置的spec.registry.type分支：Harbor或历史默认保留project流程，Zot跳过HarborAPI并使用相同配置凭据推送。只约束离线分支，保留在线及集群内部Harbor；同时核对InstallAppV1的ZIP路径，不把另一接口修好视为全部兼容。

## REG-12 验证证据与限制

本地真实Zot普通TAR/嵌套TAR推送、Harbor模拟回归及编译通过；该记录未提交或发布。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-12 来源定位

- Codex 会话 `01a0bca9-a5c7-7c81-bf16-7ef6acbf6739`；始于 2026-09-20。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a0e7b5-8ba4-7653-8222-e5c0bbf67654`；始于 2026-09-28。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
