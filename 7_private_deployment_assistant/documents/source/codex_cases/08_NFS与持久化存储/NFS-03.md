# NFS-03：Web NFSv4客户端不能自动兼容v3

项目：g_kube_installer / g_web_installer。记录状态：历史功能验证。来源会话起始日期：2026-09-29（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## NFS-03 问题与表现

创建NFS任务或备份传输拒NFSv3，只探测2049仍成功。

## NFS-03 最终根因或已确认边界

旧nfs4.DialAuto只试v4.1/v4.0，v3另需rpcbind/mountd和独立RPC路径。

## NFS-03 处理方案

历史共享客户端v4优先，仅明确协议/版本不支持才回退v3；权限、missingexport、超时不触发盲目降级。v3放通rpcbind111、mountd及NFS实际端口，验证上传/下载/比对/删除及真实认证CreateTask。

## NFS-03 验证证据与限制

121v3/v4各2.4MB读写删除一致，真实create-task成功并持久execution_location=REMOTE，无效export不落任务；PR#404。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## NFS-03 来源定位

- Codex 会话 `01a0ec7f-4204-78e0-a504-3fcda2f86723`；始于 2026-09-29。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
