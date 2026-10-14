# HELM-05：升级Chart后私有registry覆盖无效

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-08-04（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-05 问题与表现

传image.registry但最终Pod仍拉公网，initContainer/Hook镜像漏替换。

## HELM-05 最终根因或已确认边界

各Chart的global.imageRegistry、完整customImage或嵌套字段不同，不存在通用--set registry适配所有包。

## HELM-05 处理方案

按实际tgz+KK参数渲染：Bitnami优先global.imageRegistry；Neo4j完整customImage拆registry/repository/tag；Seata BusyBox单独覆盖；Nacos peer-finder及Milvus os-shell要核对。保持repository/tag不变，检查所有常规运行和升级Hook镜像。

## HELM-05 验证证据与限制

历史15/15包lint、私仓渲染及归档一致性通过；当轮未重新实装。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-05 来源定位

- Codex 会话 `019fca60-203c-77e3-aede-263fd60b5a7a`；始于 2026-08-04。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
