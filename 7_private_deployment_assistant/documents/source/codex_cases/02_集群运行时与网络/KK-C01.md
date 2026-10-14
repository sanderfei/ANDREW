# KK-C01：已有containerd关闭CRI导致unknown service runtime.v1

项目：g_kube_installer。记录状态：待验证。来源会话起始日期：2026-04-13（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes 1.32.8；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-C01 问题与表现

PullModule 的 crictl pull 报 unknown service runtime.v1.ImageService / RuntimeService。

## KK-C01 最终根因或已确认边界

历史 master 预装 containerd 2.2.2 并 disabled_plugins=[cri]；workers 是 1.7.13 且 CRI 正常。KK 检测 binary+socket 存在后跳过安装及配置，不验证预装运行时兼容性。

## KK-C01 处理方案

确认实际 containerd 版本、配置及 CRI 插件状态，按对应版本启用正确 CRI 插件并重启运行时，再用 crictl info 和目标镜像拉取验证。需统一运行时版本时按节点维护计划处理；不要把 containerd 1.x 配置块直接用于 2.x。

### KK-C01 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
containerd --version
ps -ww -C containerd -o pid,args
crictl info
```

## KK-C01 验证证据与限制

三节点运行时和 CRI 故障已实查；最终改配置后集群完成安装未记录。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-C01 来源定位

- Codex 会话 `019d85fa-2ea8-78b3-b206-29382cb353ec`；始于 2026-04-13。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
