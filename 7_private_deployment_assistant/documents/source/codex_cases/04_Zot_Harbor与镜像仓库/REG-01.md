# REG-01：init registry成功后UpdateLocalHosts127或resource busy

项目：g_kube_installer / g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-09-28, 2026-09-30, 2026-10-08（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-01 问题与表现

registry 已启动，但 UpdateLocalHostsModule [LocalHost] exit127；补 sudo 后 sed -i 报 Device or resource busy/exit4。

## REG-01 最终根因或已确认边界

此任务在执行 KK 的 Web 容器/主机运行。旧 sudo sed -i 先可能缺 sudo，又因容器挂载 /etc/hosts 无法 rename。exit127 不含 stderr 时不能凭此认定唯一缺失命令。

## REG-01 处理方案

持久修复原地读写 /etc/hosts：精确匹配完整 hostname、更新旧 IP、去重，WriteAt+Truncate+Sync 保留 inode，失败恢复原内容。节点 hosts 更新与这一步分开；临时原地写入不修复旧 KK 重跑。

## REG-01 验证证据与限制

源代码/挂载问题确认；修复聚焦测试与构建通过并 PR #64 合并。未完成真实 Web 容器全流程回归。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-01 来源定位

- Codex 会话 `01a0f1be-127f-7623-b005-44535a0d38e2`；始于 2026-09-30。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a1191d-6db7-7c42-8d00-6194d609a369`；始于 2026-10-08。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a0e73a-d872-7de0-b4bd-898a8dc97d47`；始于 2026-09-28。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
