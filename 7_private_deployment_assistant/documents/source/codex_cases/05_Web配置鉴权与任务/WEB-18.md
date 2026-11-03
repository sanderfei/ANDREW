# WEB-18：Web接口ERR_EMPTY_RESPONSE且未取得HTTP响应

项目：g_web_installer。记录日期：2026-10-29。记录状态：待定位；失败接口与部署链路尚未确认。

适用环境：用户确认问题发生在浏览器调用 Web 接口时，具体失败 URL、HTTP Method、耗时、发生时刻、目标服务器、部署方式、Web 运行版本和代理配置均未提供。本轮核对本地 `release/290fd15` 源码，不能将其默认监听方式视为客户现场事实。Kubernetes 和操作系统版本未知，在线、离线模式均需按实际链路核对。

## WEB-18 问题现象

浏览器 Network 面板显示 `(failed)net::ERR_EMPTY_RESPONSE`。用户已澄清这是 Web 接口调用问题。本案例独立记录，不与仓库镜像查询或 Shell 续行粘贴错误合并。

## WEB-18 已确认边界与证据

Chromium 的 `net/base/net_error_list.h:604-605` 将 `EMPTY_RESPONSE` 定义为网络错误 `-324`，含义为连接在未发送数据时已关闭。它不是 HTTP 状态码；当前只能确认浏览器没有取得有效 HTTP 响应，不能据此确定由应用、代理还是中间链路结束连接。

仅凭该错误不能认定镜像缺失、JWT 失效、CORS、服务崩溃、超时、OOM 或代理故障。上述部分情况可作为后续排查方向，均不是本轮已确认根因。

当前源码提供以下排查参照：

- `cmd/server/main.go:27-38` 默认监听 `:8080`，使用明文 HTTP 的 `ListenAndServe()`；`G_WEB_INSTALLER_PORT` 可改变监听地址。`ReadTimeout`、`WriteTimeout` 均为 90 分钟。客户是否运行此版本、是否经 TLS 终止/反向代理或使用该端口，尚未核实；不能因浏览器空响应就直接扩大超时。
- `internal/transport/router.go:16-27` 使用 `gin.Default()`，为 `/api/v1` 安装 JWT 中间件，并注册只读 `GET /api/v1/profile`。
- `internal/service/login/middleware.go:11-37` 在没有 Token 或 Token 无效时调用 `response.Error` 返回未认证错误；`internal/transport/pkg/response/response.go:14-19,28-37` 将其写为 JSON 响应，`pkg/errors/errors.go:136-138` 与 `pkg/errors/errors_code.go:31` 最终对应 HTTP `401`。因此这版源码的常规 JWT 拒绝应有 HTTP 响应，不能把浏览器空响应直接归因为 JWT。
- 该版本依赖的 Gin `Default()` 安装 Logger 和 Recovery。被 Recovery 捕获的普通请求 panic 通常返回 `500`，不能把所有 panic 都解释成空响应。未恢复的后台 goroutine panic、OOM 或进程退出需要对应时刻日志等证据，当前均未确认。

## WEB-18 可执行排查步骤

1. 记录失败请求的脱敏 URL、HTTP Method、发生时刻和持续时间，并确认是单个接口还是全部接口失败。记录浏览器访问入口及实际部署目标，确定是否有反向代理、负载均衡、端口映射或 TLS 终止。不要将 Authorization、Cookie、Token 或完整客户配置写入案例。
2. 在实际 Web 服务所在运行环境执行以下无凭据只读探测；实际端口不同时替换 `8080`。这是对基础 HTTP 响应路径的检查，不重放未知有副作用的业务请求：

   ```bash
   curl --noproxy '*' -v --connect-timeout 5 --max-time 15 'http://127.0.0.1:8080/api/v1/profile'
   ```

   若 Web 在容器里运行，且使用独立容器网络，宿主机回环地址不等于容器回环地址；应在该容器环境探测，或使用实际发布到宿主机的端口。不要据此猜测客户端地址或直接将 HTTPS URL 改为 HTTP；探测使用的是源码所示后端协议，外部入口仍按现场配置核对。
3. 按实际结果划分边界：无凭据请求在当前源码下应收到 `401` JSON，这只证明本次被测基础 HTTP 链路有响应，不证明原故障接口正常、登录成功或业务恢复。连接拒绝、超时、TLS/协议错误或 `Empty reply from server` 需分别记录，不能相互等同；15 秒只是本次诊断命令上限，不是服务端故障阈值。
4. 对照同一时刻 Web 进程标准错误/服务日志、进程重启记录、系统或容器 OOM 信息；如果确实存在代理，再对照它的访问日志与错误日志。比较外部失败请求与直连后端的结果，定位请求在哪一段消失。没有代理存在的证据前，不将代理故障写成根因。
5. 取得失败接口和日志后再确定修复。当前没有授权或证据支持关闭鉴权、修改业务代码、盲目扩大超时、部署或重启；不能将这些操作作为已验证的解决方案。

## WEB-18 验证结果与遗留事项

本轮完成 Chromium 错误语义与本地 Web 监听、路由、JWT 响应代码路径核对，仅提供只读排查命令，没有连接目标环境、执行探测、重放业务接口或修改业务源码。仍待失败 URL/Method/耗时/时间、部署目标和对应日志，以及基础响应探测的结果。最终根因和恢复均未确认，元数据保持 `unverified`。

## WEB-18 来源定位

- 用户提供的浏览器错误文本及“Web 接口调用”的澄清；只保存脱敏现象与结论。
- `g_web_installer` 本地 `release/290fd15`：`cmd/server/main.go:27-38`、`internal/transport/router.go:16-27`、`internal/service/login/middleware.go:11-37`、`internal/transport/pkg/response/response.go:14-19,28-37`、`pkg/errors/errors.go:136-138`、`pkg/errors/errors_code.go:31`。
- [Chromium 网络错误定义](https://raw.githubusercontent.com/chromium/chromium/main/net/base/net_error_list.h)：`EMPTY_RESPONSE`，本轮读取时位于 604-605 行；主分支行号后续可能变化。
- [Gin v1.10.1 Default 实现](https://github.com/gin-gonic/gin/blob/v1.10.1/gin.go#L223-L228)；[Gin v1.10.1 Recovery 实现](https://github.com/gin-gonic/gin/blob/v1.10.1/recovery.go)。

[返回案例索引](../README.md)
