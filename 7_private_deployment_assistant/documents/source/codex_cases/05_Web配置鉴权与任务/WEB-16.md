# WEB-16：V3服务端登录会话缺失导致401

项目：g_web_installer。记录日期：2026-10-20。记录状态：V3 中间件拦截条件已定位，具体会话失效触发和截图请求 URL 待验证。

适用环境：本地 test 及 121 Web 源码 HEAD 均为 `e982a0f51e557d00caf4e6d66c7cc5820314eba2`；121 采用 `/root/wfweb/g_web_installer` 的独立后端进程方式，上一轮已执行该提交的编译和启动。本轮仅核对源码 HEAD 和脱敏访问日志，没有重新核对运行二进制或调用认证接口。与 Kubernetes 版本、OS 和安装模式无直接关联。

## WEB-16 问题表现

用户提供浏览器 Network 截图，选中名称为 `list` 的请求，其响应为：

```json
{"error":"v3 login session is missing or expired, please login again"}
```

截图没有显示 Request URL、方法或目标服务器，不能只凭 `list/delete` 名称判断是本地文件接口还是 OBS 远端接口。已请求用户补充 URL 和方法，不索取 Authorization、Cookie 或 Token。

## WEB-16 问题原因与已确认边界

1. 当前源码中，该错误字符串由 `internal/transport/handler/obs_v3_middleware.go` 的 `ObsV3Middleware` 返回：路由需要 OBS 网关会话，但 `GetOpsCredentialsV3` 没有取得当前 JWT 对应的有效服务端会话时，直接返回 HTTP 401。当前请求在调用 OBS 网关业务 handler 之前已被拦截。
2. V3 分组先经过 Web JWT 鉴权及 OBS 用户字段检查，再检查 V3 会话。因此这条特定错误不能简单等同于 Web JWT 已过期、账号密码错误或 OBS 包文件异常。
3. `internal/service/login/ops_session_v3.go` 的 `opsSessionsV3.entries` 是进程内存 map。V3 登录会为 JWT 写入随机会话 ID，并将 IAM 应用/用户凭据绑定到对应 map 项；凭据不写入 JWT 或本地文件。服务进程重启后该 map 重新为空，浏览器旧 JWT 即使仍能通过签名和期限校验，也无法找回此前 V3 会话。
4. 缺少 JWT 会话 ID、查不到 map 项、会话过期、会话身份字段不匹配，以及此前网关拒绝 IAM 凭据后清除当前会话，也可能使会话检查失败。本轮未检查用户的 JWT 内容或服务端会话，不能把重启写成本次截图的唯一已证实触发原因。
5. 前一轮 Web 发布确实执行了重启，因而重启丢失内存会话与现象相符，但这仍是需要请求 URL、登录时序或重新登录结果支持的推断。

本问题与 [WEB-09](WEB-09.md) 的上游 `TOKEN_INVALID` 不同：此处为 Web 自身 V3 中间件在网关请求前拒绝，不能把上游应用/用户凭据哪一项失效的结论套用到这里。

## WEB-16 121 只读证据

固定使用 `ssh codex-test-121`，只读取源码提交和 `logs/server.log` 尾部访问记录。仅提取相关路由的方法、路径和状态码，去除 query，未输出登录正文、认证 Header、Cookie 或 Token。

相关访问记录按日志中出现的顺序归纳如下，未将这些记录强行对应到截图：

| 请求 | 观察状态 | 说明 |
|---|---|---|
| `GET /api/v1/obs/file/local/list` | 多次 200 | V1 本地列表存在被请求并返回 200 的记录 |
| `POST /api/v3/obs/file/local/delete` | 404 | 请求使用了不存在的 V3 本地删除地址；对应问题见 OBS-23 |
| `POST /api/v3/obs/folder/list` | 401，后续另有 200 | V3 OBS 目录列表确有认证失败记录，后来也有成功 HTTP 记录 |

访问日志不包含此次响应正文，不能仅凭其中的 401 认定其与截图为同一请求；后来 200 也不能证明是同一用户重新登录修复。未取得该请求的 JWT 或同一浏览器的登录链路，不判定具体会话失效方式。

## WEB-16 处理方案

先根据浏览器 Headers 中的完整 Request URL 和方法区分操作目标：

- 若操作本地 `data/obs/local/` 文件，应使用 `GET /api/v1/obs/file/local/list` 或 `POST /api/v1/obs/file/local/delete`，仅需要有效 Web JWT，不依赖 V3 IAM 会话。删除地址的 `/api/v3` 应改为 `/api/v1`，详见 [OBS-23](../07_OBS网关与文件传输/OBS-23.md)。
- 若操作 OBS 远端目录/文件，相关 V3 路由仍需要 V3 登录。重新完成 `POST /api/v3/login` 的内层登录，后续请求改用这次返回的新 Web JWT。若外层 Web 登录也失效，先通过 `POST /api/login` 重新建立外层登录，再进行 V3 登录。不要只沿用旧 token 或仅刷新页面。
- 可用 `GET /api/v3/isOps/login` 检查当前 JWT 的 V3 会话是否存在；此接口读取同一个服务端会话表。随后重试实际业务请求，以业务响应确认恢复。

本轮未代用户登录、重试删除或修改调用方，也未修改业务代码、提交、推送、部署或再次重启。

## WEB-16 验证结果与遗留事项

- 已确认错误产生位置、V3 内存会话机制，以及 V1 本地文件接口不会经过上述 V3 会话检查。
- 已取得 121 当前源码 HEAD 与相关 HTTP 状态记录。
- 待用户补充截图请求 URL/方法，或取得重新 V3 登录后同一请求的成功结果。
- 未验证本次浏览器会话确因前一轮重启失效，未验证删除成功或具体业务恢复，元数据为 `unverified`。

## WEB-16 来源

- 用户 2026-10-20 提供的 Network 错误预览截图。
- `g_web_installer/internal/transport/handler/obs_v3_middleware.go:49`、`internal/transport/router.go:23`、`internal/transport/router.go:61`、`internal/transport/router.go:183`。
- `g_web_installer/internal/service/login/ops_session_v3.go:23`、`internal/service/login/middleware.go`、`internal/service/login/ops_login_v3.go:156`。
- `g_web_installer/internal/transport/handler/file_server_v3.go:20`。
- 本轮 121 只读 Git 提交与脱敏相关路由访问日志结果；上一轮发布命令证据见 OBS-23。

[返回案例索引](../README.md)
