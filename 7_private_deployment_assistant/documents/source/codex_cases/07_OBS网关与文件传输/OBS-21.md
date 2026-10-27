# OBS-21：214本地IAM镜像归档导入Zot的功能验证

项目：g_web_installer。记录日期：2026-10-16。记录状态：现场功能验证（单个 IAM 包导入、目标 manifest 可读、源包保留）。

适用环境：214 Web `http://10.40.46.214:8080`，用户说明部署的是 test 分支；本轮未通过 SSH 独立核验实际运行提交。目标为接口固定的 `digiwin.gkubeinstaller.local:444` Zot。与 [OBS-20](OBS-20.md) 的 IAM 包下载记录衔接。

## OBS-21 问题与验证目标

用户要求使用已下载到 Web 本地的 `中间件/4.38.2/IAM/iam_4382_1006.tar`，调用 `ImportLocalImagesV3` 验证真实导入。验证目标为任务成功结束、目标仓库存在对应镜像 manifest，以及本地源包保留，不能只依据接口返回 `success:true` 判断完成。

## OBS-21 请求与现场证据

先调用 `GET /api/v3/obs/file/local/list`，HTTP 200 的正式文件列表包含：

```json
{"path":"中间件/4.38.2/IAM/iam_4382_1006.tar"}
```

随后调用 `POST /api/v3/registry/images/import`，请求体必须是数组：

```json
[
  {"path":"中间件/4.38.2/IAM/iam_4382_1006.tar"}
]
```

接口返回 HTTP 200、`code:10000`、`msg:OK`：

```json
{
  "success": true,
  "pid": "2026-10-16_13-02-49.883_v3_registry_import_王飞_1a253926"
}
```

通过同一 PID 的 WebSocket 日志取得实际执行证据：

```text
[2026-10-16 13:02:49] [INFO] Found 1 image tag(s) in docker archive iam_4382_1006.tar
[2026-10-16 13:02:49] [INFO] Copying image registry.digiwincloud.com/middleware/iam:4.38.2.1006 -> digiwin.gkubeinstaller.local:444/middleware/iam:4.38.2.1006
[2026-10-16 13:03:15] [INFO] Package imported successfully: /g_web_installer/data/obs/local/中间件/4.38.2/IAM/iam_4382_1006.tar
[2026-10-16 13:03:15] [INFO] Package import summary: total=1 success=1 failed=0
[2026-10-16 13:03:15] [SUCCESS] Operation completed successfully
```

导入期间一次 manifest HEAD 返回 404；任务成功后再次请求返回 HTTP/2 200，不能把导入完成前的 404 当作最终失败。

任务成功后的独立仓库检查使用 HTTPS、关闭本次客户端证书校验，并将目标主机名显式解析到 214 地址；这不表示已核验 Web 进程自己的 DNS/hosts 配置：

```bash
curl --noproxy '*' --connect-timeout 5 --max-time 15 \
  --resolve digiwin.gkubeinstaller.local:444:10.40.46.214 -k -sS -I \
  -H 'Accept: application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json' \
  https://digiwin.gkubeinstaller.local:444/v2/middleware/iam/manifests/4.38.2.1006
```

实际结果：

```text
HTTP/2 200
content-type: application/vnd.docker.distribution.manifest.v2+json
docker-content-digest: sha256:9ce2ab9963579eb659e2bfdfe8610d9b9b055d7ba7b21746ab6cffd34a312490
content-length: 2861
```

此 HEAD 请求没有携带认证值。导入完成后再次调用本地列表，IAM 源路径仍在，确认本地正式源文件保留。

## OBS-21 最终定位与源码边界

- `internal/transport/router.go` 将 `/api/v3/registry/images/import` 映射到 `handler.ImportLocalImagesV3`；handler 绑定 `[]request.ImportLocalImagesV3Request`。
- `internal/service/file_server/obs_v3_local_import.go` 在启动任务前校验本地相对路径并与下载共用占用锁，然后异步导入固定 Zot。纯本地导入不依赖 OBS 网关，但仍需要有效 Web 登录身份。
- `internal/common/registry.go` 读取 Docker-save 归档中的标签，以 `containers/image` 复制镜像并替换源 registry，保留 `middleware/iam:4.38.2.1006` 路径及标签。
- `Package import summary` 和执行器成功终态属于真实导入证据；额外的 manifest HTTP 200 证实目标端可读取该标签。原文件在导入后继续列出，与源码只关闭句柄、清理临时产物的行为一致。

### 为什么镜像路径保留 middleware

用户随后询问为何“项目”是 `middleware`。本次日志中的源镜像为 `registry.digiwincloud.com/middleware/iam:4.38.2.1006`。`dockerArchiveTags` 从包内 `manifest.json` 的 `RepoTags` 读取标签；`rewriteImageToRegistry` 调用 `stripSourceRegistry` 仅去除源 registry，保留 `middleware/iam:4.38.2.1006`，再拼接固定目标 registry。因此 `middleware` 来自包内原始镜像引用，不由本地 `中间件/4.38.2/IAM/` 文件夹或 tar 文件名推导。

