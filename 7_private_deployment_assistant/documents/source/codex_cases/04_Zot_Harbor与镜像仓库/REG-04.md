# REG-04：Harbor或Zot的HTTPS444被客户端当作HTTP

项目：g_kube_installer / g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-09-20, 2026-10-08（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes 1.32.8；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-04 问题与表现

HEAD http://digiwin.gkubeinstaller.local:444/.../pause/manifests/3.10 返回400 Bad Request。

## REG-04 最终根因或已确认边界

受管仓库在444提供HTTPS，旧 insecureRegistries 分支生成HTTP endpoint。证书跳过选项不改变协议；已有 containerd 又可能保留旧配置。

## REG-04 处理方案

历史 f9828e9 等修复限定离线且带 registry 角色的 Harbor/Zot，privateRegistry 对应 endpoint 统一HTTPS；检查每个节点实际 config_path/hosts.toml，重启正确运行时后用 crictl pull 闭环。Web 固定 KK 二进制也需更新。

## REG-04 验证证据与限制

配置场景测试/构建通过；早期干净节点有成功安装记录，但2026-10-08客户worker修复后的pull未取得，不能宣称所有现场已修好。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-04 来源定位

- Codex 会话 `01a0bca9-a5c7-7c81-bf16-7ef6acbf6739`；始于 2026-09-20。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a11acc-4df5-78f3-9d32-2b2307bff4c5`；始于 2026-10-08。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
