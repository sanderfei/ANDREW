# REG-19：Harbor删除非空项目412与应用推送环境依赖

项目：g_kube_installer / g_web_installer。记录状态：历史功能验证。来源会话起始日期：2026-07-23, 2026-07-27（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-19 问题与表现

测试清理项目返回412；Web以containerd运行时怀疑无法PushAppImages。

## REG-19 最终根因或已确认边界

Harbor非空项目保护需先清仓库。该推送接口读Docker-save归档后由Go客户端推registry，不依赖部署机Dockerdaemon，但仍依赖网络/DNS/TLS/认证和可写暂存路径。

## REG-19 处理方案

限定测试对象先删repository再删project，保留业务仓库。按归档真实结构及最终registry配置推送；不能把不依赖Docker等同不依赖环境。镜像备份旧docker-save路径是另一功能，需要分别核对。

## REG-19 验证证据与限制

121现有alpineTAR真实API推送，Harbor manifest/config/layer可读且config digest一致；测试412随后按正确顺序清理。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-19 来源定位

- Codex 会话 `019f8c93-8796-7c53-8ef4-c07f7c0baddf`；始于 2026-07-23。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019fa2fa-18bc-7b81-91c4-d4f4d3ea916c`；始于 2026-07-27。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
