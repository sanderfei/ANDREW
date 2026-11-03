# REG-21：init registry被Zot仓库地址格式校验提前拒绝

项目：g_web_installer / g_kube_installer。记录日期：2026-10-29。记录状态：截图与源码已定位，实际配置及修正后初始化待验证。

环境：Web 集群离线部署页面执行初始化仓库。目标服务器、实际 KK/Web 版本、Kubernetes 和操作系统版本未提供。本轮只读核对本地 Web `release/290fd15` 与 KK `test/9a73986` 相关后端源码，不能将本地版本视为现场版本。

## REG-21 问题与表现

页面先显示 `Initializing registry with kk...`，随后出现：

```text
error: zot privateRegistry must be a hostname or IPv4 address with an optional port, without a URL scheme or path
Error: Failed to initialize registry
Command failed with error: exit status 1
```

## REG-21 已确认原因与边界

原始错误来自 KK 对 `spec.registry.privateRegistry` 的地址格式校验。字段需要域名或 IPv4，可带端口，不能包含 URL 协议头、路径、查询参数、片段或用户信息。带 `https://`、仓库项目路径或末尾 `/` 均可能触发截图中的同一条错误；空值等解析失败也会进入该分支。截图没有实际字段值，因此不能断言用户具体填了哪种非法格式。

在所核对源码中，`NewKubeRuntime` 读取配置并调用 `ValidateZotRegistry`，失败直接返回，尚未进入 `InitRegistryPipeline` 的解包、证书生成与仓库安装阶段。这条报错本身没有提供 Zot 服务故障、网络不可达或认证失败的证据。

## REG-21 源码证据

- Web `internal/service/offline/offline.go:153`、`:177`、`:179`：脚本进入 `data/cluster/<cluster>`，执行 `kk init registry -f config.yaml -a <artifact>`。配置路径相对于 Web 进程工作目录。
- Web `internal/service/offline/offline.go:180`、`:41`：`Error: Failed to initialize registry` 与终端底部失败提示是包装层信息，原因应看之前的 KK 原始错误。
- Web `internal/service/cluster/cluster.go:168`、`:183`、`:186`：集群更新接口将完整配置保存至对应 `config.yaml`，初始化接口不另传仓库地址。
- KK `cmd/kk/pkg/common/zot.go:20-27`：`ZotEndpoint` 对 `"https://" + cfg.PrivateRegistry` 调用 URL 解析，解析失败、主机为空，或含用户信息、路径、查询、片段时返回截图中的原文错误。
- KK `cmd/kk/pkg/common/zot.go:45-50`、`cmd/kk/pkg/common/kube_runtime.go:64-76`：Zot 类型启用上述校验，错误向上传递。
- KK `cmd/kk/pkg/pipelines/init_registry.go:80-89`：运行时创建成功后才调用初始化流水线。

## REG-21 可执行处理步骤

1. 在受影响集群配置中核对 `spec.registry.type` 和 `spec.registry.privateRegistry`。实际文件为 `<Web进程工作目录>/data/cluster/<集群名>/config.yaml`，不要误改另一集群或另一份配置。
2. 将地址写为实际使用的 `主机名或IPv4:端口`；示例结构如下，域名和端口需要匹配实际部署：

   ```yaml
   spec:
     registry:
       type: zot
       privateRegistry: digiwin.gkubeinstaller.local:444
   ```

   不写成 `https://digiwin.gkubeinstaller.local:444`、`digiwin.gkubeinstaller.local:444/` 或 `digiwin.gkubeinstaller.local:444/project`。配置字段省略协议并不改变受管 Zot 使用 HTTPS 的约定。
3. 如改变了实际主机或端口，还需核对 `spec.registry.auths` 的对应键；仅去掉误填的协议或路径时，也应确认键与最终主机、端口一致。凭据不写入案例或聊天日志。
4. 保存正确集群配置后重新执行初始化，观察完整任务终态。通过格式校验只说明越过当前错误，仍需后续安装及仓库功能证据才能确认恢复。

## REG-21 验证结果与遗留事项

本轮证据为用户截图和本地相关源码，未读取客户配置、未连接服务器，未修改业务代码、运行配置或执行安装重试。当前没有修正后的任务日志、仓库 `/v2/` 检查或实际镜像操作结果，整体保持 `unverified`。

### 2026-10-29 续问：是否写入 /etc/hosts 时携带端口

用户提出 hosts 写入带端口的可能性。当前源码中，本机写入 `cmd/kk/pkg/bootstrap/registry/tasks.go:302` 和远端节点 hosts 生成 `cmd/kk/pkg/bootstrap/os/templates/init_script.go:270` 均调用 `Registry.GetHostname()`；其实现 `cmd/kk/apis/g_kube_installer/v1alpha2/cluster_types.go:364-370` 会去掉端口。示例 `digiwin.gkubeinstaller.local:444` 最终用于 hosts 的名称是 `digiwin.gkubeinstaller.local`，端口仍保留在 `privateRegistry` 供仓库访问使用。

截图原始错误发生在运行时配置校验，先于整个初始化流水线及其 hosts 写入任务；合法的 `域名:端口` 本身允许通过该校验。因此本条截图无法归因于向 hosts 写入了端口。即使现场留有历史错误 hosts 行，它也不是这条配置解析错误的直接来源；本轮没有读取现场 hosts 或确定实际配置值，现场文件与实际二进制版本仍待核对。

与 [REG-04](REG-04.md) 的客户端 HTTP/HTTPS 协议错配、[REG-17](REG-17.md) 的特殊字符凭据及 NAT 证书 SAN 风险分开记录；本案例是安装前的仓库地址字段格式拒绝。

[返回案例索引](../README.md)
