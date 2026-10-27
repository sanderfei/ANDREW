# OBS-20：214本地下载接口拒绝带前导斜杠的path

项目：g_web_installer。记录日期：2026-10-16。记录状态：2026-10-19 两字段均无前导斜杠的 IAM 下载功能已验证；2026-10-16 KK 制品完整下载仍待验证。

适用环境：用户说明 test 分支已部署到 214；本轮直接访问 `http://10.40.46.214:8080`。本地 test 源码为 `e901e0f`，SSH 认证未通过，未独立核验目标进程工作目录及实际部署提交。前端尚未对接，使用接口调用。

## OBS-20 问题表现

用户要求下载 OBS 对象 `kk/g_kube_installer-artifact.tar.gz` 到 Web 服务本地，向 `POST /api/v3/obs/file/download/local` 提交以下请求体：

```json
{
  "path": "/kk/g_kube_installer-artifact.tar.gz",
  "real_path": "/kk/g_kube_installer-artifact.tar.gz"
}
```

使用用户本轮提供的 Bearer 凭据发起一次真实请求，214 返回 HTTP 400：

```json
{"error":"invalid local download path: path must be a relative file path"}
```

未返回任务 PID，不能据此声称下载已开始或文件已落盘。认证值未保存到文档或本地脚本。

## OBS-20 最终定位与证据

- `internal/transport/router.go` 注册该 POST 路由，对应 `handler.DownloadObsFileLocalV3`。
- `internal/model/request/obs.go` 将 `path` 和 `real_path` 定义为必填字符串，两者语义独立。
- `internal/service/file_server/obs_v3_local_download.go` 的 `resolveObsLocalFilePathV3` 首先执行 `filepath.IsLocal`；Linux 下以 `/` 开头的绝对路径被拒绝。此处发生在异步执行器创建之前。
- `internal/service/file_server/file_server_v3.go` 的 `normalizeObsObjectKeyV3` 会去除 OBS 对象 key 的前导 `/`，因此 `real_path` 可以保留用户指定值。不能把它与本地 `path` 的校验混为一谈。
- `internal/transport/handler/obs_v3_middleware.go` 将 `ErrInvalidObsLocalDownloadV3` 映射为 HTTP 400，现场返回与本地源码一致。
- `ssh -o BatchMode=yes -o ConnectTimeout=10 codex-test-214` 返回 `Permission denied (publickey,password)`。随后直接访问 HTTP 服务成功，说明此次 SSH 认证失败并不阻止网络可达的接口调用。

原请求已确认的失败原因是本地目标 `path` 使用了绝对路径。修正参数后已取得源对象响应并开始写入下载临时文件，证据见下文；完整文件发布和离线安装仍未验证。

## OBS-20 处理方案

保留 OBS `real_path`，将本地 `path` 改为相对于 Web `data/obs/local/` 的路径：

```json
{
  "path": "kk/g_kube_installer-artifact.tar.gz",
  "real_path": "/kk/g_kube_installer-artifact.tar.gz"
}
```

目标语义为 `<Web进程工作目录>/data/obs/local/kk/g_kube_installer-artifact.tar.gz`。这里的“本地”指 214 上 Web 服务工作目录中的存储；容器部署时宿主机映射位置需要另外核对。

用户随后明确采用上述修正请求体，已于 2026-10-16 重新调用接口。后续执行步骤：

1. 使用有效登录会话的 Bearer 凭据，按修正后的请求体调用下载接口。
2. 记录返回的 `pid` 和 `download_path`。`success:true` 仅表示异步任务已创建。
3. 通过 WebSocket 连接 `/api/v3/obs/logs/tail/<pid>` 观察任务终态，并通过 `GET /api/v3/obs/file/local/list` 确认正式相对路径已出现。该日志路由需要 WebSocket Upgrade，普通 HTTP GET 返回 400，不能把此响应当作下载任务失败。若要确认宿主机实际存储位置或制品可用于安装，需要进一步的现场证据。

## OBS-20 修正参数后的实际调用

214 返回 HTTP 200、`code:10000`、`msg:OK`，任务响应为：

```json
{
  "success": true,
  "pid": "2026-10-16_09-35-43.118_v3_download_file_local_王飞_4935e7e7",
  "download_path": "/g_web_installer/data/obs/local/kk/g_kube_installer-artifact.tar.gz"
}
```

WebSocket 握手返回 101，任务日志确认源对象规范化为 `kk/g_kube_installer-artifact.tar.gz`，目标为上述绝对路径。首次本地列表请求返回 `data:[]`，暂未出现正式文件。此时仅能确认异步任务已创建，不能将 `success:true` 写成下载完成。

用户查询该任务的前端日志页面时，核对 `web/src/router/index.js` 的 `/obs/logs/tail/:pid` 路由及 `web/src/views/package/Package.vue` 的 `handleLogAction`，对应入口为：

```text
http://10.40.46.214:8080/#/obs/logs/tail/2026-10-16_09-35-43.118_v3_download_file_local_%E7%8E%8B%E9%A3%9E_4935e7e7
```

