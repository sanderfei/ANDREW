# HELM-19：Nacos和Seata IngressClass为空或端口指向错误

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-04-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## HELM-19 问题与表现

nip.io可解析，页面404；Seata IngressClass为空，Nacos UI路径端口错误。

## HELM-19 最终根因或已确认边界

DNS只把Host映射到IP，Controller需识别IngressClass及后端Service/port。Nacos3UI使用8080console，不等于8848配置API。

## HELM-19 处理方案

在最终Chart给受管Ingress配置nginx class，核对Host/Path、Service命名端口与Endpoints。比较直连应用和带Host访问Controller结果，别仅修改DNS。

## HELM-19 验证证据与限制

历史两包已修复/渲染，具体访问成功需看对应组件专项验证。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## HELM-19 来源定位

- Codex 会话 `019da8b7-4fb6-7c53-9418-182a68ec00e3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
