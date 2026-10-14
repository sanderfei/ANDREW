# HELM-22：Milvus历史失败Hook Pod使Web健康状态误判

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-08-12（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-22 问题与表现

Helm deployed且服务健康，Web is_success=false，命名空间留一个ErrorPod。

## HELM-22 最终根因或已确认边界

Job使用Never重试创建旧FailedPod，但最终JobComplete；Web旧算法将任一FailedPod判整组件失败。Running也不等于Ready。

## HELM-22 处理方案

历史milvus.tgz增加before-hook-creation,hook-succeeded清理成功Hook；Web判定需结合release、ownerReferences/Hook注解、Job最终状态与长期服务Ready。更改OnFailure仅规避部分现象，不能代替完整状态判断。

## HELM-22 验证证据与限制

74b090b包修改推送及214遗留Pod清理记录；通用Web状态判定建议不能当作当轮已全部实现。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-22 来源定位

- Codex 会话 `019ff49e-b946-72a0-8913-0ab2764c18ca`；始于 2026-08-12。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