当前目标为 Zot，`middleware/iam` 是仓库路径，其中 `middleware` 为路径前缀；导入逻辑只在目标类型是 Harbor 时调用项目创建 API，Zot 分支不会创建 Harbor 项目。接口输入只有本地 `path`，不支持通过该字段指定目标项目名。相关实现为 `internal/common/registry.go` 的 `dockerArchiveTags`、`rewriteImageToRegistry`、`stripSourceRegistry`，以及 `pushSingleDockerArchiveToRegistry` 的 Harbor 条件分支。本轮只解释已有命名行为，未改名或重新导入镜像。

### Zot 自动形成仓库与 Harbor 预建项目的区别

用户继续确认：Zot 没有 `middleware` 项目时是否自动创建，以及 Harbor 是否必须预建仓库。这里需区分项目（Project）与镜像仓库（Repository）：

- Zot 不需要先创建 Harbor 式项目；首次成功推送 `middleware/iam:4.38.2.1006` 时，自动形成 `middleware/iam` 仓库及相应标签。`middleware` 只是该仓库名的路径前缀，不是另行创建的项目对象。推送仍需满足配置的创建/写入权限、配额等条件。
- Harbor 要先存在 `middleware` 项目，推送用户需具备该项目的推送权限；项目内的 `iam` 镜像仓库通常由首次推送自动形成，不需要预先手工创建 `iam` 仓库。因此“Harbor 推送前必须创建仓库”更准确的说法是“先创建项目”。
- 本项目 `internal/common/registry.go` 的 `pushSingleDockerArchiveToRegistry` 只在 `registryType == "harbor"` 时调用 `ensureHarborProjectWithOptions`：先 GET 查询项目，再在需要时 POST 创建项目，前提是使用的账号拥有相应权限。Zot 跳过该步骤，直接复制镜像。这是已有源码行为，并非本轮新增功能。

本次 IAM 导入成功、目标 manifest 可读的证据说明无需本轮额外执行 Zot 项目创建；但本轮没有事先取得整个 `middleware` 路径不存在的证据，不能把这次操作描述为已证明“214 首次创建 middleware”。此处对首次推送建仓行为的说明依据官方文档，不混同于新增现场测试。

