# OBS-24：V3版本链接改存OBS并按请求下载合并

项目：g_web_installer。记录与更新日期：2026-10-23。记录状态：开发验证通过，PR420已合并；121Web构建、替换及启动命令成功，真实OBS功能待验证。

适用环境：Web实现提交为 `release/8afe3ab0875bed68f1cdb51af8ab0a8042fc2101`，中央合并提交为 `96c8cf3715da8b34fa2af79622b06e6127dffb90`，已在121以宿主机后端进程方式执行发布命令。适用于通过Image Gateway操作OBS的V3接口，Kubernetes、OS和在线/离线安装模式不决定该协议。本轮没有调用真实OBS功能；V2历史实现不属于此次迁移范围。

## OBS-24 问题与表现

用户先询问 `POST /api/v3/obs/folder/create` 的逻辑及 `rev_url`、`opt_url` 保存位置，随后明确调整要求：两个URL的映射以OBS的 `/config/versionUrl.json` 为准。保存时先下载最新文件，增量合并后覆盖上传并删除临时文件；列表每次也下载读取，不依赖本地缓存。

原源码将映射长期保存在Web工作目录的 `data/obs/versionUrl.json`，列表读取同一本地文件，无法反映其他服务或用户对OBS配置的后续修改。这是本次已确认的实现差异，没有收到现场失败日志；最初关于本地文件的说明只适用于修改前版本。

## OBS-24 最终实现与已确认边界

### 远端文件和合并方式

唯一远端映射对象key为 `config/versionUrl.json`。用户描述中的前导 `/` 表示桶内路径，网关请求使用不带前导 `/` 的key。内容结构保留原有格式：

```json
{
  "产品/4.38.9/": ["https://example.com/review", "https://example.com/operation"],
  "其他产品/版本/": ["https://example.com/another-review"]
}
```

数组第一个元素为 `rev_url`，第二个为非空的 `opt_url`。保存时先GET远端最新JSON，将本次目录key对应的数组替换为新值，保留其余目录，然后以JSON和准确Content-Length整体PUT到相同远端key。网关客户端要求HTTP201及返回key、size一致才视为上传成功。

“增量合并”指保留其他目录记录；同一目录的数组仍按本次请求整体更新，未改为字段级补丁。传入新 `rev_url` 但省略 `opt_url` 会移除该目录原来的第二个URL。创建普通目录时仍仅在 `rev_url` 非空才保存映射；单独传 `opt_url` 不会保存。

### 每次下载与临时文件清理

`readVersionUrlsV3` 每次从OBS下载到操作系统临时目录的独立 `obs-v3-version-urls-*.json` 文件，使用0600默认权限，按16MiB上限读取并解析为映射。解析后关闭并删除临时文件；下载、大小校验或解析失败时也执行清理，关闭或删除失败会返回错误。

下载文件只在此次解析过程中存在。保存随后在内存合并映射并上传；列表读取解析结果填充返回值。两个流程均不再读取或写入固定的 `data/obs/versionUrl.json`，也不使用旧本地文件作为失败回退。历史文件不会被自动迁移或删除，保留它不影响新的V3读取来源。

下载、上传分别受现有metadata超时限制，源码默认30秒。远端404、401、403、下载截断、空文件、非法JSON、根值null或超过大小上限均直接报错；保存前读取失败不会执行覆盖上传。需要初始空映射时，应在OBS明确准备合法的 `{}` 文件，代码不会把读取失败转换为空映射后覆盖远端数据。

### 受影响入口

| 入口 | 修改后的行为 |
|---|---|
| `POST /api/v3/obs/folder/create` | 异步创建目录；有 `rev_url` 时下载、合并并上传远端映射 |
| `POST /api/v3/obs/folder/version/create` | 创建目录并上传版本文件后，下载、合并并上传远端映射 |
| `POST /api/v3/obs/folder/version/update` | 下载、合并并上传远端映射；要求当前V3网关登录会话 |
| `POST /api/v3/obs/folder/list` | 当前用户有可见权限时，每次重新下载映射，填回 `rev_url`、`opt_url` |

列表每次最多下载一次版本链接映射，不逐对象下载；没有可见权限时仍按原行为直接返回空列表。新配置文件本身从普通对象结果中排除，包括拥有 `all` 权限的列表。`pass.json` 等其他元数据逻辑保持各自现有实现，本轮只迁移版本链接映射。

2026-10-23再次核对列表实际顺序：先从OBS读取 `config/users.json` 权限，再读取现有审核元数据，下载 `config/versionUrl.json` 到本地临时文件并解析、删除，随后通过 `ListAll` 获取OBS对象列表。最后按权限与内部文件规则过滤，以完整对象key精确匹配映射，数组第一个元素组装为 `rev_url`、第二个组装为 `opt_url`，连同路径、大小、修改时间和审核标志返回。缺少映射时两个URL保持空字符串；下载或解析失败直接返回错误，不使用旧缓存。该流程已随本次Web代码在121执行发布命令，真实接口和OBS行为仍待功能验证。

