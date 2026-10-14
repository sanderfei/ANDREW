# OBS-04：旧docker_push依赖Docker CLI导致command not found

项目：g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-04-20, 2026-08-19（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## OBS-04 问题与表现

docker login failed: exec docker executable file not found in PATH。

## OBS-04 最终根因或已确认边界

旧镜像打包路径调用docker login/pull/save，运行服务环境没有CLI/socket，不是OBS权限问题。

## OBS-04 处理方案

最终改Go registry客户端拉取并写Docker-save兼容归档，显式认证/平台并汇总逐镜像失败；不依赖Dockerdaemon、不写本机镜像缓存。对其他私库需确认凭据映射支持，不能假定Dockerlogin自动被使用。

## OBS-04 验证证据与限制

历史构建通过并确认旧CLI调用去除；后续docker load功能证明另见兼容格式案例。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## OBS-04 来源定位

- Codex 会话 `019da8f6-435c-7673-8dfe-09956eaf3dd3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a018e0-e6d3-7a11-ad79-7ea0114c8a96`；始于 2026-08-19。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
