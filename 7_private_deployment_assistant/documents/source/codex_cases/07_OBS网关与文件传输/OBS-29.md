# OBS-29：版本导入大镜像包下载被HTTP2对端重置

项目：g_web_installer。记录日期：2026-10-28。记录状态：出口选路PR427已发布121；214旧断流原因及恢复仍待验证。

适用环境：用户确认Web地址为214:8080，已只读定位容器内 `/g_web_installer/app` 进程及 `wfoff` 精准版本任务日志。运行二进制版本和编译生效的超时值尚未核实；初次只读诊断基于本地 `release/9e5b1e8`；后续出口地域签名选路通过开发验证后，以 `934701b` / PR427合并为 `bc6cd1a`，完成121Web编译替换及启动；214现场未更新，旧任务证据与对端内部原因不因此改变。Kubernetes/OS和数据库版本未限定；失败发生在包下载，尚未进入组件预检、镜像推送或数据导入。版本任务设计与交付背景见 [OBS-28](OBS-28.md)，本条独立记录正文传输故障，不与历史上传取消或浏览器下载超时合并。

## OBS-29 问题现象与日志证据

以下保留任务日志时间；关联容器主日志UTC09:28至09:35，对应CST17:28至17:35：

| 时间 | 日志事实 |
|---|---|
| 2026-10-28 17:29:06 | 版本任务开始；14个文件通过审核，7个资料文件跳过，计划处理7个包。 |
| 17:32:07 | 首个镜像tgz计划大小4311.29MiB，进度采样显示已接收8.50MiB。 |
| 17:33:33 | 首包下载报下列正文流错误，任务停止；汇总downloaded=0、validated=0、images_imported=0、databases_imported=0。 |

```text
download <版本镜像包>.tgz: save local download: stream error: stream ID 23; INTERNAL_ERROR; received from peer
```

`downloaded=0`是完整成功包的计数，不代表网络从未接收字节；8.50MiB只是已显示的中间采样，不是最终残留文件大小。日志中的Completed/结束时间也不代表成功，错误和零完成汇总表明本次没有进入后续预检及导入。

## OBS-29 已确认机制与未闭环边界

1. 故障当时对照的源码每包设置transfer timeout，调用 `client.Get(..., "")`，没有Range；只接受HTTP200并核对长度后进入本地保存。现有错误包装表明失败点为读取响应正文并写临时文件的 `io.Copy`，不是等待首个HTTP响应头，也不是镜像包格式或数据库脚本错误。
2. Go HTTP/2实现把收到的RST_STREAM错误交给响应Body读端；`received from peer` 表明重置由该HTTP/2连接对端发来，`INTERNAL_ERROR`为协议错误码。对端可能是Web连接的HTTPS网关或其前置代理；这一字符串不能定位到OBS源站、网关业务还是某个代理的内部故障。
3. 3分钟进度是日志采样周期，不是3分钟下载超时。源码默认transfer=21600秒（6小时）、async=43200秒（12小时）、metadata=30秒；当前 `LoadConfig` 使用编译常量而不读配置yaml。214容器没有源码/配置yaml，不能由此确定该二进制的有效编译值，也不能用这些默认值覆盖网关内部、反向代理或链路限制。不能据此直接判定浏览器超时或只调大Web默认值。
4. 按现源码，失败的 `.part` 临时文件由defer删除，完整下载后才Rename为正式包；当前入口没有正文失败的业务重试或断点续传，首包失败直接结束该任务。214该失败PID的packages现已核对为空，未见 `.part` 或正式包；该现场状态与源码清理机制一致，仍未取得完整包或恢复证明。

尚未闭环的是对端为何重置、具体失败节点、实际运行参数及修复后完整下载。现已从214主日志取得同对象请求ID及HTTP200/响应头耗时，但尚无该请求对应的网关或前置代理内部日志，不把协议症状写成已确认的服务端内部根因。

## OBS-29 实际Web实例核对结果

最初固定别名121只读检查：8080进程PID `1998781`，cwd/exe为 `/root/wfweb/g_web_installer` 及其 `server`，但其 `data/cluster` 无 `wfoff`。这仅排除了当时错误参照的121固定部署，不能拿其磁盘或配置代表用户任务。用户随后确认实际地址为214:8080。

通过固定别名214只读定位8080进程PID `43745`，cwd为 `/g_web_installer`，exe为 `/g_web_installer/app`，运行在容器namespace/cgroup；经该进程的 `/proc/<pid>/root` 找到 `data/cluster/wfoff/history` 下17:29:06.714开始的精准任务。其 `execute.log` 与用户给出的首包大小、8.50MiB采样、17:33:33错误及全0计数一致；对应packages目录存在但为空，没有 `.part` 或正式包。

容器data挂载宿主 `/root/g_web_installer_data`，文件系统ext4，检查时可用55,155,609,600字节（约51.37GiB）。这是当前状态，无当前空间耗尽证据；不能据此倒推故障时磁盘状态，也不能以容量数字解释HTTP2对端重置。

只读 `nerdctl --namespace k8s.io inspect` 精确匹配容器 `g_web_installer`、PID43745及其nerdctl JSON主日志。在UTC09:28至09:35窗口按目标object key精确匹配，各取得一条GET请求/响应：网关host为 `private-obs-gw.digiwincloud.com`，Range为空，HTTP状态200，`elapsed_ms=121`，request ID为 `5a145d0def2a45e1c68c6a6447a5bf5d`。121ms只计到响应头，不是4.3GiB正文下载耗时；正文在任务开始约267秒后失败，因此HTTP200不能作为下载完成证据。