官方依据：[Zot 推送与拉取](https://zotregistry.dev/user-guides/user-guide-datapath/)、[Zot 仓库数量限制说明](https://zotregistry.dev/v2.1.21/general/whats-new/)（明确区分创建新仓库的推送与已有仓库推送）、[Zot 按仓库路径配置权限](https://zotregistry.dev/v2.1.16/admin-guide/admin-configuration/)、[Harbor 推送镜像及镜像名结构](https://goharbor.io/docs/main/working-with-projects/working-with-images/pulling-pushing-images/)。本轮没有新建、删除项目或重复导入。

## OBS-21 可执行操作步骤

1. 在 214 完成 V3 登录，确认本地正式文件列表中已有目标包；下载未完成或目标正被占用时不要反复触发导入。
2. 用上面的数组请求调用导入接口，请求头为 `Authorization: Bearer <当前有效Token>` 和 `Content-Type: application/json`。认证值只在运行时使用，不写入文档或脚本。
3. 根据返回 PID 打开日志页面，等待汇总和成功/失败终态。当前任务入口为：

```text
http://10.40.46.214:8080/#/obs/logs/tail/2026-10-16_13-02-49.883_v3_registry_import_%E7%8E%8B%E9%A3%9E_1a253926
```

4. 终态成功后核对目标镜像 manifest，并再次列举本地文件，确认源包保留。

## OBS-21 验证结果与遗留事项

本次验证通过：单个 IAM Docker-save 包、一个镜像标签成功导入 Zot；仓库 manifest HEAD 返回 200 并取得 digest；本地源包保留。元数据 `verified` 仅覆盖这条真实导入路径，不代表多包导入、全部归档格式、完整镜像拉取、容器运行或 IAM 应用业务均已验证。

没有修改业务代码、部署、重启、删除源包或重复触发下载。未核验此前 KK 制品下载任务的终态。

### 214 手动拉取工具核验边界（2026-10-16）

用户随后询问 214 实际已有的镜像拉取工具。首次执行 `ssh -o BatchMode=yes -o ConnectTimeout=10 codex-test-214`，计划只用 `command -v` 检查 `docker`、`ctr`、`nerdctl`、`crictl`、`containerd`；连接在执行远端命令之前返回 `Permission denied (publickey,password)`，退出码 255。当时工具清单未确认，此前给出的 Docker/containerd 拉取命令只是适用工具存在时的用法，不能作为 214 已安装这些命令的证据。

可由已有终端会话在 214 执行 `command -v docker ctr nerdctl crictl containerd` 获取当前 PATH 下可用工具的位置；PATH 中不存在也不能完全排除其他目录有二进制。Web 本次导入使用 Go 镜像库，成功导入本身不证明宿主机存在 Docker 或 ctr。此边界不改变上文已经确认的 API 导入及 manifest 验证结果。

用户随后提供 214 终端实际输出，补充确认以下工具可用：

```text
/usr/bin/ctr
/usr/bin/nerdctl
/usr/bin/crictl
/usr/bin/containerd
```

本次 `command -v docker ctr nerdctl crictl containerd` 未输出 Docker 路径，结论仅为当前 PATH 中未找到 Docker。依据用户提供的现场输出，推荐使用现有 ctr 拉取到 Kubernetes 使用的 `k8s.io` namespace：

```bash
ctr -n k8s.io images pull --skip-verify digiwin.gkubeinstaller.local:444/middleware/iam:4.38.2.1006
```

`--skip-verify` 跳过本次拉取的 HTTPS 证书校验。该手动拉取命令尚未取得实际执行结果，不能把工具路径确认或此前导入成功写成镜像已拉取完成；现有工具版本及 containerd 服务健康未在此步骤验证。

## OBS-21 再次调用并返回原始响应（2026-10-16）

用户要求再次验证接口并提供返回响应。本轮按同一 `ImportLocalImagesV3` 接口，在 214 重新导入同一个 IAM 本地包；这是用户明确要求的第二次调用，与上文首次导入验证分开记录。

```text
POST http://10.40.46.214:8080/api/v3/registry/images/import
HTTP 200
```

请求体：

```json
[{"path":"中间件/4.38.2/IAM/iam_4382_1006.tar"}]
```

实际响应（仅调整缩进）：

```json
{
  "code": 10000,
  "msg": "OK",
  "data": {
    "success": true,
    "pid": "2026-10-16_13-17-51.351_v3_registry_import_王飞_234989f3"
  }
}
```

该返回表示第二次异步任务已创建；本轮未订阅第二次任务的终态，不能用首次任务成功代替第二次完成证据。第二次日志页面为：

```text
http://10.40.46.214:8080/#/obs/logs/tail/2026-10-16_13-17-51.351_v3_registry_import_%E7%8E%8B%E9%A3%9E_234989f3
```

本轮没有修改代码或部署，也没有访问 Harbor 创建项目接口；使用的是固定目标为 Zot 的本地导入接口。

## OBS-21 本地列表实际响应及后台下载展示规则（2026-10-16）

用户要求取得 `ListObsLocalFilesV3` 实际响应，并确认其他后台下载任务如何展示。本轮真实调用 `GET http://10.40.46.214:8080/api/v3/obs/file/local/list`，HTTP 200，响应为：

```json
{
  "code": 10000,
  "msg": "OK",
  "data": [
    {"path": "kk/g_kube_installer-artifact.tar.gz"},
    {"path": "中间件/4.38.2/IAM/iam_4382_1006.tar"}
  ]
}
```

源码核对 `internal/service/file_server/obs_v3_local_list.go`、`obs_v3_local_download.go` 及 `internal/model/reply/obs.go` 后确认：

- 列表递归返回本地正式普通文件的相对 `path`，按路径排序；当前模型没有状态、任务 PID、进度或文件大小字段。
- 下载新文件时，内容先写入 `.v3-download-*.part`，列表跳过这些临时文件，因此下载中的新文件不会占一条记录。完整写入、长度检查和关闭后成功 rename 为正式路径，后续列表才能显示该文件。
- 如果同一路径已有旧正式文件，重新下载时旧文件不会先删除，列表仍显示原来的路径；新下载成功后原子替换正式文件。仅看这一条路径无法分辨正在重新下载或已更新。该路径被下载/导入任务占用时，即使旧文件在列表中，导入的占用检查仍可能返回 HTTP 409。
- 下载失败时临时文件清理，已有旧正式文件保留；失败的新文件没有正式记录。空列表只说明没有可列出的正式文件，不能证明没有后台任务。
- `.v3-import-*` 临时产物、`docker_archive_bundle_*` 临时目录、符号链接和特殊文件也会被跳过。

后台下载进度和成功/失败结果需依据发起请求返回的 PID，通过 WebSocket 日志 `/api/v3/obs/logs/tail/<pid>` 查看。当前 GET 响应本身不能判定现场是否还有其他下载任务。本轮未额外创建下载任务或修改接口；并发下载展示规则属于已核对源码结论，不冒充本轮新增并发现场测试。

## OBS-21 来源

- 2026-10-16 本轮 214 本地列表、真实导入 POST、WebSocket 任务日志及目标 manifest HEAD 结果。
- `g_web_installer/internal/transport/router.go`、`internal/transport/handler/obs_v3_local_import.go`、`internal/model/request/obs.go`。
- `g_web_installer/internal/service/file_server/obs_v3_local_import.go`、`internal/service/file_server/obs_executor.go`、`internal/common/registry.go`。

[返回案例索引](../README.md)
