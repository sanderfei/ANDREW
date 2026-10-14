# REG-07：Zot缺少离线二进制不能靠init自动下载

项目：g_kube_installer / g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-09-20, 2026-10-09（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes 1.32.8；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-07 问题与表现

artifact 缺 Zot，init registry 无法找到 zot-linux-amd64。

## REG-07 最终根因或已确认边界

Zot 是导出时下载并校验后打包的独立二进制，不是 KK 内嵌程序；manifest 未配置 zot 就不打包。

## REG-07 处理方案

恢复 spec.components.zot.version（历史v2.1.21），用对应 manifest 重新 export。tar 列表必须出现 registry/zot/v2.1.21/amd64/zot-linux-amd64。把 manifest 复制到服务器不等于制品已重建。

### REG-07 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
tar -tzf g_kube_installer-artifact.tar.gz | rg "registry/zot/.*/zot-linux-amd64"
```

## REG-07 验证证据与限制

历史恢复 manifest 并复制121成功；完整重新导出和现场init未证实。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-07 来源定位

- Codex 会话 `01a11e76-e245-75f0-82a7-b73685d728c7`；始于 2026-10-09。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a0bca9-a5c7-7c81-bf16-7ef6acbf6739`；始于 2026-09-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