鉴权仍经过JWT与Ops身份校验，IAM双token来自当前JWT绑定会话；编辑版本链接已从纯本地接口例外中移除，缺失或过期会话返回401。接口URL、请求及响应字段未改变，因此本轮未修改已有 `swag.json` 工作稿。

### 并发与失败边界

保存沿用进程内 `obsMetadataMuV3`，锁覆盖“读取远端最新值、合并、上传”全过程，防止同一Web进程的两个保存相互覆盖。该锁不协调其他Web实例或外部写入者，当前协议没有ETag条件写或跨实例锁；多个写入者同时修改远端文件仍可能产生最后写入覆盖。

普通目录创建仍返回异步PID和 `success:true`，只表示任务已启动。目录或版本文件已上传、随后映射保存失败时，任务报告失败，但之前写入的远端对象不会回滚。真实完成应以本次PID终态及远端对象、映射为准。

## OBS-24 可执行使用与确认步骤

1. 核对目标桶已存在 `config/versionUrl.json`，内容为合法JSON对象，且当前IAM身份可读取和覆盖该对象。新环境可按明确初始化操作准备 `{}`，不要用旧Web本地文件自动替代远端内容。
2. 使用有效V3登录JWT，按原接口请求创建或编辑链接，例如：

```json
{
  "path": "产品/4.38.9",
  "rev_url": "https://example.com/review",
  "opt_url": "https://example.com/operation"
}
```

3. 普通目录创建返回后，通过WebSocket订阅 `/api/v3/obs/logs/tail/<本次pid>`，或读取Web工作目录 `data/obs/history/<pid>/execute.log`。终态成功为 `Operation completed successfully`，失败为 `Operation failed: ...`；HTTP成功或WebSocket关闭不能替代终态。
4. 任务成功后检查OBS的 `config/versionUrl.json`：本次目录数组已更新，其他目录仍存在。再次调用目录列表核对链接。外部修改该远端映射后，下一次列表应读取新值，不需要重启服务或修改Web本地文件。
5. 下载、JSON解析或上传报错时按PID日志与远端响应排查对象路径、内容及IAM权限。远端目录已创建而映射失败时，处理映射问题后可通过版本链接更新接口重试；不要根据任务失败推断已创建对象被删除。

## OBS-24 手工目录改名后的历史映射修正（2026-10-23）

用户说明此前通过 `obsutil mv` 手动改过OBS一级目录。当前列表通过 `versions[key]` 精确匹配完整对象key，移动远端对象不会由Web自动更新JSON中的字符串；旧目录前缀因此需要同步修改，否则目录可能可见，但无法匹配原来保存的两个URL。当前Web的 `renameObsObjectV3` 只执行对象复制和删除，也没有联动更新版本链接映射。

用户提供的Windows下载文件最初复制为Web项目根目录的 `version.json`，后续按程序使用的名称统一更名为 `versionUrl.json`。文件共137条记录，所有key都以 `/` 结尾，没有重复key；93条含两个URL，44条含一个URL。这里只记录脱敏后的结构和处理结果，不复制原始URL或整份环境配置。

已按用户明确的对应关系，只替换key的一级目录前缀：

| 原一级目录 | 新一级目录 | 修改记录数 |
|---|---|---|
| 流程行业PLMPRO | 流程行业PLM2.0 | 8 |
| 报表看板平台 | 报表看板 | 1 |
| IndepthAi | IndepthAI | 10 |
| 数据采集 | 数采平台 | 7 |

共修正26条记录。后续版本路径、URL数组及文件其他文本均保留，总记录数仍为137。替换前检查目标key冲突，生成后验证JSON结构、记录数及每条URL值一致；前缀修正阶段仅修改本地配置文件，没有执行测试或构建。

用户进一步确认准确大小写为 `IndepthAi -> IndepthAI`，现有 `IndepthAI` 的1条记录属于改名后新增版本，需保留。已迁移旧前缀的10条，最终 `IndepthAI` 共11条，未发现相同版本路径的key冲突。后续补充 `数据采集 -> 数采平台`，迁移7条，与已有7条无key冲突，合并后该前缀共14条。上传OBS时目标key为 `config/versionUrl.json`。本轮尚未上传OBS，也未新增自动重命名映射功能。

用户随后明确要求将该文件发送到121的 `/root/wfkk/configyaml/`。通过固定别名 `codex-test-121` 创建目标目录，scp传输成功；用户确认文件名后，本地文件与121上的文件均由 `version.json` 改为 `versionUrl.json`。最终本地路径为 `g_web_installer/versionUrl.json`，121路径为 `/root/wfkk/configyaml/versionUrl.json`，文件35014字节。mkdir、scp及远端mv均退出0；这只证明目录准备、传输与改名命令成功，没有上传OBS或重启Web/KK，也没有把文件传输描述为业务功能验证。

## OBS-24 验证结果与遗留事项

