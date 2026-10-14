# OBS-03：NoSuchUpload可能表示multipart已完成

项目：g_web_installer。记录状态：历史功能验证。来源会话起始日期：2026-05-06（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## OBS-03 问题与表现

obsutil abort指定UploadId返回NoSuchUpload。

## OBS-03 最终根因或已确认边界

该未完成上传ID已完成/被清理/状态变化，不代表正式对象不存在。

## OBS-03 处理方案

重新列-m未完成任务并stat最终key。若对象已完成，abort不再适用；清理只针对授权的测试key/UploadId，不使用桶级批量删除。多part ETag不是整个文件MD5，应另校验完整字节。

## OBS-03 验证证据与限制

当次11GB正式对象存在，解释了NoSuchUpload；没有执行生产桶清理。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## OBS-03 来源定位

- Codex 会话 `019dfc40-ff43-7c53-adcd-825f5bee9539`；始于 2026-05-06。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
