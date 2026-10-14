# HELM-28：Elasticsearch升级后analysis插件缺失

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-08-31（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-28 问题与表现

analysis-hao、ik、pinyin、stconvert不可用，ES9.x基础镜像与业务插件不匹配。

## HELM-28 最终根因或已确认边界

插件是镜像内与ES产品版本配套的文件，不由helm--set自动安装；7.15.0插件不能当作9.x插件。Chart布局、探针、镜像入口也需同时兼容。

## HELM-28 处理方案

历史最终恢复兼容7.15.0Chart与私库插件镜像，改KK资源/registry/Ingress参数、precheck识别7.15及9.x避免误降级。证书helper改KubernetesPod并取消危险delete namespace，同步offline manifest。既有9.x数据不可原地随意降级。

## HELM-28 验证证据与限制

214/215分别验证/_nodes/plugins与4种_analyze，最终嵌包实装通过；a4ee37fd推送，当轮未发布121。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-28 来源定位

- Codex 会话 `01a056e4-c464-7211-92f1-7361bdbc24c0`；始于 2026-08-31。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
