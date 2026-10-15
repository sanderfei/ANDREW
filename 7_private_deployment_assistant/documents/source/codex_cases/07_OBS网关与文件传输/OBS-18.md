# OBS-18：V3上传取消日志归属及网关与接口超时边界

项目：g_web_installer。记录日期：2026-10-15。记录状态：待验证（日志归属与本地调用链已确认，现场取消原因未闭环）。

适用环境：本地 release 工作区，HEAD 为 00a0d61，上传与中间件存在未提交改动；结论基于本轮实际读取的工作区源码，不代表目标机已部署相同代码。部署机器、运行配置、文件大小与请求耗时均未提供。适用流程为 Web V3 普通文件/分片上传；Kubernetes、OS、安装方式未限定。

## OBS-18 问题与表现

用户询问上传对象时的以下错误是否来自后端。脱敏后的核心形式为：

```text
Put "https://<obs-gateway>/api/v1/objects/content?bucket=<bucket>&key=<object-key>": context canceled
```

仅保留方法、接口路径及错误类型，不保存实际域名、业务目录、文件名或任何认证信息。

## OBS-18 最终根因或已确认边界

1. 本地 Web 网关客户端调用 http.Client.Do 失败后，会以 error 字段记录底层错误，并包含 method、endpoint、elapsed_ms。该日志形式与用户提供的内容匹配，属于 Web 后端作为 HTTP 客户端调用 OBS 网关时产生的传输错误，不是已确认的 OBS 服务端 HTTP 业务错误响应。
2. 普通上传将进入请求的 Context 传到网关 PUT。浏览器/调用端断开或入口代理结束上游连接时，可能取消进入请求，进而取消 Web 发往网关的 PUT；后端显式取消同样需要排查。
3. context canceled 表示上下文被取消；Context 自身到达 deadline 的标准错误为 context deadline exceeded。外层浏览器/代理超时仍可表现为本地 context canceled，不能仅靠这一个字符串断定哪个节点超时。
4. 本轮没有完整日志、elapsed_ms、入口代理记录或客户端错误，尚未定位谁先取消。不能直接归因为浏览器固定十分钟超时，也不能认定 OBS 故障、鉴权失败、对象不存在或上传已完整成功。
5. 普通上传使用同步 executeOperation(..., false, ...)，异步任务路径另有 WithoutCancel 与独立超时；不能将本结论泛化为所有 OBS 后台任务都会随浏览器关闭而中断。

## OBS-18 关键源码证据

- g_web_installer/internal/service/image_gateway/client.go:139：NewRequestWithContext 将传入上下文绑定到出站 HTTP 请求。
- g_web_installer/internal/service/image_gateway/client.go:157：执行 httpClient.Do；159-164 行记录原始传输错误，随后在 Context 已结束时返回 ctx.Err()。
- g_web_installer/internal/service/image_gateway/client.go:268：Put 使用传输超时并调用 PUT /api/v1/objects/content；成功还需检查 HTTP 201 及返回的 key、size。
- g_web_installer/internal/transport/handler/obs_v3_middleware.go:69：使用 c.Request.Context() 创建 ObsV3Context；83-96 行在长请求原 Context 上派生超时。
- g_web_installer/internal/service/file_server/file_server_v3_upload.go:66、125：完整上传与分片合并后的上传都同步等待网关调用。
- g_web_installer/internal/service/file_server/obs_v3_progress.go:98-107：上传进度包装后继续传递 obsContext.ctx 给 Put。
- g_web_installer/internal/service/file_server/file_server_v3.go:82：只有异步执行分支使用 context.WithoutCancel。

## OBS-18 排查与处理步骤

1. 在实际部署版本中核对上述方法和中间件，避免将本地未提交代码视为线上版本。先记录目标版本、上传开始/失败时间、请求耗时与文件大小。
2. 从 Web 日志定位同一请求的 method、endpoint、elapsed_ms 和上传进度；从入口代理访问/错误日志核对客户端断开、499/504、上游超时等记录。排查时使用脱敏副本，不记录认证头。

```bash
rg -n -C 4 'context canceled|elapsed_ms|image_gateway' /path/to/server.log
```

上面的日志路径需替换为实际部署日志路径。本轮没有执行线上日志读取。

