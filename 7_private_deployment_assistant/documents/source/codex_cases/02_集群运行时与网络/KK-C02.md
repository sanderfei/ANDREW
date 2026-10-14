# KK-C02：CoreDNS1.9.3不支持kubeadm1.32生成的新Corefile

项目：g_kube_installer。记录状态：代码已验证。来源会话起始日期：2026-04-15（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes 1.32.8；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-C02 问题与表现

K8s 1.32.8 安装后 CoreDNS 启动失败；Corefile 中 cache disable 等新语法无法识别。

## KK-C02 最终根因或已确认边界

旧 GetImage 版本映射把 1.32.8 落入 CoreDNS 1.9.3/pause 3.9 分支，与 kubeadm 1.32 配置不匹配。

## KK-C02 处理方案

持久修复为 1.32.x 映射 CoreDNS 1.11.3、pause 3.10，核对真实仓库 repository/tag 并补齐 artifact。去掉新语法是旧现场临时兼容方案。后续用户要求保留统一 registry 路由，因此不能沿用早期强制 registry.k8s.io 的草稿。docker.io 的 CoreDNS tag 与中国区/私库是否带 v 必须分别查。

## KK-C02 验证证据与限制

历史已修改映射；这条长会话含多次方案调整，使用最后仓库路由方案。没有在本次文档任务重新验证镜像可用性。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-C02 来源定位

- Codex 会话 `019d9001-85fa-74e1-8139-e17f1bfb9e81`；始于 2026-04-15。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
