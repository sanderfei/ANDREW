# KK-O02：1.23.10与1.32.8的运行时和配置差异

项目：g_kube_installer。记录状态：源码结论。来源会话起始日期：2026-04-15, 2026-07-22（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-O02 问题与表现

高版本沿用低版本 kubeadm、pause、CoreDNS 或 Docker 配置而失败。

## KK-O02 最终根因或已确认边界

项目历史版本分支分别处理 kubeadm 配置结构、CRI 接入、PSP 和 ingress-nginx Chart；不是只替换 Kubernetes 镜像 tag。

## KK-O02 处理方案

本项目现行支持范围按用户约定：1.23.10 支持 Ubuntu/CentOS，1.32.8 支持 Ubuntu。1.23.10 对应历史 kubeadm v1beta3、pause 3.6、CoreDNS 1.8.6；1.32.8 对应 v1beta4、pause 3.10、CoreDNS 1.11.3，具体 tag 是否带 v 取决于镜像仓库。Web 高版本默认 containerd；若自行选 Docker，另核对 cri-dockerd 二进制和 socket。

## KK-O02 验证证据与限制

历史源码与配置模板核对；没有把历史其他版本描述为当前受支持版本。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-O02 来源定位

- Codex 会话 `019f885c-37ff-7ba1-8684-30e6d14bc858`；始于 2026-07-22。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019d9001-85fa-74e1-8139-e17f1bfb9e81`；始于 2026-04-15。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
