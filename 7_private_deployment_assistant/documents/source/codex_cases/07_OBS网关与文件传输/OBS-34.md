# OBS-34 私有化 OBS 分片上传在 10.02 秒显示 canceled

记录日期为 2026-11-23。用户在私有化部署环境通过浏览器上传大文件。源码核对基于 `private-service` 的 `c41b48f9`。现场部署版本、入口拓扑及实际配置待核实。

## 现象

页面显示上传进度 40%。浏览器 Network 中两次 `upload` 请求耗时都是 10.02 秒，状态为 `(canceled)`，Size 显示 0.0 kB；多次成功请求耗时约 7 秒，HTTP 状态为 200。0.0 kB 是浏览器记录的响应大小，已发送的分片字节数仍需查看请求详情。截图未显示取消请求的分片序号、错误码或后端返回体。

## 已确认的超时配置

| 层级 | 仓库配置或实现 | 作用范围 |
|---|---|---|
| 私有化 HTTP 服务 | `etc/config.yaml:21` 中 `application.http.service.timeout` 为 100 秒；`internal/app/transport/http/http.go:58` 按秒配置 Kratos | 作用于每个 HTTP 请求。实际值取决于启动使用的配置文件或 Apollo。配置中的 10 秒是 `application.grpc.service.timeout` |
| OBS 网关客户端 | `internal/app/pkg/util/obs.go:74` 中元数据请求默认 60 秒、文件传输上限 6 小时 | 两类请求继承父请求的截止时间和取消信号 |
| 分片上传 | `internal/app/service/privatization/service.go:5336` 写入本地临时分片，`:5356` 在分片未收齐时返回，收齐后合并并调用 `obsUploadFile` | 单片用时包括入站请求体、鉴权及分片落盘。收齐后的请求还要等待完整文件写入 OBS |

两次耗时高度接近，值得优先核对发起请求时设置的 10000 毫秒超时或取消逻辑。仅凭浏览器状态无法确定触发点。入口代理和运行中服务也可能使用与仓库不同的配置。

## 现场核对步骤

1. 打开失败请求的 Payload 和 Timing，记录失败时刻、`chunk_index`、`total_chunks` 和实际耗时。检查该 XHR 实例的 `timeout`、取消调用及报错；共享记录时去除凭据。
2. 在同一时间窗口对照这条请求的入口访问日志和私有化服务日志，核对入口记录的耗时、上游状态以及应用是否收到了取消信号。若看到 499（下游先断开）或 504（网关超时），结合该层的上下游和配置判断。
3. 从启动配置核对 `APOLLO_CONFIG_ENABLE` 与 `CONFIG_PATH` 决定的生效来源，只查看 HTTP 服务超时值。按实际 Request URL 确认证据对应的 Ingress 或代理。确定哪一层先结束请求后，仅调整该层，再复测相同分片。
4. 检查所有分片均已接收，上传返回 `merged=true`、`success=true`，并核对 OBS 对象大小。现场仍缺上述证据，状态为 `unverified`。

后续出现的另一次请求在 4.05 秒返回 HTTP 500。其网关 PUT 已成功，应用在关闭临时文件时报错，单独记录于 [OBS-35](OBS-35.md)。两次 10.02 秒取消仍待用各自的请求记录确认原因。
