# OBS-25 private-service版本输出同步OBS链接与目录key格式

记录日期：2026-10-23。适用环境：`private-service` 本地 `dev`，开发基线 `455e586d463622a0fe040310b60efbf49def6da6`，Go 1.25.0；同步调用现有OBS网关，安装模式不限。本轮仅本地实现和验证，未提交、推送或发布private-service，未调用真实OBS。

## OBS-25 问题表现

`POST /api/v1/privatization/version/output` 原先在版本输出时创建OBS目录，但请求没有操作链接、审核链接字段，目录创建后不会写入已迁移到OBS的 `config/versionUrl.json`。Web列表按完整对象key读取链接，private-service新增目录需要同步维护同一映射。

用户补充指出，JSON的目录key以 `/` 结尾，而业务层 `folderPath` 没有末尾 `/`，必须同时核对开头和结尾。复核用户提供的本地配置只统计结构，不记录URL：137个key均无前导 `/`、均有一个末尾 `/`，没有末尾双斜杠。

## OBS-25 最终定位与源码证据

- 服务层原有 `folderPath` 为 `<部门名称>/<UnixMilli>-<请求version>-noisrev`；`CreateOBSFolder` 在发往网关前已经去掉前导 `/` 并补上末尾 `/`。直接拿未经处理的 `folderPath` 写JSON会与实际目录key不一致。
- Web版本链接数组约定为 `[rev_url, opt_url]`，其中第一个是审核链接、第二个是操作链接。映射对象key是 `config/versionUrl.json`，不含前导 `/`。
- 版本、应用、依赖写入与目录回调位于同一个GORM事务。扩展现有回调即可在创建目录后同步链接，无需再次生成时间戳或拼出另一条目录路径。

## OBS-25 已实现方案

1. `request.OutputAppVersion` 增加Go字段 `OptUrl`、`RevUrl`，JSON和表单参数分别为 `opt_url`、`rev_url`。两者可选；都为空时保持原有版本输出及建目录流程，不读写链接映射。
2. 服务层先执行 `CreateOBSFolder(ctx, folderPath)`，成功后把同一个 `folderPath` 交给 `SyncOBSVersionURLs`。
3. 目录创建和映射保存共用 `normalizeOBSFolderKey`，去掉前导 `/`，末尾统一保留一个 `/`，保持原有非法字符及 `.`、`..` 路径段校验。例如 `/部门/时间戳-4.38.9-noisrev///` 对应实际目录和JSON key均为 `部门/时间戳-4.38.9-noisrev/`。
4. 任一URL非空时，通过现有网关 `GET /api/v1/objects/content`，使用现有bucket、`key=config/versionUrl.json` 和 `download=1` 读取远端最新JSON。认证沿用现有app凭据与请求头用户凭据，不保存或展示凭据值。
5. 每次在本次请求内存中解析最新映射，保留其他目录，仅写入本次目录的数组，然后PUT覆盖同一对象。不读写固定本地缓存或创建持久文件。
6. 两个链接都有值时写 `[rev_url, opt_url]`；只有审核链接时写 `[rev_url]`；只有操作链接时写 `["", opt_url]`，保留数组下标语义。同一key按本次请求整体更新数组，不是字段级补丁。
7. 下载要求HTTP 200，上传要求HTTP 201，并校验上传响应key与字节数。读取、解析、大小校验失败时直接返回错误，不会拿空映射覆盖远端。响应读取限制为16MiB，元数据读写沿用60秒同步超时，禁止自动重定向。
8. 进程内互斥锁覆盖读取、合并和上传，防止同一private-service进程内并发请求相互覆盖。新增请求字段、接口注释及现有三份Swagger产物同步更新。

## OBS-25 可执行使用与确认步骤

1. 确认OBS已有合法的 `config/versionUrl.json`，当前IAM身份具有读取和覆盖权限。需要初始化时，应明确准备 `{}`，不要把404、权限失败或非法JSON当成空文件。
2. 在原有合法版本输出请求中增加以下字段，其他必填参数及认证沿用原接口：

