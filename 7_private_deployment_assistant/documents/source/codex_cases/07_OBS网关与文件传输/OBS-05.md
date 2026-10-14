# OBS-05：registry上传ECONNRESET因同步长任务跨HTTP窗口

项目：g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-04-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## OBS-05 问题与表现

前端代理ECONNRESET，拉镜像/打包/上传迟迟不返回。

## OBS-05 最终根因或已确认边界

历史接口同步等待整个任务，Web当时Read/WriteTimeout2分钟；超时是高度匹配因素，但单个ECONNRESET也可能进程OOM/panic，需要日志确认。

## OBS-05 处理方案

历史RegistryPushToObs改ExecuteAsync，预建history/log并立即返回PID；前端按PID查最终日志。success:true只受理不代表上传完成。不能拿此历史异步改法解释所有同步V3最后分片上传。

## OBS-05 验证证据与限制

编译通过，日志目录初始化代码核对；原代理故障未做同路径耗时回归。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## OBS-05 来源定位

- Codex 会话 `019da8f6-435c-7673-8dfe-09956eaf3dd3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