该页面使用 `web/src/views/logs/Obs.vue` 连接同源 `/api/v3/obs/logs/tail/<pid>` WebSocket，需要浏览器具备有效登录状态。本轮确认 214 根页面可返回前端 HTML；未通过真实浏览器验证该日志页面展示效果。

继续订阅同一任务后，取得真实传输进度：

```text
[2026-10-16 09:38:43] [INFO] 下载到本地进度：累计 280.41 MiB / 总量 8365.36 MiB
```

这证明已取得源对象响应并写入临时文件，进度约为 3.35%，总量约 8.17 GiB。尚未观察到 `Downloaded ... bytes`、`Operation completed successfully` 或任务失败日志，不能声称正式文件已生成。进度日志按 3 分钟周期输出，并非连续无日志就表示卡住。关闭本轮日志订阅不会取消异步任务：当前源码通过 `context.WithoutCancel` 从请求上下文分离后继续执行；本轮没有发送取消或重复下载请求。

## OBS-20 后续 IAM 归档下载请求（2026-10-16）

用户继续要求通过同一 214 接口下载 IAM 归档，并返回日志页面。本次沿用用户在当前会话中已提供的有效认证，提交请求体：

```json
{
  "path": "中间件/4.38.2/IAM/iam_4382_1006.tar",
  "real_path": "/中间件/1773213495167-4.38.2-tcudorp/1773213537087-IAM-noisrev/dingCode202603051540000239171-iam_4382_1006.tar"
}
```

`POST /api/v3/obs/file/download/local` 返回 HTTP 200、`code:10000`、`msg:OK` 和以下任务数据：

```json
{
  "success": true,
  "pid": "2026-10-16_11-47-55.597_v3_download_file_local_王飞_fc768daa",
  "download_path": "/g_web_installer/data/obs/local/中间件/4.38.2/IAM/iam_4382_1006.tar"
}
```

对应日志页面（浏览器需已登录 214）：

```text
http://10.40.46.214:8080/#/obs/logs/tail/2026-10-16_11-47-55.597_v3_download_file_local_%E7%8E%8B%E9%A3%9E_fc768daa
```

本次只确认 IAM 下载任务已创建，并向用户提供日志入口；未检查该任务进度、终态或正式文件，不声称 IAM 包已下载完成。没有重复触发之前的 KK 制品下载，没有修改代码、部署或重启服务。

用户随后要求验证本地 IAM 包导入：导入前后两次正式文件列表均包含此 IAM 路径，真实导入任务成功且目标 manifest 可读。后续功能证据单独记录于 [OBS-21](OBS-21.md)，此前“仅创建下载任务”的结论保留为当时观察范围。

## OBS-20 验证结果与遗留事项（2026-10-16 当时观察）

已验证原请求体的 HTTP 400、修正请求后的 HTTP 200、WebSocket 日志订阅及 280.41 / 8365.36 MiB 的实际写入进度。后台任务继续执行，完整下载及正式文件发布仍待验证，元数据保持 `unverified`。未修改业务代码，未部署或重启服务；没有验证 KK 安装或向 Zot 导入镜像。后续使用上面的 PID 继续订阅日志，并在成功终态后核对本地正式文件列表。

## OBS-20 请求路径前导斜杠复核（2026-10-19）

用户复核 Swagger 下载示例时，回忆上周有路径需要以 `/` 开头。本轮核对当前本地 test 后端源码及本案例 2026-10-16 的既有现场记录：当时成功受理的 KK/IAM 下载请求均使用不带前导 `/` 的本地 `path`，以及带前导 `/` 的 OBS `real_path`。

当前源码中，`resolveObsLocalFilePathV3` 在规范化前通过 `filepath.IsLocal` 校验本地 `path`，因此该字段不能以 `/` 开头；`real_path` 经 `normalizeObsObjectKeyV3` 的 `strings.TrimLeft(strings.TrimSpace(raw), "/")` 去除前导 `/` 后，作为 key 传给 Image Gateway。由此确认 `real_path` 带或不带前导 `/` 均可，历史请求使用该写法不代表字段必须带 `/`。

推荐请求形式：

```json
{
  "path": "制造部门/产品A/v1.0/images.tgz",
  "real_path": "/制造部门_123/产品A_456/v1.0_789/dingCode_images.tgz"
}
```

已在本地 `g_web_installer/swag.json` 补充两个字段的前导 `/` 规则，并将 `real_path` 示例改为带 `/`。本轮仅复核源码和已有现场记录、校验 JSON，未重新调用 214 接口、未验证当前部署版本、未修改业务代码或发布。既有现场结果及 `verification_status: unverified` 保持原有证据边界。

## OBS-20 两字段均无前导斜杠的现场验证（2026-10-19）

在用户提供当前有效认证后，直接调用 214 的 `POST /api/v3/obs/file/download/local`。请求体如下，两个字段都不以 `/` 开头；使用独立本地目录避免覆盖已有 IAM 文件：