另一个17:45:23的同版本任务较早快照为一个7,867,836字节 `.part`；因主日志出现新事件而补查一次，17:48:23采样8.42MiB、17:51:23采样16.63MiB，均以4311.29MiB为总量，仍是 `[2/5 下载 1/7]` 且无终态。补查时packages只有一个17,776,060字节临时文件，无正式文件。前6分钟样本平均约47KiB/s，仅说明该次确有慢传现象，不能据此认定限速配置或具体源端原因，也不证明重试失败/成功、下载完成或功能恢复；本轮没有触发该任务。

此次仅只读检查实际进程、任务日志与文件状态，没有新发下载、触发重试、HTTP2协议对照或修改配置/进程。实际二进制版本、有效超时及该request ID对应的网关/前置代理内部日志仍待补。

## OBS-29 处理建议（未实现、未执行）

1. 实际Web地址/进程和失败任务已匹配，下一步核对该二进制有效transfer/async及网关/代理设置，并以request ID `5a145d0def2a45e1c68c6a6447a5bf5d` 关联17:29至17:33的网关/前置代理日志，检查读取OBS、写客户端、传输字节和中断原因。使用脱敏记录，不保存签名URL、IAM Token或认证头。
2. 可在同一总PID、同一个 `execute.log` 内为可重试网络错误增加有界退避和顺序单包重试，不重试整个版本导入；鉴权、磁盘及包校验错误不盲目重复。重试只属于建议，现入口尚无该恢复能力，且不能靠重试掩盖持续的源端断流。
3. 4GiB级文件更适合在对象身份一致的前提下支持Range续传。现网关客户端能传Range，网关API合同 `docs/API.md` §1.3声明206、Content-Range、ETag/checksum，但一键入口未使用。实现前应核对206与请求范围、ETag/对象版本，服务端返回200时重新完整下载或停止，禁止直接拼接；最终仍需完整大小和校验值验证，不能只把收到部分字节视为成功。

初次只读诊断没有修改代码或重新触发下载；随后实现了下节签名选路增强并交付121，但上述重试/Range仍未实现，也未重新执行214现场任务。数据库整体导入重试不属于本条建议，避免在已经产生副作用的流程上重复执行。

## OBS-29 验证结果与遗留事项

- 已将失败定位到Web出站HTTP/2连接的响应正文流，用户日志确认本次完成包、预检、镜像与数据导入计数均为0。
- 实际任务已确认在214容器，失败PID日志、空packages及同对象HTTP200/121ms响应头/request ID已核对；有效编译超时、二进制版本和对端内部日志仍待补。17:45任务只确认慢传且无成功终态，不作为恢复证据。
- 没有完整文件、hash或重试后的实际业务证据，未验证功能恢复，metadata保持 `unverified`。
- 与 [OBS-02](OBS-02.md) 的OBS HTTP408、[OBS-06](OBS-06.md) 的浏览器下载/WriteTimeout、[OBS-11](OBS-11.md) 的元数据超时和 [OBS-18](OBS-18.md) 的上传context取消分别处理，不沿用其最终原因。

## OBS-29 2026-10-28 后续签名选路增强与121发布

用户要求根据Web出口大陆/台湾选择既有 `url_cn` / `url_tw`，已实现并完成定向、两包race及server构建，随后通过PR427交付121，详见 [OBS-28](OBS-28.md) 同日选路及发布段。每任务下载前一次HTTPS出口判定，未知/失败回退CN、父context取消则停；每包现签CN sign-direct或TW sign-cdn，再以无IAM/Cookie、禁redirect、identity编码的新请求保存原始字节，沿用part/大小及失败清理。未新增retry/resume，未改变API结构。

地域是Web出口而非主机物理位置，代理/VPN会影响结果；CN仍经既有网关，只有TW使用CDN。该改变不定位旧请求 `5a145d0def2a45e1c68c6a6447a5bf5d` 的RST_STREAM内部原因，也没有证明214慢传或4GiB下载已经恢复。现已commit/push并经PR427合并 `bc6cd1a` 完成121Web编译替换启动（PID2084894）；214未更新、KK未动，仍无真实GeoIP/大陆台湾/CDN大包导入验证；现有HTTP200后断流与17:45慢传记录仍为历史现场证据，metadata继续为 `unverified`。

## OBS-29 来源定位

- 后续本地 `internal/service/file_server/obs_v3_version_download.go`、`internal/service/image_gateway/signed_download.go`，新选路已随PR427部署121，不代表214已部署或业务已恢复。

- 用户提供的2026-10-28版本任务进度、错误和汇总；仅保存脱敏摘要，不复制原始完整日志或业务对象key。
- 初次诊断源码快照 `internal/service/file_server/obs_v3_version_import.go:323`（首错停止）、`:406-438`（无Range下载、状态/长度校验）。
- `internal/service/file_server/obs_v3_local_download.go:104-139`（临时文件、Body复制、失败清理与Rename）。
- `internal/service/image_gateway/client.go:59`（默认Transport）、`:158`（Do）、`:350-368`（Get/Body及取消）；`internal/config/image_gateway.go`（源码默认时间）。
- `internal/service/file_server/obs_v3_progress.go:12`（3分钟采样）；网关接口合同 `docs/API.md` §1.3（Range响应能力，不等于本入口已续传）。
- [Go 1.24.5 HTTP/2 RST_STREAM处理](https://github.com/golang/go/blob/go1.24.5/src/net/http/h2_bundle.go#L10022-L10037)；[received from peer错误标记](https://github.com/golang/go/blob/go1.24.5/src/net/http/h2_bundle.go#L1357-L1360)。源码标签用于解释协议处理，不代表已核对未知现场Go版本。
- 本轮121排除检查与214容器8080进程、精准任务日志、packages、data挂载、磁盘当前状态及nerdctl inspect映射的JSON主日志只读结果；`internal/config/config.go:3` 的编译配置说明。

[返回案例索引](../README.md)
