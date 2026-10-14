# WEB-02：ComponentsStatus私钥路径没有透传

项目：g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-05-09（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## WEB-02 问题与表现

集群安装SSH成功，ComponentsStatus报either private key or password must be provided。

## WEB-02 最终根因或已确认边界

GetMasterSSHConfig返回SSHClientConfig时漏传PrivateKeyPath；不同功能SSH配置构造并不相同。

## WEB-02 处理方案

沿保存hosts信息到GetMasterSSHConfig再到SSH客户端透传私钥路径，同时保留用户/端口。区分配置路径、文件在服务容器内可见性和节点认证；不得把密码硬编码当修复。

## WEB-02 验证证据与限制

历史代码定位/修复记录；没有该次正式组件状态API闭环证据。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## WEB-02 来源定位

- Codex 会话 `019e0baa-05fc-7120-aeb3-04dbb297c88c`；始于 2026-05-09。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
