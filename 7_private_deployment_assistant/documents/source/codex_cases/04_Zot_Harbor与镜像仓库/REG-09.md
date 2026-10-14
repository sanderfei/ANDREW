# REG-09：Zot就绪检查节点缺curl

项目：g_kube_installer / g_web_installer。记录状态：待验证。来源会话起始日期：2026-09-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 Ubuntu；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-09 问题与表现

checkZotReady 命令未找到curl，Web容器中有curl仍报错。

## REG-09 最终根因或已确认边界

检查通过SSH runner.SudoCmd 在registry节点执行；Web容器依赖不能代替目标节点依赖。

## REG-09 处理方案

在日志标出的registry节点安装/提供可用curl，离线使用匹配依赖包；联网节点可apt-get安装后再init。只读连通排查可先用已有wget/openssl，但不能改变旧检查脚本必须curl的事实。

## REG-09 验证证据与限制

历史确认执行节点与依赖，未记录补curl后完整初始化成功。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-09 来源定位

- Codex 会话 `01a0bca9-a5c7-7c81-bf16-7ef6acbf6739`；始于 2026-09-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
