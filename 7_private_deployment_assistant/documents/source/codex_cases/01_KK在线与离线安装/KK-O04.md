# KK-O04：离线制品的宿主机路径与容器路径不一致

项目：g_kube_installer。记录状态：源码结论。来源会话起始日期：2026-10-13（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-O04 问题与表现

包已复制到服务器，但 Web 提示缺少 artifact 或 please run InitRegistry first。

## KK-O04 最终根因或已确认边界

Web 按进程工作目录读取 data/cluster/<cluster>/g_kube_installer-artifact.tar.gz；文件存在于别的目录或未映射的宿主机路径时不可见。提示不等于必须重复初始化仓库。

## KK-O04 处理方案

核对容器 Mounts 和进程 cwd，把包放进实际挂载的对应集群目录。默认 root 安装脚本映射 /root/g_web_installer_data 到 /g_web_installer/data；自定义部署以实际映射为准。已有共享仓库时仍需要本集群 artifact 提供二进制和 OS 依赖。

## KK-O04 验证证据与限制

2026-10-13 源码分析确认存在性检查；未验证此次客户路径。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-O04 来源定位

- Codex 会话 `01a1335b-0dc5-78f2-8722-2aa5f948ef7d`；始于 2026-10-13。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
