# NFS-08：NFS4ERR_PERM因高位源端口需要exports匹配

项目：g_kube_installer / g_web_installer。记录状态：历史功能验证。来源会话起始日期：2026-07-23（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## NFS-08 问题与表现

Go直连NFS CreateTask写验证NFS4ERR_PERM，Linux挂载看似正常。

## NFS-08 最终根因或已确认边界

历史Go客户端使用非保留高位源端口，Linux服务端默认secure端口策略拒绝；exports的insecure是允许高位客户端端口，与registryHTTP/TLS无关。

## NFS-08 处理方案

确认真实客户端来源IP和导出路径后，在限定客户端exports策略允许对应端口行为，避免对所有网段开放。验证真实create-task写探针及完整读写，不盲目降NFSv3或改目录chmod。

## NFS-08 验证证据与限制

215受限export补insecure后121CreateTask拒绝→成功，写探针无残留。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## NFS-08 来源定位

- Codex 会话 `019f8c93-8796-7c53-8ef4-c07f7c0baddf`；始于 2026-07-23。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