```json
{
  "rev_url": "https://example.com/review",
  "opt_url": "https://example.com/operation"
}
```

3. 完整请求成功后，核对实际创建的OBS目录key与远端JSON key逐字一致：无前导 `/`，有且仅有一个末尾 `/`。数组顺序为审核链接、操作链接；其他目录记录应保留。
4. 通过已有Web目录列表核对返回的两个URL。该步骤需要真实部署后的接口与OBS证据，本轮尚未执行。
5. 同步失败时按具体HTTP状态、配置JSON格式及IAM权限处理。不要从数据库回滚推断远端目录已经删除；确认远端状态后再决定修正或重试。

## OBS-25 验证结果与边界

- `CGO_ENABLED=0 go test ./internal/app/pkg/util ./internal/app/service/privatization ./internal/app/repository/privatization ./internal/app/transport/http/handler/privatization` 退出0。
- `CGO_ENABLED=1 go test -race ./internal/app/pkg/util ./internal/app/service/privatization` 退出0，覆盖同一进程8个并发保存保留全部目录。
- 本地HTTP传输替身验证：实际建目录PUT的key与JSON新增key完全一致；前导、末尾斜杠归一；连续保存重新读取并保留外部新增记录；JSON与表单绑定；两字段缺省及单字段场景；建目录、下载、上传失败的调用顺序。
- 11类读取失败场景均未上传，包括404、401、403、503、重定向、空响应、损坏JSON、null、数组、尾随内容及超过16MiB。另覆盖8类上传状态、JSON响应和key/size不一致场景。
- `CGO_ENABLED=0 go test ./internal/app/transport/http/api/docs` 退出0，校验运行时Swagger模板能解析、新接口及可选URL字段存在。JSON/YAML语义一致，原有12条路径和定义保留，新增该接口后共13条路径、增加4个定义。
- 全量Swagger生成遇到既有注释引用不存在的 `response.Response`，本轮没有扩大修改范围；仅按新增标签生成本接口并合并进既有三份产物。以上局部产物验证通过不表示全量生成器已修复。
- 使用 `make build APP_BIN_PATH=<临时目录>/app` 完成项目真实构建；最终产物105271409字节，已随临时目录清理。测试源码按用户约定在通过后删除，`gofmt -d` 与 `git diff --check` 无输出。
- 同步回调返回错误会回滚本次数据库事务；OBS目录或配置一旦写入，不会随SQL回滚。上传响应丢失、上传后事务提交失败等情况仍可能留下远端对象，需要按实际状态处理。
- 进程锁不协调其他private-service实例、Web或外部写入者。现有协议没有ETag条件写，多进程同时修改仍存在最后写入覆盖风险。
- 本轮没有真实OBS、数据库事务故障注入或Web联调功能证据，未提交或发布private-service；案例元数据保持 `unverified`。前一轮Web发布独立记录于[OBS-24](OBS-24.md)，不能作为本接口已发布或功能通过的证据。

## OBS-25 来源定位

- `private-service/internal/app/model/request/request.go:250`：请求字段及JSON、表单命名。
- `private-service/internal/app/service/privatization/service.go:2897`：复用现有 `folderPath`，依次建目录和同步映射。
- `private-service/internal/app/pkg/util/obs.go:99`：共享目录key规范化；同文件 `CreateOBSFolder` 为实际目录PUT入口。
- `private-service/internal/app/pkg/util/obs_version_urls.go:20`、`:27`、`:86`：对象key、读取合并上传与网关请求校验。
- `private-service/internal/app/repository/privatization/repository.go:2179`、`:2291`：版本输出事务及提交前回调。
- `private-service/internal/app/transport/http/handler/privatization/http.go:992` 及 `internal/app/transport/http/api/docs/`：接口注释与三份产物。
- `g_web_installer/internal/service/file_server/obs_v3_version_urls.go`、`file_server_v3.go`：远端映射来源和列表数组顺序。
- 本地结构统计、HTTP替身断言、测试、race、构建、格式和差异检查的直接结果；不保留临时测试源码、真实URL配置或认证值。

[返回案例索引](../README.md)
