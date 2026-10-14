# REG-03：Harbor缺少dmp和cloud项目导致push拒绝

项目：g_kube_installer / g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-09-18（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-03 问题与表现

部分镜像推送成功，dmp 或 cloud/neo4j 被拒；projects 查询返回404。

## REG-03 最终根因或已确认边界

清单出现新一级项目，但初始化脚本 harbor_projects 未创建 dmp/cloud。不能把后续拒绝一律看作旧密码缓存或重复推送。

## REG-03 处理方案

先查询对应 project，缺失则按安装策略创建后重试；持久修复补入 harbor_projects。补 project 不需要重启 Web。Zot 不使用 Harbor project API，不能套用该操作。

## REG-03 验证证据与限制

历史404确认项目缺失；两项模板修改 PR #51 合并（2cb66b8/7b470c2）。没有本次重新验证客户全部清单。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-03 来源定位

- Codex 会话 `01a0b30c-04bf-7fc0-954b-f763a87a463e`；始于 2026-09-18。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a0b396-9930-75e1-8954-874cb2cd724e`；始于 2026-09-18。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
