# NFS-15：Web已回退NFSv3但MOUNT返回AUTH_TOOWEAK

项目：g_web_installer。记录日期：2026-10-21。记录状态：待验证；已确认失败阶段，现场认证策略尚未闭环。

适用环境：Web 创建任务时选择 NFS 远端服务器，目标数据端口为 2049，导出路径为 `/fs_zsk`。现场 Web 版本、宿主机或容器部署方式、NFS 服务端系统/设备型号未知；Kubernetes、操作系统、在线/离线安装模式均未限定。本轮本地参考源码为 `release` 分支 `132955179ae4e494f984e4b615d7b293d9d4ee44`，依赖 `github.com/mactav683/go-nfs-client v0.1.0`，不等于已核验现场二进制版本。

## NFS-15 问题与表现

用户反馈已优化 NFS 协议兼容，但创建 NFS 任务仍被拒绝。截图的关键错误脱敏后为：

```text
Failed to validate NFS server:
NFSv4 unavailable: connect <NFS_SERVER>:2049: nfs4: EXCHANGE_ID:
rpc: program version mismatch (low=3 high=3)
NFSv3 connection failed: NFSv3 MOUNT /fs_zsk:
rpc: authentication error (auth_stat=5)
```

这里有两个连续阶段：v4 请求得到“该 NFS 程序只支持版本 3”的响应；客户端随后进入 v3 路径，MOUNT 请求被 RPC 认证层拒绝。截图中的两条错误是一次回退过程合并后的输出。

## NFS-15 最终根因或已确认边界

已确认：

1. 截图证明运行端实际执行了 NFSv3 回退；不能将此故障归因为客户端仍然只支持 v4。它不能证明现场二进制与本地参考提交完全一致。
2. v3 已完成 rpcbind 查询并连接 mountd，在请求 `/fs_zsk` 的 MOUNT 时收到认证拒绝。尚未取得导出目录句柄，未进入 FSINFO、创建/删除探针和备份文件读写。
3. RFC 5531 将 `auth_stat=5` 定义为 `AUTH_TOOWEAK`，表示请求因认证安全要求被拒绝；这个状态码本身不能唯一确定具体配置问题。
4. 当前客户端使用 `AUTH_SYS`，携带 Web 进程 UID/GID/附加组。mountd 与 NFS 数据连接均调用依赖的 `rpc.Dial`，其零值 `net.Dialer` 未显式绑定保留源端口，通常使用系统分配的高位临时端口。

首要待验证假设是服务端要求客户端使用小于 1024 的保留源端口，而当前客户端使用高位源端口。Linux NFS 导出的 `secure` 默认要求非 GSS 请求从小于 1024 的源端口发起，`insecure` 才允许高位源端口。这是客户端源端口要求，与表单中的服务端目的端口 2049 是两件事。即使 Web 进程以 root 运行，普通 `net.Dialer` 也不会因此自动绑定保留源端口。

现场尚无导出配置、mountd 拒绝日志或抓包，不能把上述假设写成最终根因。仍需核对服务端是否允许 `AUTH_SYS/sec=sys`，以及 NFS 服务端看到的真实 Web 来源 IP 是否满足导出策略；不同设备对拒绝原因的映射可能不同。不能仅凭该错误断言目录写权限、`root_squash` 或网络超时是根因。

## NFS-15 关键源码与证据

- `g_web_installer/internal/service/nfs_client/client.go:75`：v4 优先，明确协议/版本不支持时调用 `dialNFS3`；两条失败通过 `errors.Join` 合并。
- `internal/service/nfs_client/nfs4.go:34`：`program version mismatch` 属于允许回退的条件。
- `internal/service/nfs_client/nfs3.go:30`、`:62`：TCP 111 发现 mountd，使用 `AUTH_SYS` 发出 MOUNT；MOUNT 成功后才建立数据连接并执行 FSINFO。
- `internal/service/nfs_client/client.go:340`：认证身份来自 Web 进程的 UID/GID/附加组，没有实现 Kerberos 凭据协商。
- `go-nfs-client@v0.1.0/rpc/client.go:64`：`rpc.Dial` 使用没有配置 `LocalAddr` 的 `net.Dialer`；`:54` 提供包装已有连接的 `rpc.NewClient`。
- `internal/transport/handler/nfs_validation.go:14`、`task_execution.go:121`：创建任务前执行可写性校验，错误直接返回；未通过时不会进入后续任务目录创建。
- 本轮 `git log -- internal/service/nfs_client/nfs3.go internal/service/nfs_client/client.go` 确认 2026-09-29 的 `2dfbd65` 仍是现有 v3 兼容实现的修改记录。
- [RFC 5531 第 9 节](https://www.rfc-editor.org/rfc/rfc5531.html#section-9)：认证状态定义。
- [exports(5)](https://man7.org/linux/man-pages/man5/exports.5.html)：`secure/insecure`、`sec=` 和允许客户端的语义。

## NFS-15 处理方案

先取得服务端证据。Linux NFS 服务端可执行：

```bash
sudo exportfs -v
sudo journalctl -t rpc.mountd -t mountd --since '15 minutes ago' --no-pager
```

核对 `/fs_zsk` 对 Web 真实来源 IP 的导出规则、`secure/insecure`、`sec=`，并在重试创建任务的同一时间查看日志。日志不进入 journal 时，使用系统对应日志；NAS 使用设备管理界面的导出、保留端口和认证设置。Web 容器或 SNAT 环境要按 NFS 服务端实际看到的来源 IP 核对，不能直接使用操作浏览器的电脑 IP。

若日志明确出现 `illegal port` 或设备明确拒绝非保留源端口，可选择：

1. 在既有、限定 Web 来源 IP 的导出条目中保留其他选项并增加 `insecure`，再执行 `sudo exportfs -ra`。这是服务端允许高位客户端源端口的调整，不应顺带放宽全部网段或取消身份映射限制。当前客户端仍需服务端允许 `AUTH_SYS`。
2. 按服务端保留端口要求完善客户端连接实现，同时覆盖 mountd 与 NFS 数据连接。可以先建立绑定保留源端口的连接，再通过 `rpc.NewClient` 复用协议实现；需处理绑定权限、端口占用和网络转换。本轮仅提出实现方向，没有修改或发布该逻辑。

若服务端明确要求 Kerberos/GSS，则是当前 `AUTH_SYS` 客户端与该认证要求不匹配；需选择符合现场要求的认证方案，不能把所有 `auth_stat=5` 都按端口问题处理。若真实来源 IP 未授权，则修正对应导出条目。不要仅根据此截图修改目的端口、强制 v4 或放宽目录权限。

处理后使用相同配置重新创建任务，确认创建/删除探针成功，再验证备份上传、下载内容比对和删除。协议连接或任务创建成功各自不能替代完整备份读写验证。

## NFS-15 验证结果与遗留事项

本轮完成截图分析、本地调用链及依赖源码复核、官方协议与导出文档核对。未连接现场 NFS 或测试服务器，未修改业务代码、导出配置或目录权限，未执行部署、重启、创建任务或备份读写验证。未新增测试文件。

待补充现场 `/fs_zsk` 导出配置和失败时 mountd 拒绝日志，以确定源端口、认证类型或其他策略中的实际原因。修复及现场功能验证均未闭环，元数据为 `unverified`。

相关历史案例：[NFS-03](NFS-03.md) 记录原先缺少 v3 及其兼容实现；[NFS-08](NFS-08.md) 记录另一次已确认的 v4 高位源端口拒绝。当前 v3 事件单独记录，不能把历史案例根因直接当成现场事实。

[返回案例索引](../README.md)
