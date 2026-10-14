# OBS-17：V3镜像归档registry重命名只改目标RepoTags

项目：g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-10-12（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## OBS-17 问题与表现

离线加载后镜像仍带源私库域名，希望打包前改registry。

## OBS-17 最终根因或已确认边界

Docker-save的RepoTags保存完整registry/project/repository:tag。改下载文件名不改镜像引用，也不应该切换源pull认证到目标库。

## OBS-17 处理方案

历史实现is_rename/registry_name，先按源地址拉取，以映射目标引用写归档，保留path/tag；拒绝digest改名、无效registry及目标碰撞，同步400验证。省略目标时历史默认内网444。不联络目标registry执行push，后续实际部署另定。

## OBS-17 验证证据与限制

本地registry/gateway隔离测试含零layer、多镜像及认证通过；最终改动当轮未提交/部署。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## OBS-17 来源定位

- Codex 会话 `01a12e08-2388-76a1-8436-3d9d3c519720`；始于 2026-10-12。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
