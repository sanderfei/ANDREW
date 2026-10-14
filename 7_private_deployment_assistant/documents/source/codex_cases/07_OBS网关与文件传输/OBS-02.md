# OBS-02：408 RequestTimeout在OBS而非浏览器HTTP超时

项目：g_web_installer。记录状态：待验证。来源会话起始日期：2026-08-12（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## OBS-02 问题与表现

异步registry_push日志HTTP408/RequestTimeout带OBSRequestID。

## OBS-02 最终根因或已确认边界

状态来自OBS上游请求，任务已异步返回PID；调大Axios或Web响应超时不直接修复这段上游传输。历史SDK4xx（含408）不自动重试、checkpoint关闭。

## OBS-02 处理方案

按PID明确卡在pull、归档还是OBS传输，再查网络/代理/endpoint、分片大小和并发、可恢复重试策略。历史100MiB/4并发及阈值只属当时实现；避免无限重试不确定覆盖。

## OBS-02 验证证据与限制

历史源码和SDK错误阶段确认；最终408现场根因没有记录。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## OBS-02 来源定位

- Codex 会话 `019ff4a4-8c23-7a63-aecb-9f31290a1918`；始于 2026-08-12。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
