# HELM-23：Milvus账号配置路径与旧etcd数据保留

项目：g_kube_installer。记录状态：历史功能验证。来源会话起始日期：2026-08-12, 2026-08-31（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-23 问题与表现

界面不要求密码、YAML密码改了不生效，215查询Helm失败。

## HELM-23 最终根因或已确认边界

历史WebRequireName/RequirePwd=false但通用字段可持久化；KK用milvus.extraConfig.common.security.defaultRootPassword。旧etcd/PVC保留旧凭据，已有proxy可能使precheck跳过。

## HELM-23 处理方案

逐层核对Web元数据→保存YAML缩进→KKoverride→ChartConfigMap及旧状态。只支持root的版本不要传其他用户名。通过实际MilvusAPI受控认证确认，不打印Secret或密码。worker无kubeconfig时从控制面查对象、两节点分别测NodePort。

## HELM-23 验证证据与限制

历史Milvus2.6.0、NodePort30530在214/215有效候选HTTP200/code0，错误候选401/code1800；不含明文。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-23 来源定位

- Codex 会话 `01a056e4-c464-7211-92f1-7361bdbc24c0`；始于 2026-08-31。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019ff4a8-2a85-7430-bb79-e576e4793ee1`；始于 2026-08-12。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