```json
{
  "path": "slash-check/20261019/iam_4382_1006.tar",
  "real_path": "中间件/1773213495167-4.38.2-tcudorp/1773213537087-IAM-noisrev/dingCode202603051540000239171-iam_4382_1006.tar"
}
```

214 返回 HTTP 200、`code:10000`、`msg:OK` 和 `success:true`：

```json
{
  "pid": "2026-10-19_09-44-46.508_v3_download_file_local_王飞_7c203601",
  "download_path": "/g_web_installer/data/obs/local/slash-check/20261019/iam_4382_1006.tar"
}
```

WebSocket 日志接口握手返回 101，并显示不带前导 `/` 的实际 OBS key 及上述本地目标路径。初次文件列表尚未出现验证文件；继续订阅同一任务取得以下现场证据：

```text
[2026-10-19 09:47:46] [INFO] 下载到本地进度：累计 384.22 MiB / 总量 849.87 MiB
[2026-10-19 09:50:46] [INFO] 下载到本地进度：累计 661.31 MiB / 总量 849.87 MiB
[2026-10-19 09:51:32] [INFO] Downloaded 891151360 bytes to /g_web_installer/data/obs/local/slash-check/20261019/iam_4382_1006.tar
[2026-10-19 09:51:32] [SUCCESS] Operation completed successfully
```

随后 `GET /api/v3/obs/file/local/list` 返回 HTTP 200，并在正式文件数组中包含 `{"path":"slash-check/20261019/iam_4382_1006.tar"}`。由实际下载完成日志、字节数及正式文件列表共同确认：214 上两个字段均不带前导 `/` 的请求能够完成该 IAM 对象下载。验证文件保留在独立目录中；未重复触发同一下载，未保存认证值、未修改业务代码、未部署或重启服务，也未导入 Zot。

本次实际功能证据允许将案例元数据更新为 `verified`，仅覆盖本次 IAM 无前导斜杠下载路径；不代表已核验 214 部署提交、覆盖重下载、并发冲突、文件内容或校验和，以及 2026-10-16 KK 制品下载的最终结果。

## OBS-20 重复下载与覆盖边界（2026-10-19）

用户询问重复下载同一文件是否覆盖。本轮复核 `obs_v3_local_download.go`：覆盖由本地目标 `path` 决定，而不是仅由 OBS `real_path` 决定。相同 `path` 在旧任务结束后再次下载，先通过 `os.CreateTemp` 写入同目录临时文件，完成响应内容写入、已知长度校验并关闭文件后，再以 `os.Rename` 替换正式路径；失败时清理临时文件并保留此前成功下载的原文件。不会自动跳过已有文件，也不会自动生成新的正式文件名。

同一进程内相同本地目标正在下载或导入时，由共享 `obsLocalDownloadsV3` 拒绝重复任务，HTTP 返回 409。同一个 `real_path` 配合不同本地 `path` 则保存为多个文件。本轮路径验证使用独立的 `slash-check/20261019/` 目录，未请求替换上周的 IAM 文件。此覆盖结论来自当前本地源码，未额外在现场发起覆盖或并发冲突实验。

## OBS-20 下载期间本地列表的可见性（2026-10-19）

用户询问文件正在下载时目录是否返回。本轮复核当前 `obs_v3_local_list.go`：`GET /api/v3/obs/file/local/list` 返回递归查找的正式普通文件相对路径，不返回目录条目；路径字符串可以包含父目录层级。下载使用的 `.v3-download-*.part` 临时文件由前缀过滤规则排除，下载期间创建的父目录也不会单独返回。

- 首次下载且目标没有旧正式文件：下载期间不返回该目标；成功 rename 发布正式文件后，下一次列表请求可见该文件。
- 相同 `path` 已存在旧正式文件并重新下载：下载期间仍返回旧正式文件的相对路径，成功后由新文件替换；下载失败仍保留旧文件。
- 列表没有下载状态字段，也不检查正在下载或导入的目标锁，因此“出现在列表中”不等于同路径当前没有重下载任务，导入时仍可能返回 409。

2026-10-19 既有现场证据已观察到首次下载期间验证路径未出现在列表、完整下载后出现。旧正式文件重下载期间的可见性及目录过滤依据本轮源码复核，未另发覆盖下载或并发请求。案例整体已验证状态仍仅覆盖此前取得实际功能证据的 IAM 下载路径。

## OBS-20 来源

- 2026-10-19 214 下载接口 HTTP 响应、同任务 WebSocket 完成日志和本地文件列表响应（仅记录脱敏证据）。

- 2026-10-16 本轮真实 HTTP 请求结果及 SSH 认证结果（只记录脱敏结论）。
- `g_web_installer/internal/transport/router.go`、`internal/transport/handler/obs_v3_local_download.go`、`internal/transport/handler/obs_v3_middleware.go`。
- `g_web_installer/internal/model/request/obs.go`、`internal/service/file_server/obs_v3_local_download.go`、`internal/service/file_server/file_server_v3.go`。

[返回案例索引](../README.md)
