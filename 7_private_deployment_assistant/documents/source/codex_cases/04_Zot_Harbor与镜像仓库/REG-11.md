# REG-11：Zot数据目录改为data-zot不自动迁移旧数据

项目：g_kube_installer / g_web_installer。记录状态：待验证。来源会话起始日期：2026-09-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-11 问题与表现

升级后GUI看不到旧镜像，旧数据仍在/mnt/registry/zot。

## REG-11 最终根因或已确认边界

新常量将工作目录、storage.rootDirectory和systemd可写路径统一/data/zot，但代码修改不自动搬运既存数据。GUI索引/访问端点也可能与push端点不同。

## REG-11 处理方案

先核对服务启动参数/config.json、/v2/_catalog与repository tags及真实push端点。确需目录迁移时停止服务，迁移数据并设置zot属主，再启动核对。保留containerd数据和无关仓库，不能把卸载Zot当清空节点。

## REG-11 验证证据与限制

历史独立数据目录修改有测试/构建，但本条给出的会话是安装链路说明；数据迁移和UI最终恢复未验证。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-11 来源定位

- Codex 会话 `01a0bca9-a5c7-7c81-bf16-7ef6acbf6739`；始于 2026-09-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
