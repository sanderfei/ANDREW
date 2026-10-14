# WEB-01：全局app.yaml与集群config.yaml及容器数据挂载

项目：g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-04-20, 2026-10-10（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## WEB-01 问题与表现

Web启动后data/config没有config.yaml，或OBS提示registry credentials not configured in config file。

## WEB-01 最终根因或已确认边界

全局设置是data/config/app.yaml，集群KK文件是data/cluster/<cluster>/config.yaml；启动不自动生成全局设置。早期代码固定configs/app.yaml，历史修为data/config优先并兼容cwd/可执行文件目录。挂载可遮住镜像内文件。

## WEB-01 处理方案

先确认目标版本LoadConfig及挂载路径，再把全局设置放进真实运行data/config/app.yaml。勿为修问题复制整个含密码的客户YAML到知识库。Docker登录状态不能代替Go镜像客户端所需运行配置。

## WEB-01 验证证据与限制

配置解析聚焦测试通过；2026-10-10解释为源码结论，未访问客户容器。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## WEB-01 来源定位

- Codex 会话 `01a123ed-8f95-7d10-97c1-e7521f6ee643`；始于 2026-10-10。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019da8f6-435c-7673-8dfe-09956eaf3dd3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
