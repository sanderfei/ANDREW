# KK-O05：Harbor离线初始化回退到GitHub下载

项目：g_kube_installer。记录状态：待验证。来源会话起始日期：2026-07-21（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-O05 问题与表现

kk init registry 带 -a 仍尝试下载 harbor-offline-installer-v2.10.2.tgz。

## KK-O05 最终根因或已确认边界

历史 KK 默认 Harbor 从 v2.5.3 升为 v2.10.2，旧 artifact 缺少所需文件或校验不匹配。RegistryPackageModule 的旧逻辑遇到缺失/错误本地包会联网回退。

## KK-O05 处理方案

用目标 KK 对应的 manifest 重新导出制品，确认 registry/harbor/v2.10.2/amd64/harbor-offline-installer-v2.10.2.tgz 存在且匹配版本表校验值。不能把修改 manifest 当作已经更新旧制品，也不能通过修改校验值接受错误下载。

### KK-O05 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
tar -tzf g_kube_installer-artifact.tar.gz | rg "registry/harbor/"
```

## KK-O05 验证证据与限制

Git 历史定位 a57cbf3 和旧下载逻辑；提供制品核对步骤，未找到这次重新初始化完成的记录。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-O05 来源定位

- Codex 会话 `019f842c-ee19-7382-95c8-fc50e58bc4e7`；始于 2026-07-21。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