3. 对照调用端的取消/超时发生时间和服务端 Context 原因。若确认入口或调用端先超时，调整对应长传输链路的期限；若确认后端误用请求上下文承载应独立存活的任务，再设计持久后台任务与独立期限。这里均为条件性处理建议，未实施修改。
4. 若需判断该次文件是否已经写入，以网关对象元信息、大小及必要的校验值核验；HTTP 客户端取消不能证明远端没有收到或没有完成上传。
5. 使用同一目标、同类文件和明确的完整性验证确认修复；单次请求启动、日志消失或进程运行不构成功能恢复证据。

## OBS-18 网关与接口超时补充（2026-10-15）

本轮继续只读核对同一本地工作区，没有读取目标机器运行配置或确认现场二进制版本。

| 层次 | 本地当前代码的值 | 说明 |
|---|---|---|
| Web 到 OBS 网关的上传 PUT、下载 GET、大对象复制 | 21600 秒（6 小时） | 每次调用使用 transfer timeout；继承的父 Context 更早结束时仍会提前结束 |
| 列表等元数据请求 | 30 秒 | 使用 metadata timeout |
| 异步后台任务总时间 | 43200 秒（12 小时） | 任务内单次 PUT 仍受传输超时限制 |
| HTTP Server 全局 ReadTimeout / WriteTimeout | 各 90 分钟 | 是服务器读写期限，不等同于所有业务任务的 Context 生命周期 |
| V3 普通上传等指定长接口的 Context 与读取 deadline | 从中间件设置时起 6 小时 | 中间件单独覆盖这些长接口的读写期限 |
| 上述 V3 长接口的写响应 deadline | 6 小时加 30 秒 | 为业务 Context 超时后的错误响应留时间 |
| Web 到网关的建连 / TLS 握手 | 分别 60 秒 | 连接阶段期限，不是文件传输总期限 |

关键配置事实：internal/config/config.go:37 的 LoadConfig 直接返回固定常量，没有读取 app.yaml。configs/app.yaml 的示例值虽然相同，但编辑该文件不会改变当前代码返回的超时；data/config/app.yaml 在本地不存在。以上均不能替代现场版本核对。

源码定位：

- internal/config/image_gateway.go:11-13：metadata=30、transfer=21600、async=43200。
- internal/config/config.go:50-55：将上述常量直接构造成 ImageGatewayConfig。
- internal/service/image_gateway/client.go:61-65：连接与 TLS 各 60 秒，ResponseHeaderTimeout=0；IdleConnTimeout=90 秒只影响空闲连接复用。
- internal/service/image_gateway/client.go:276：PUT 传输 Context；318 行为 GET；380 行为大对象复制。
- cmd/server/main.go:27-32：全局 HTTP 读写各 90 分钟。
- internal/transport/handler/obs_v3_middleware.go:76-96：指定 V3 上传、下载、版本目录创建、重命名长接口的 Context 和 ReadDeadline 使用 transfer timeout，WriteDeadline 多 30 秒。
- internal/transport/router.go:183、190：V3 上传路由挂接上述中间件；本地依赖 Gin v1.10.1 的 responseWriter 支持 Unwrap，便于 ResponseController 获取底层 writer。实际协议、部署版本或其他 writer 包装仍需按现场核对。

总时间边界：普通 V3 上传的进入请求从中间件起就有 6 小时父期限，后续 PUT 再设 6 小时不会把整条链路延长为 12 小时；父 Context 更早取消时以父限制为准。网关内部到 OBS 的超时、入口代理超时和客户端超时不在这些常量的确认范围。

如果远早于上述期限就出现 context canceled，应继续核对取消来源；不能直接认定本地 6 小时传输上限已经到期。本轮只补充配置和调用链结论，没有实施超时修改或执行实际上传验证。

## OBS-18 验证结果与遗留事项

已完成：只读核对本地后端调用链、日志分支，以及 Go 官方取消语义。没有修改业务代码，没有连接现场、重传文件或发布；未执行业务功能验证。

待确认：真实取消源、目标机版本与配置、是否固定耗时失败、远端对象最终状态、修复后完整上传结果。verification_status 保持 unverified。

## OBS-18 来源定位与相关案例

- 本轮来源：2026-10-15 用户提供的脱敏后错误形态，以及上列本地项目源码读取结果。
- Go HTTP Request.Context：https://pkg.go.dev/net/http#Request.Context
- Go context.Canceled 与 DeadlineExceeded：https://pkg.go.dev/context#Canceled
- [OBS-12](OBS-12.md) 有历史浏览器十分钟取消的额外证据；本轮尚未确认相同根因，不能沿用其根因结论。若后续确认同一事件，再合并证据并同步索引。

[返回案例索引](../README.md)