- `CGO_ENABLED=0 go test -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./internal/service/file_server ./internal/transport/handler` 退出0，两包均通过。
- 相同包使用 `CGO_ENABLED=1 go test -race` 和上述tags通过，含8个并发保存保留所有目录的验证。
- 本地HTTP网关替身验证：编辑链接保留其他目录、再次保存保留外部新增记录；列表连续两次读取远端新内容并过滤配置对象；损坏旧本地文件被忽略；创建普通目录与创建版本目录都将映射上传到新key。
- 覆盖远端404/401/403/500、空文件、非法JSON、null、数组、尾随内容、超过16MiB及下载截断共11个读取失败场景；均未发生覆盖上传。另验证上传失败、列表读取失败、成功路径的临时文件清理，以及编辑入口缺失网关会话被拒绝。
- 使用项目tags、`CGO_ENABLED=0` 构建真实 `./cmd/server` 成功，临时构建产物160247670字节并已清理。测试源文件在验证通过后按约定删除，格式及差异检查通过。
- 开发测试仅调用本机HTTP替身，不证明真实IAM、Image Gateway、OBS权限或远端合并功能已通过。后续提交与发布进展见下一节；元数据保持 `unverified`。

## OBS-24 提交、合并与121Web发布结果（2026-10-23）

用户明确要求提交代码并仅发布Web到121，KK不发布。本次Web提交为 `8afe3ab0875bed68f1cdb51af8ab0a8042fc2101`，标题 `fix(obs): store version URL mappings in OBS`，涉及版本链接读写、中间件、Git忽略规则及停止跟踪 `swag.json`，共5个文件。`git commit` 和 `git push origin release` 均成功；两个本地JSON文件继续保留，不进入代码提交，andrew案例文档未提交。

用户明确授权创建并合并PR后，创建并正常合并 [PR420](http://192.168.3.34/Installation-package/g_web_installer/pulls/420)，目标为中央 `release`，源为 `wangfei:release`。合并前核对仅含本次1个提交和5个文件。Gitea返回 `merged=true`，合并提交为 `96c8cf3715da8b34fa2af79622b06e6127dffb90`；fetch中央分支后确认其包含 `8afe3ab`。本次没有CI状态记录，不能将此前本地验证描述为CI通过。

121通过固定别名 `ssh codex-test-121` 发布Web，目录 `/root/wfweb/g_web_installer` 从 `release/6a674f4` 使用 `git pull --ff-only origin release` 快进到 `96c8cf3`，HEAD与 `origin/release` 一致并确认包含实现提交。保留 `configs/users.json`、持久化 `data` 及禁用Vue import和 `vue.ServeVue` 的后端 `router.go` 本地修改。

发布命令及直接结果：

1. 使用登录Shell执行 `CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o server.next ./cmd/server`，成功后 `mv -f server.next server`；整体退出0，输出构建及二进制替换完成。
2. 二进制准备完成后，通过一次 `ss` 查询8080监听PID，并只核对一次进程归属：旧PID为2649702，cwd为 `/root/wfweb/g_web_installer`，exe为该目录的 `server (deleted)`，符合刚替换二进制的目标Web进程。
3. 对该旧PID执行SIGKILL后立即运行 `/root/wfweb/web_start.sh`。启动脚本输出 `server started, pid=2832810`，退出0。

本次只发布Web，没有构建、复制或发布KK；案例文档仅本地更新。发布阶段复用开发验证，没有重复测试，也没有追加启动后接口、日志、端口或多轮进程检查。构建、替换和启动命令成功不证明真实OBS列表、URL合并上传或IAM权限已通过；JSON配置先前只传到121的 `/root/wfkk/configyaml/versionUrl.json`，本轮没有执行OBS上传，元数据继续保持 `unverified`。

## OBS-24 来源定位

- `g_web_installer/internal/service/file_server/obs_v3_version_urls.go:13`、`:19`、`:65`：新对象key、按次下载与清理、增量合并上传。
- `g_web_installer/internal/service/file_server/file_server_v3.go:163`、`:179`、`:207`、`:239`、`:266`、`:301`：列表读取及配置过滤、创建普通/版本目录、编辑链接入口。
- `g_web_installer/internal/transport/handler/obs_v3_middleware.go:35`：编辑入口要求网关会话。
- `g_web_installer/internal/service/image_gateway/client.go:269`、`:317`；`internal/config/image_gateway.go:9`：PUT校验、GET及默认超时。
- `g_web_installer/internal/transport/router.go:182`；`internal/model/request/obs.go:7`；`internal/service/file_server/obs_executor.go:44`、`:95`：原有V3路由、参数和异步完成边界。
- 开发验证命令的直接结果及本地HTTP替身断言；临时测试已删除。
- `g_web_installer/versionUrl.json` 的结构统计与前缀替换校验；用户提供的旧目录与新目录对应关系；`internal/service/file_server/file_server_v3.go:227`、`:393` 的精确映射读取与对象重命名实现。
- `ssh codex-test-121 'mkdir -p /root/wfkk/configyaml'`、scp至该目录及远端 `mv .../version.json .../versionUrl.json` 的退出状态；本地文件更名后的路径和大小。
- PR420的提交、文件范围、合并API直接结果及中央Git祖先关系；121登录Shell的ff-only拉取、构建替换、单次8080归属检查和启动脚本直接输出。

[返回案例索引](../README.md)
