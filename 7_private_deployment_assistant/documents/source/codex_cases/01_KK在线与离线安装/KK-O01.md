# KK-O01：在线与离线模式的实际开关及三步安装

项目：g_kube_installer。记录状态：源码结论。来源会话起始日期：2026-07-22（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-O01 问题与表现

配置里写了 offline，但安装仍访问网络；不清楚 init registry、images push、create cluster 各负责什么。

## KK-O01 最终根因或已确认边界

普通 Kubernetes 流水线以是否传入 -a artifact（runtime.Arg.Artifact）选择在线或离线源；spec.system.install 是 Web 的业务标记，不能代替 KK 参数。

## KK-O01 处理方案

在线显式填写目标版本并执行 create cluster -f；离线先准备匹配 artifact，再初始化仓库、推送镜像、创建集群。--skip-push-images 只省去重复推送，节点仍要拉取镜像。--with-packages 保留在 Web 的离线命令中；历史定制主流水线曾重复执行 RepositoryModule，需按目标二进制确认。

### KK-O01 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
./kk create cluster -f config.yaml -y
./kk init registry -f config.yaml -a g_kube_installer-artifact.tar.gz
./kk artifact image push -f config.yaml -a g_kube_installer-artifact.tar.gz
./kk create cluster -f config.yaml -a g_kube_installer-artifact.tar.gz -y --skip-push-images --with-packages
```

## KK-O01 验证证据与限制

历史通过源码及 CLI help 核对流程；不代表任意现场安装已成功。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## KK-O01 来源定位

- Codex 会话 `019f885c-37ff-7ba1-8684-30e6d14bc858`；始于 2026-07-22。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
