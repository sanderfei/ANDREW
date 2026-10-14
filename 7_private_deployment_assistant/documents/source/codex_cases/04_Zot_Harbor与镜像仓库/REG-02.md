# REG-02：Harbor初始化密码和auths推送密码不一致

项目：g_kube_installer / g_web_installer。记录状态：历史功能验证。来源会话起始日期：2026-09-18（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-02 问题与表现

Harbor 容器 healthy，但 artifact image push Unauthorized。

## REG-02 最终根因或已确认边界

旧初始化模板与 config.yaml spec.registry.auths 的密码来源不统一；容器健康不证明调用端认证通过。

## REG-02 处理方案

在 Web 容器对实际仓库地址进行只读认证核对，把保存配置的 auths 与服务器实际认证一致。配置保存后新 KK 任务读取，无需重启 Web 或重新初始化已正常仓库；凭据仅留运行配置，不进入本文。

## REG-02 验证证据与限制

历史重新推送前50个镜像完成，随后进入缺 project 问题，表明此次认证已跨过。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-02 来源定位

- Codex 会话 `01a0b30c-04bf-7fc0-954b-f763a87a463e`；始于 2026-09-18。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
