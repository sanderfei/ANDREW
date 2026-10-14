# WEB-11：NFS存储位置和任务远程执行位置是两个配置

项目：g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-07-23, 2026-07-28（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## WEB-11 问题与表现

传nfs_server后任务仍LOCAL，或把NFS误当SSH remote_server。

## WEB-11 最终根因或已确认边界

NFS是备份数据目的地，执行位置历史由remote_server决定；nfs_server本身不会创建服务器。旧存储remote协议后改为nfs。

## WEB-11 处理方案

区分execution_location、SSHremote_server和nfs_server(host/port/export_path)。端口省略/0默认2049。创建前验证导出可访问；按实际目标版本确认最终执行字段，不能把开发建议当代码现行值。

## WEB-11 验证证据与限制

配置持久化与验证实现记录；后续NFSv3兼容有真实API证明。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## WEB-11 来源定位

- Codex 会话 `019fa651-7fbb-7fd0-a241-ca3a1dfc4512`；始于 2026-07-28。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019f8c93-8796-7c53-8ef4-c07f7c0baddf`；始于 2026-07-23。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
