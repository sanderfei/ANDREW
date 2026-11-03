# OBS-28：V3版本目录一键下载并导入集群数据与镜像的串行任务

项目：g_web_installer。记录日期：2026-10-26；更新日期：2026-10-29。记录状态：镜像优先按组件执行PR428已合并；121编译替换启动成功，业务未验证。

适用环境：Web 本地 `release`，初始基线为 `5f148d0`；2026-10-28 复查修复后提交 `65b61e3` 并推送 `origin/release`。代码已通过 PR424 合入中央 `release`，合并提交为 `1ed3b02d10a2eb3bab4d66553bf9f298fcd41ab4`；121 Web 已按该提交完成编译、二进制替换及启动命令，真实版本导入待验证。已完成本地源码、模拟链路及部分真实库的离线解析/归档读取验证，没有调用真实 OBS、离线 Zot 或数据库。路径相对于 Web 服务工作目录；宿主机与容器部署需按实际挂载核对，数据库组件、工具和连接参数仍须匹配现场。未修改前端实现。随后新增“仅处理审核通过包”的过滤，定向验证后提交 `39f55cd` 并经PR425合并为 `07f2566bbc7b5a35ae47295ac64fc97678e87a43`；121现已按该合并提交完成Web编译、替换及启动命令，真实审核下载导入仍待验证。随后将锁粒度细分为目标cluster加规范化完整版本prefix，提交 `9e5b1e8` 并经PR426合并为 `69cf625d82e31c01c163be1e59f8be9cb7a01e98`，121已完成该版编译、替换及启动命令；不同path可并行为源码/开发测试结论，未做真实并发导入验证。后续Web出口CN/TW签名选路经定向/race/构建后提交 `934701b`，通过PR427合并为 `bc6cd1a200ec92dd23643f7a270340d45a9aa6d9` 并完成121Web编译替换及启动命令；214未更新，真实出口GeoIP及4GiB级CDN下载仍未验证。

## OBS-28 问题与最终选择

用户希望在 OBS V3 的版本目录增加“导入到集群”能力：选择已有集群后，把版本直属文件中的镜像包、数据包下载到该集群目录，自动完成镜像入离线仓库和数据导入。XLSX、PDF 等资料跳过，缺某类包就不执行该类导入。

曾讨论并行业务、子日志落盘后按编号归并的备选；用户认为复杂，明确放弃。最终实现采用一个总 PID、一个 `execute.log`，内部全部顺序串行，没有新增 `progress.log`、`tasks/` 子日志或归并器。外层后台异步受理与内部顺序执行分别处理。

相关已有案例为 [OBS-22：本地镜像导入迁移 V1 并按集群归档任务日志](OBS-22.md) 和 [WEB-17：PID WebSocket 结束通知与自动衔接](../05_Web配置鉴权与任务/WEB-17.md)。本次新增后端版本任务，不把旧接口或历史现场证据视为本功能已上线。

## OBS-28 接口、权限与受理边界

已增加路由、handler、request/reply 及错误映射，并随 PR424 发布到121后端；尚未执行真实版本导入验证：

```http
POST /api/v3/obs/folder/version/import
Content-Type: application/json
```

```json
{
  "path": "安装包仓库/知识智能/1.6.7/",
  "cluster": "cluster-a"
}
```

`path` 是完整 OBS 版本目录前缀，规范为一个末尾 `/`；`cluster` 必须是已有真实 `config.yaml` 的单级集群名，拒绝斜杠、冒号、控制字符等非法名称。不接受任意本地目标路径、数据库账号或目标仓库覆盖参数。复用有效 Web JWT、Ops 身份及 V3 IAM 会话，实时读取当前用户 OBS 目录权限，按 `all` 或匹配的顶层目录授权；普通目录授权不扩展到 `config/`。

受理成功沿用标准 `code/msg/data`：

```json
{"code":10000,"msg":"OK","data":{"success":true,"pid":"<本次总任务PID>"}}
```

`success: true` 只表示后台任务已受理，不代表下载或导入完成。同步坏参数为 400，目录无权限为 403，集群不存在为 404，同cluster加同规范化完整版本path的重复任务为409；JWT/IAM 会话错误沿用 V3 认证规则，返回受理结果前的同步元数据超时可映射 504。扫描歧义、下载或导入失败可能发生在受理后，只在该 PID 日志报告，不会追改已经返回的 HTTP 状态。

## OBS-28 文件识别与串行流程

后端使用 `ListAll(prefix)` 完整分页，随后只保留前缀内的直属文件，排除目录标记、子目录及相邻版本。后续新增审核门槛：先以完整 OBS object key 精确匹配现有 `pass.json` 审核记录的一次快照，只让已审核文件进入后续分类；该门槛已随PR425发布到121，真实业务待验证。通过审核的可处理文件按文件名稳定排序，再检查去掉完整压缩扩展名后的末尾 `_数据库标识`，大小写不敏感，不以任意子串猜测类型：

| 数据标识 | 内部类型 | 现有压缩格式 |
|---|---|---|
| `Mysql`、`MariaDB` | `mysql`、`mariadb` | `.zip` |
| `PostgreSQL` | `postgresql` | `.zip` |
| `MongoDB` | `mongodb` | `.tar.gz` |
| `Elastic`、`ElasticSearch` | `elastic` | `.tar.gz` |
| `StarRocks` | `starrocks` | `.tar.gz` |

例如 `1.6.7_ElasticSearch.tar.gz`、`1.6.7_MongoDB.tar.gz`、`1.6.7_Mysql.zip` 分别进入对应数据导入。命中数据库后缀但压缩格式不符、同一数据库出现多个数据包时停止并报告错误，不推断分片或覆盖顺序。未命中数据库的 `.tar`、`.tar.gz`、`.tgz` 仅为镜像候选，仍须通过内容预检；未识别 ZIP、XLSX、PDF 等文件跳过且不下载。

识别细节（2026-10-26 只读澄清）：`classifyObsVersionPackage` 先限制扩展名为 `.zip`、`.tar.gz`、`.tgz`、`.tar`，其中 `.tar.gz` 作为完整后缀去除；随后仅取剩余文件名最后一个下划线后的 token，忽略大小写匹配表中数据库，前面的版本号、日期不参与分类。数据库标识必须位于去压缩扩展名后的末尾，例如 `v_Mysql_backup.zip` 的末尾 token 是 `backup`，因此作为未知 ZIP 跳过；`v_Mysql.tar.gz` 则已命中数据库但扩展不符，报告错误。未知 tar/tar.gz/tgz 只是镜像候选，若内容不是受支持的 Docker-save 或 bundle，预检失败并停止，不能扫描包内 SQL/BSON 来猜数据库类型。本次仅解释当前规则，没有修改业务代码或重新运行测试。

```text
[1/3 扫描] 直属文件 → 审核过滤 → 分类计划
[2/3 镜像] 检查离线仓库；不可用则日志跳过镜像下载
  → 可用时每包：下载 → prepare → 同步import → cleanup
[3/3 数据] mysql → mongodb → mariadb → elastic → postgresql → starrocks
  → 对有包组件先检查配置/Helm/健康；不可用日志跳过并继续
  → 合格组件：下载 → prepare → Run → cleanup
汇总及一次总终态
```

以上新策略已通过PR428发布121，真实新流程导入待验证，覆盖旧全量预检屏障。任务仍单PID串行，但镜像逐包导入完成后才处理下一包，再按binding顺序处理数据；缺仓库/组件配置或健康异常日志跳过，不阻断其他合格目标。真实下载、包格式、导入或清理错误仍停止后续，已完成副作用保留；父context取消优先中止。全部跳过时不做GeoIP、不创建obs-import下载/工作目录，但PID/history的execute.log正常存在，不能把完成日志称为所有包均已导入。

目录按集群与本次 PID 隔离：

```text
data/cluster/<cluster>/obs-import/<PID>/packages/<原文件名>
data/cluster/<cluster>/obs-import/<PID>/work/
data/cluster/<cluster>/history/<PID>/execute.log
```

下载原包仍保留在packages，不覆盖集群根目录旧固定包名。每个镜像只prepare一次，立即同步导入并清理展开tar；数据按组件prepare/Run/cleanup，逐包及最终清work。cleanup只清工作产物，不自动删除history或原压缩包；历史任务/下载的删除需单独明确授权。移除了二次镜像prepare及全版写入屏障，原包、数据库副本和内层bundle仍需空间，并行任务分别计量。

镜像目标沿用当前本地镜像导入的固定 444 端口离线 Zot，认证由后端提供；`cluster` 决定数据目标、下载目录和日志归属，不自动改用该集群的其他仓库。它与 `apps/:cluster/images/push` 的应用镜像流程分别处理。本功能没有新增 NFS 前置条件。

## OBS-28 PID、取消、互斥与导入核心

只有最外层调用一次 `ExecuteAsync`，总 PID 增加随机尾；内部下载、镜像和数据核心均同步等待，不调用会返回另一个 PID 的高层异步 API，也不解析日志猜成功后启动下一步。日志通过现有 WebSocket 实时读取：

```text
GET /api/v1/logs/cluster/<cluster>/tail/<pid>/execute.log
```

阶段、文件名、单包完成、汇总与唯一总成功/失败写入同一文件。HTTP 请求结束或浏览器关闭不取消后台流程，后台 context 脱离请求取消并使用总异步超时，每个文件另有传输超时。WebSocket 重连和日志回放只用于展示，不负责重复触发业务。

当前锁身份为目标cluster加规范化完整OBS版本prefix（包含部门/产品/版本，保留大小写），在clusterDir下使用 `.obs-version-import-<SHA256(prefix)>.lock`，摘要为全64位十六进制，继续采用非阻塞跨进程 `flock`。只有同cluster加同规范化完整path的重复任务返回409，不同部门、产品或版本path可各自执行；单个任务内部仍串行、一个PID一个日志。此增强已通过PR426发布到121；PR425的旧 `.obs-version-import.lock` 及cluster整体互斥保留为此前版本事实。锁只约束本入口，旧手动导入或其他写路径没有因此共同互斥；旧 `LockOwner` 的注释逻辑未恢复，新数据核心仍使用私有目录而非共享 `/tmp/mongo_dump`。

PR425旧版锁提示澄清（2026-10-28，只读）：当时截图错误 `an OBS version import is already running for this cluster` 对应 `LOCK_EX|LOCK_NB` 竞争返回的 `EWOULDBLOCK/EAGAIN`，映射为HTTP409；同一cluster的所有版本导入共享该锁，覆盖下载、预检、镜像和数据阶段，不同cluster各自独立。后台回调 `defer lock.Close()`，nonce或启动失败也关闭句柄；只有任务真正结束（成功、失败、超时退出）或持锁进程退出后释放，HTTP受理返回、WebSocket失败/断开不结束后台任务，也不释放锁。磁盘锁文件可以保留，文件存在本身不代表仍被锁。此次未查询现场持锁PID或任务状态；截图只说明请求获取锁时存在持锁者，不能据此断定某个先前PID仍在运行或已经卡死。没有解锁、删除文件、代码修改、测试或远端操作。

镜像核心 `obs_version_images.go` 根据魔数处理 gzip，并完整读取校验 CRC、tar 结构、安全成员路径、`manifest.json`/`RepoTags` 和层引用；bundle 中每个内层 Docker-save tar 也预检。导入复用 `common` 的带 context 仓库复制能力。结构预检不验证镜像 config 的全部业务字段或层 digest，实际推送仍可能因内容、认证或仓库条件失败。

数据核心Prepare/Run仍接受显式包与私有目录，不创建子PID。当前公开 `ValidateArchiveImportTarget` 在本组件下载前复用配置及只读SSH/Helm/Pod readiness；准备时若目标漂移返回 `ErrArchiveImportTargetUnavailable`，以errors.Is识别后日志跳过继续，真实包格式错误不带该sentinel。父context取消不作为跳过处理；实际Run错误仍失败停止，不猜凭据或安装组件。

组件校验规则保留：配置需精确匹配database标识；Helm过滤只判输出非空，并非精确release/deployed断言；同名namespace全量Pod需非空、不在删除中，Succeeded接受，其他需Running/PodReady及container Running+Ready。当前改为每个有包组件下载前检查、准备时复核；不满足依赖则日志跳过后续组件继续，不缓存早期健康/凭据。K8s健康不证明数据库连接或导入成功。

新 MySQL/MariaDB、MongoDB 路径使用严格脚本，解包和数据库命令错误向上传递；MongoDB 使用私有临时目录，并检查本机 `mongorestore --help` 支持 `--config` 与 `--stopOnError` 后执行。ES、PostgreSQL、StarRocks 复用参数化生成器。凭据经 stdin 传入，日志 writer 对跨多次 write 的敏感值脱敏；取消时杀死并等待整个命令进程组，日志 flush 错误计入失败。

旧单独数据接口的 MySQL/Mongo 宽松脚本仍保留，包括历史忽略解包错误、`mysql --force` 或 `mongorestore ... || true` 等边界；本次不能描述为所有旧导入入口已经修复。新路径仍有 `--drop` 等覆盖语义，失败重跑前需要结合日志与实际数据判断已完成步骤。

## OBS-28 本地验证与证据边界

开发阶段已通过以下定向验证，测试使用本地模拟网关、仓库动作、数据库命令和生成脚本，不代表真实环境功能恢复：

- 镜像归档临时定向测试覆盖结构预检；没有执行真实离线仓库推送。
- 六类数据 archive 验证，以及真实生成 shell 配合 mock 命令的失败传播、取消、凭据脱敏和语法检查通过；未执行真实数据库恢复。
- 总流程模拟网关覆盖分页、相邻版本/子目录隔离、跳过资料、下载及所有预检先于导入、镜像优先、预检或首镜像失败停止、原包保留、私有工作目录清理。
- HTTP 请求结束后后台继续、同集群重复锁拒绝、单 PID、handler 的 400/403/404/409 与标准 200 包装通过。本地现有 WebSocket 在后台 OBS 列表阻塞、任务尚未结束时已读取到 `execute.log`，随后读取到 no-op 总终态；这是本地实时日志证据。

```bash
CGO_ENABLED=1 go test -race -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./internal/service/file_server ./internal/service/importdata -run '^(TestObsVersion|TestArchiveReview)' -count=1
CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o <临时目录>/server ./cmd/server
```

上述 race 定向测试及 server 构建通过；最终源码又完成同 tags 的 server 构建，12 个本轮 Go 文件的 `gofmt -l` 为空，`git diff --check` 通过。临时二进制目录精确清理，所有本轮临时测试文件按用户约定在通过后删除。忽略文件 `swag.json` 已增量保留原接口并新增本接口，现为 14 条路径、19 个定义，最终再次校验 JSON 及 46 个定义引用通过；未修改 `.gitignore`。

真实 OBS/IAM 权限、固定 Zot 推送、六类真实数据库导入尚未验证；此前开发验证还受缺少 `mongorestore`、`unzip` 等实际工具限制，mock 不能替代现场工具版本和真实数据验证。代码现已提交推送、合入中央并完成121 Web编译替换及启动命令，但没有真实版本导入业务证据，metadata 保持 `unverified`。

后续部署与验证须按明确授权执行：准备符合格式的版本目录、目标集群组件和客户端工具，以有效会话受理后跟踪该 PID 的总终态，再检查目标仓库 manifest/可用镜像和目标数据库数据或业务查询。测试失败、部分写入、旧手动入口并发及重复导入的影响仍应结合现场判断，不能仅凭 HTTP 200、日志文件存在、编译或服务启动宣称整版恢复成功。

## OBS-28 2026-10-28 复查修复、验证与提交

用户要求复查后提交并发布 121。本轮先完成代码复查及修复，再提交推送；发布仍受中央已合并的项目约定约束。

| 复查问题 | 已完成修复与本地证据 |
|---|---|
| MongoDB URI 在查询参数前缺 `/`，可阻断解析 | 新增凭据配置 helper 并设置 `Path: "/"`。在临时独立 module 中用真实 MongoDB Go driver v1.17.6 的 `ParseAndValidate` 离线验证；临时 module 已清理，项目依赖未变。此结果只证明 URI 能解析，不证明真实连接或恢复。 |
| Elasticsearch 旧 API 的密码中含模板 token 时被后续替换再次改写 | 改为一次 `strings.NewReplacer`，运行真实但无网络的 shell setup 回归，验证生成脚本保留预期凭据值；不包含真实 Elasticsearch 导入。 |
| 镜像层的合法 symlink 被过严拒绝，别名 RepoTags 可能静默指向不同镜像 | 允许包内合法一跳 layer symlink，继续拒绝越界、链、环、非 layer 链接及 bundle 链接；以 normalized reference 去重，避免 `app:v1` 与 `docker.io/library/app:v1` 冲突。真实 `containers/image` 读取本地 manifest/blob 回归通过；不代表远端仓库推送成功。 |
| 无需导入的资料文件名含冒号等字符中断版本计划 | 先分类并跳过非导入资料，只有需处理的包才校验导入名称；跳过日志用 `%q`，避免控制字符破坏日志行。 |
| 新同步 MySQL/MariaDB 脚本受外部用户/login 配置影响凭据和失败语义 | 使用 `--defaults-file`、`--skip-force`，并设置 `MYSQL_TEST_LOGIN_FILE=/dev/null`；最终项专项 race 通过。旧独立 MySQL/MariaDB 宽松脚本未因此改变。 |

总流程重新验证分页、相邻版本/子目录隔离、资料跳过、下载→全部预检→镜像→数据的顺序，以及下载、预检、首镜像、首数据错误停止；原包保留、work 清理和 flock 释放通过。最后联合 `file_server`/`importdata` race、最终带支持 tags 的 server 构建、格式和 diff 检查通过；3 个临时测试文件已删除，临时构建产物已清理。根 `swag.json` 的 14 路径、19 定义、46 个引用校验通过，该文件因现有忽略规则仅保留本地更新，未纳入提交，未修改 `.gitignore`。

提交为 `65b61e3`，标题 `feat(obs): import version packages serially into clusters`，范围为本次 12 个 Go 文件，1518 行新增、6 行删除。`git push origin release` 成功，直接输出为 `5f148d0..65b61e3`。代码提交推送不等同中央合并或121发布。

提交后首次 fetch 核对时，中央 `release` 仍为 `014f0a1c33462ea8f6141d5240ce76753f5587f8`，`merge-base` 确认 `65b61e3` 未合并。现行 `AGENTS.md` 要求发布前目标已合并，并明确不自动创建/合并 PR；因此当时先请求“允许创建并合并 PR 后继续发布”或由用户手动合并，没有越过门槛直接发布。用户随后明确授权创建并合并中央 PR 后继续121发布，最终执行结果见后节。

121 发布前经固定别名 `codex-test-121` 做只读预检：当时仓库为 `release/014f0a1`，持久 `data` 保留，`configs/users.json` 为已有删除状态，`router.go` 仅有禁用 Vue 的两处本地调整，`server`/`server.pid` 为未跟踪文件，启动脚本存在。这些仅是发布准备事实；后续发布保留这些已有状态，结果见下节。

## OBS-28 2026-10-28 PR424合并与121 Web发布

用户明确授权后，创建并核对 [中央 PR424](http://192.168.3.34/Installation-package/g_web_installer/pulls/424)：head 为 `65b61e360a211b3d6892e72b5f7b30d935685c04`，base 为 `release`，范围仅 1 个提交、12 个文件、1518 行新增和6行删除。服务端 `mergeable=true` 后以正常 merge、`force_merge=false`、限定 `head_commit_id` 合并，API 返回 HTTP 200；后续读取确认 `merged=true`、合并 SHA 为 `1ed3b02d10a2eb3bab4d66553bf9f298fcd41ab4`。本地 fetch `upstream` 并核对祖先关系，确认原提交已进入中央 `release`。没有检查或等待 CI，不能把可合并状态描述为 CI 通过。

121 首个只读预检辅助脚本因目标 Python 不支持 `str.removesuffix` 报 `AttributeError`；错误发生在修改源码、构建或停止进程之前。改用兼容的 `endswith` 和切片后继续，不是未解决的部署失败。

固定使用 `ssh codex-test-121`，在 `/root/wfweb/g_web_installer` 的 `release` 上通过 `git pull --ff-only origin release` 从 `014f0a1c33462ea8f6141d5240ce76753f5587f8` 快进到 `1ed3b02d10a2eb3bab4d66553bf9f298fcd41ab4`，确认 `HEAD == origin/release` 且包含源提交。持久 `data`、`configs/users.json` 已有删除状态及未跟踪 `server`/`server.pid` 保留；只临时还原 `router.go` 禁用 Vue 的两行以拉取，并在 finally 基于新 HEAD 重新应用，没有覆盖其他本地改动。

使用登录 Shell 执行规定构建：

```bash
CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o server.next ./cmd/server
mv -f server.next server
```

构建与替换均退出0。二进制就绪后，仅一次 `ss` 定位8080旧监听 PID `852376`，单次 `/proc` exe/cwd 确认属于目标 Web；旧 exe 显示 `server (deleted)` 为替换后仍运行旧 inode 的正常现象。随后 `SIGKILL` 该进程并立即 `bash /root/wfweb/web_start.sh`，脚本直接报告 `server started, pid=1837742`，`web_start_exit=0`，SSH 退出0。

本次仅发布 Web，没有发布 KK。发布阶段没有重复跑测试，没有追加接口探测、日志关键字匹配、多轮端口/进程复核或自动回退。以上证明拉取、编译、替换及启动命令成功，不证明真实 OBS/IAM、镜像推送或数据库导入成功；真实版本导入仍待验证，metadata 保持 `unverified`。

## OBS-28 2026-10-28 审核过滤增强与本地定向验证

用户要求版本导入只处理审核通过的包。已在 `obs_v3_version_import.go` 新增 `filterApprovedObsVersionObjects`：先筛出版本直属文件，再通过现有 `obsMetadataMuV3` / `readMetadata(true)` 读取一次 `pass.json` 审核快照，沿用当前审核记录来源，本地优先、缺失时远端回源及缓存；按完整 `object.Key` 精确匹配，不以目录、裸文件名或其他版本的同名包代替授权。

审核过滤先于文件分类、空包/扩展及同数据库多包检查。每个未审核文件用 `%q` 在总 PID 日志输出 `[跳过] 文件未审核`，不下载、不预检、不导入；因此未审坏格式、空包或重复数据库包不会阻断已审核包。记录已审/未审数量，总汇总增加 `unapproved_skipped` 并计入 skipped。无直属文件时不读取审核记录；全部未审时记录跳过并沿用无可处理包的 no-op 终态。读取或解析审核记录失败时停止，不默认放行；现 helper 的远端404空记录按无审核包跳过，本地坏JSON不尝试回源覆盖。

定向 `TestObsVersionApproval*` 及以下 race 均通过：

```bash
CGO_ENABLED=1 go test -race -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./internal/service/file_server -run '^TestObsVersionApproval' -count=1
```

测试覆盖已审镜像/MySQL的下载、全部预检及镜像优先数据顺序；未审包不落地且不触发包检查；目录/裸名/他版本同名不能匹配；全未审 no-op；本地优先批审、远端回源缓存/404空记录、403/坏JSON失败停止、本地坏JSON不回源、无直属文件不查审核。它们使用本地模拟元数据及导入动作，没有真实OBS调用。

真实 `cmd/server` 以支持 tags、`CGO_ENABLED=0` 构建退出0，临时构建目录已清理；`gofmt -l` 为空、`git diff --check` 通过。唯一临时 `obs_v3_version_approval_temp_test.go` 在通过后删除；Swagger仍为14路径、19定义、46引用，JSON与引用再次校验通过，URL及参数结构不变。

实现验证阶段的业务变更仅版本worker，Swagger及案例文档同步更新；当时尚未 commit、push、merge或部署，121仍为前述PR424/`1ed3b02`。用户随后要求提交发布，完成下节交付；本节定向测试仍仅为本地证据，没有真实审核下载导入证明，metadata继续为 `unverified`。

## OBS-28 2026-10-28 审核过滤PR425交付与121 Web发布

用户明确要求“提交代码、发布121”后，仅提交 `obs_v3_version_import.go`，1文件、52行新增、1行删除。提交为 `39f55cd2dac13827318e11924f9cbdc058324835`，标题 `fix(obs): skip unapproved version packages before import`；`git push origin release` 成功，直接输出 `65b61e3..39f55cd`。本地忽略的Swagger说明同步保留，没有改动Go接口URL或参数。

沿用用户本会话明确授权的创建合并PR后继续121发布流程，未重复请示。创建并核对 [中央PR425](http://192.168.3.34/Installation-package/g_web_installer/pulls/425)，确认head为上述源提交、base为中央`release`，仅1提交/1文件/+52/-1；`mergeable=true` 后限定head、非强制正常merge，HTTP200，合并SHA为 `07f2566bbc7b5a35ae47295ac64fc97678e87a43`。本地fetch `upstream` 并核对祖先关系，确认源提交已进入中央release；未查询或等待CI，不能将可合并状态解释为CI通过。

固定使用 `ssh codex-test-121`，在 `/root/wfweb/g_web_installer` 的 `release` 执行 `git pull --ff-only origin release`，从PR424合并提交 `1ed3b02d10a2eb3bab4d66553bf9f298fcd41ab4` 快进到 `07f2566bbc7b5a35ae47295ac64fc97678e87a43`，确认 `HEAD == origin/release`。本次只变版本导入文件，`router.go` 非重叠的禁Vue两处改动直接保留，没有临时还原；持久 `data`、`configs/users.json` 已有删除状态、未跟踪 `server`/`server.pid` 状态保留。

登录Shell执行规定的支持tags构建 `CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o server.next ./cmd/server`，退出0；`mv -f server.next server` 退出0。二进制就绪后仅一次 `ss` 定位8080旧PID `1837742`，单次exe/cwd归属核对后SIGKILL，并立即 `bash /root/wfweb/web_start.sh`；直接输出 `server started, pid=1846958`、`web_start_exit=0`，SSH退出0。

本轮未重复本地测试、race或构建验证，沿用上节开发阶段结果；发布机执行了替换前必要构建。没有发布KK，没有接口探测、多轮进程/端口或日志关键字检查，也没有真实审核、下载、镜像或数据库导入业务证据。PR424/`1ed3b02`是前次发布历史，当前121已完成审核过滤PR425版编译替换及启动命令；真实审核导入仍待验证，metadata保持 `unverified`。

## OBS-28 2026-10-28 日志入口不匹配（只读排障）

用户用 `/obs/logs/tail/<pid>` 读取本次版本导入日志时报错，只提供URL，没有HTTP状态或错误正文。源码确认 `V3TailObsLogV3` 委托的 `TailObsLog` 固定查 `data/obs/history/<pid>/execute.log`，版本任务的owner却为cluster，实际写入 `data/cluster/<cluster>/history/<pid>/execute.log`。

通过固定别名121只读定位本次PID：OBS路径无文件（`obs_log_exists=false`），唯一命中的集群为 `k8s_test`；`/root/wfweb/g_web_installer/data/cluster/k8s_test/history/<pid>/execute.log` 存在，1197字节。该证据确认本次PID的日志归属与原入口查找路径不匹配；未读取日志正文或终态，不能据文件存在和大小判断导入成功或失败。

调用方应在当前Web host使用集群WebSocket路径，并对实际路径参数逐段URL编码：

```text
/api/v1/logs/cluster/k8s_test/tail/<pid>/execute.log
```

该接口需要WebSocket Upgrade，普通HTTP读取不等同订阅；V1认证需有效JWT Cookie或Bearer。原反馈没有HTTP状态/正文，不能把可能同时存在的认证、WebSocket升级等错误全部归因为路径。此次没有发起WS/HTTP请求、新导入、业务代码修改、测试或重启发布；只确认文件路径，不产生真实审核导入功能证据。既有PR425/`07f2566`启动记录保持，metadata仍为 `unverified`。

## OBS-28 2026-10-28 版本路径锁细分与本地定向验证

用户要求锁粒度细到部门版本，已在版本worker将锁身份改为 `clusterDir + normalize(完整OBS prefix)`；API callsite把prefix传入锁helper。完整路径的全部部门、产品、版本参与SHA256计算，不只截取末级版本号；首尾空白、前导/末尾斜杠规范化，路径大小写保留。相同目标cluster、相同规范化路径才互斥；不同部门/产品/版本或大小写不同的路径独立，不同cluster相同path也独立。锁文件为cluster目录下的 `.obs-version-import-<全64hex摘要>.lock`，继续使用flock而非仅进程内状态。

错误文字改为同cluster和version path已有任务，HTTP409及URL/入参不变。nonce/启动失败Close、后台全流程 `defer Close`、持锁进程退出后由OS释放的机制不变；持久锁文件无需消失即可重入。任务内部仍单PID单日志、顺序下载/预检/镜像/数据，锁细分允许多个不同path任务并行，不等于数据库写入已获得冲突隔离；旧手动入口仍未纳入锁。

`TestObsVersionLock*` 定向与以下race退出0：

```bash
CGO_ENABLED=1 go test -race -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./internal/service/file_server -run '^TestObsVersionLock' -count=1
```

覆盖同cluster同完整path的斜杠/首尾空白等价写法互斥；不同部门/产品/version/大小写路径及不同cluster独立；Close后保留文件仍可重入；内部重复斜杠和 `..` 拒绝；真实子进程持锁阻止同scope、不阻止别scope，并在 `os.Exit` 未显式Close后由OS释放、可重入。这些证明锁helper及进程级锁语义，未执行HTTP/API并发集成或真实并行业务导入，不能描述为数据库并发业务通过。

本地实际以支持tags、`CGO_ENABLED=0` 构建 `cmd/server` 退出0，临时产物清理；格式及diff检查通过，临时 `obs_v3_version_lock_temp_test.go` 已删除。业务仅1个Go文件18行diff（13新增、5删除），项目根目录Swagger只更新本接口description/409说明，14路径/19定义/46引用保持。当时仅完成本地开发验证、尚未commit/push或发布，121仍为PR425/`07f2566`旧cluster整体锁；用户随后明确要求提交发布，完成下节交付。没有新增真实并发导入业务证据，metadata继续为 `unverified`。

## OBS-28 2026-10-28 版本路径锁PR426交付与121 Web发布

用户明确要求提交并发布121后，仅提交本次Go文件，13行新增、5行删除。提交为 `9e5b1e883163da2157e40cb5d44eac279b01b86a`，本地分支为 `release`；`git push origin` 成功，直接输出 `39f55cd..9e5b1e8`。没有提交andrew归档，本地忽略的Swagger说明另行保留。

沿用本会话已明确授权的PR合并发布流程，创建并核对 [中央PR426](http://192.168.3.34/Installation-package/g_web_installer/pulls/426)：仅1commit/1file/+13/-5，head及base匹配后普通merge成功，合并SHA为 `69cf625d82e31c01c163be1e59f8be9cb7a01e98`。随后fetch `upstream` 并确认源提交祖先关系。

固定使用 `ssh codex-test-121` 登录Shell，在 `/root/wfweb/g_web_installer` 的 `release` 从 `07f2566` 快进到 `69cf625d82e31c01c163be1e59f8be9cb7a01e98`，核对HEAD精确匹配。保留持久 `data`、`configs/users.json` 已有删除状态及 `router.go` 禁用Vue的两处本地调整。

按规定执行 `CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o server.next ./cmd/server`，退出0；`mv -f server.next server` 退出0。二进制就绪后一次 `ss` 精确定位8080旧PID `1846958`，一次exe/cwd核对归属；`kill -9` 后立即 `bash /root/wfweb/web_start.sh`，直接输出 `server started, pid=1998781`，`web_start_exit=0`，SSH退出0。

没有重复开发验证或追加API、日志关键字、端口/进程探测。细粒度cluster加规范化完整版本path锁现已合并并发布到121；不同path可并行仅有源码及此前锁开发测试证据，没有真实并发导入业务验证，不能据编译、启动或锁测试宣称数据库并发导入通过，metadata仍为 `unverified`。

## OBS-28 2026-10-28 按Web出口选择下载线路与开发验证

用户确认沿用既有 `/api/v3/obs/file/download/url` 的 `url_cn` / `url_tw` 能力，不增加URL、入参、响应或前端改动。对有可处理包的任务，在下载循环前仅一次HTTPS请求 `https://ipwho.is/?fields=success,country_code`，以Web出口IP判断CN/TW；3秒总预算、最多4KiB，只接受HTTP200、success=true和CN/TW，禁重定向，不带Cookie/IAM或对象key。未知/失败写 `[下载线路]` 并回退CN，父context已取消则停止任务。该判断是出口而非物理主机地域，代理/VPN可能改变结果。

CN每包临下载前调用既有 `Client.Sign` / sign-direct，TW调用 `SignCDN` / sign-cdn；不提前签全版本，不调用会消耗兑换token的URL handler。只有TW走CDN，CN仍走既有网关签名直下，不能据此宣称214旧HTTP2 peer断流已修复。

新 `GetSigned` 复用连接池但创建不带IAM、Authorization或Cookie的下载请求，设置Accept-Encoding=identity，禁止redirect，transfer context保留至Body.Close。Do错误脱敏，不输出签名URL；非200只报状态码。原串行、总PID、临时part、完整大小校验及失败清理继续使用，没有新增retry/resume。

地域/client定向及整合测试通过，覆盖CN/TW每包现签且只选择对应签名接口、IAM仅用于sign而不发往下载端、原始字节保存和失败清理。联合race通过：

```bash
CGO_ENABLED=1 go test -race -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./internal/service/file_server ./internal/service/image_gateway -run '^(TestObsRegionDetector|TestObsSignedVersion|TestSignedDownload)' -count=1
```

实际server以支持三tags、CGO_ENABLED=0构建退出0，临时二进制目录及3个临时测试文件已清理，格式/diff检查通过。业务范围为修改version_import及新增version_download、gateway/signed_download三个源文件，无依赖或API结构变化；Swagger描述同步，14路径/19定义/46引用保持。该实现验证阶段尚未commit/push或部署，随后按用户指令完成下节121交付；仍无真实大陆/台湾GeoIP或4GiBCDN业务验证，metadata保持 `unverified`，旧发布事实及 [OBS-29](OBS-29.md) 的214断流证据保留。

## OBS-28 2026-10-28 出口选路PR427交付与121 Web发布

用户要求提交并发布121后，仅提交3个源文件、165行新增/3行删除，为 `934701bf68a6c300e5313efd3cafe66c0887ce68`；`release` 推送 `origin` 成功，直接输出 `9e5b1e8..934701b`。核对 [中央PR427](http://192.168.3.34/Installation-package/g_web_installer/pulls/427) 的1commit/3files/+165/-3及精确head/base后普通merge，合并SHA为 `bc6cd1a200ec92dd23643f7a270340d45a9aa6d9`；fetch upstream并确认源提交祖先关系。

固定 `ssh codex-test-121`，`/root/wfweb/g_web_installer` 的release从 `69cf625` 快进到 `bc6cd1a` 并精确匹配HEAD，保留data、`configs/users.json` 删除状态和router禁用Vue两行调整。登录Shell执行规定CGO_ENABLED=0、三build tags的 `go build -o server.next ./cmd/server` 及 `mv` 替换，均退出0。一次ss定位8080旧PID `1998781`、一次exe/cwd确认归属后kill -9，立即运行 `/root/wfweb/web_start.sh`；直接输出 `server started, pid=2084894`，`web_start_exit=0`、SSH退出0。

仅发布121 Web，214未发布、KK未动；没有追加测试、API/日志关键字或多轮端口/进程探测。编译替换和启动成功不代表真实出口GeoIP、4GiBCDN下载或完整导入通过，也不能证明214旧HTTP2断流恢复，metadata仍为 `unverified`。

## OBS-28 2026-10-29 镜像优先、按组件执行（PR428已交付121）

用户明确要求覆盖旧策略：有离线仓库才逐包下载/prepare/import/cleanup镜像，无仓库日志跳过镜像下载；随后按mysql、mongodb、mariadb、elastic、postgresql、starrocks顺序，对有数据包的组件先完整readiness，依赖缺失/异常日志跳过继续。实际下载、格式、import或cleanup错误仍停止，取消优先；审核、出口选路、版本path锁、一个PID串行、原包保留不变。此前未发布的全版纯配置gate和两阶段镜像准备原型已撤回，不是现行方案。

现公开入口为 `ValidateArchiveImportTarget`，内部resolve配置和validate共用规则；`ValidateArchiveImportTargetConfig`已删除。Prepare识别目标不可用sentinel以处理状态漂移，坏包格式不归类为依赖跳过；不会自动补配置或跳过实际导入错误。

最终4个业务源文件（3改+新增target.go）在开发阶段联合normal、两包race、server构建及格式/diff通过，3临时测试及构建产物清理；随后已按用户指令提交合并并发布121，见下节。没有新流程实际导入或业务验证，metadata为 `unverified`。

22:38旧版任务（尾83109a4c）五包CDN下载和三镜像预检通过后，因elastic未配置终止，镜像/数据写入均0，详见 [OBS-31](OBS-31.md)。用户随后单独要求删除该终态PID：history与obs-import两个目录已删，config保留，free约45.65→57.49GiB；Web2084894未重启，原终态日志FD被持有不代表路径仍在。此为明确手动清理，不是新流程自动删日志，详见 [OBS-30](OBS-30.md)。

## OBS-28 2026-10-29 PR428交付与121 Web发布

用户要求提交并发布121后，仅四个业务源文件提交 `42bbcb8e4f78924f40daab52544a78c1385c48a5` 并推送origin/release。创建并合并 [中央PR428](http://192.168.3.34/Installation-package/g_web_installer/pulls/428)，合并SHA `a024faf86abf135018df62416d2a1bf381cca728`；fetch/merge-base确认源提交已在中央release。

固定 `ssh codex-test-121`，`/root/wfweb/g_web_installer` release经ff-only从bc6cd1a更新到a024faf，并核实包含42bbcb8；data、configs/users.json既有删除状态、router禁Vue本地调整及server/pid保留。登录Shell规定CGO_ENABLED=0、三tags构建server.next并mv替换完成；一次ss定位8080旧PID2084894、一次exe/cwd确认归属后kill9，立即执行web_start.sh，输出 `server started, pid=2689696`，`startup_command_succeeded:true`，SSH退出0。

仅发布Web，KK未发布；没有追加端口/API/日志/哈希检查，没有触发新OBS导入。编译替换启动成功不代表依赖跳过或镜像/数据库业务已实测，新流程整体仍为 `unverified`。

## OBS-28 来源定位

- 2026-10-29本地 `internal/service/file_server/obs_v3_version_import.go`、`obs_version_images.go` 的此前未发布空间原型及本地测试结果；121旧二进制22:38任务阶段与配置失败终态，见OBS-31。

- `internal/service/file_server/obs_v3_version_download.go:27`、`:72`（本轮本地出口判定）；`internal/service/image_gateway/signed_download.go:16`（签名URL无IAM下载）。

- `g_web_installer/internal/transport/router.go:193`；`internal/transport/handler/obs_v3_version_import.go:14`；`internal/transport/handler/obs_v3_middleware.go:138`。
- `internal/model/request/obs.go:51`；`internal/model/reply/obs.go:65`；根目录本地 `swag.json`。
- `internal/service/file_server/obs_v3_version_import.go:36`（受理、权限、异步 context）、`:111`（本轮本地版本路径锁）、`:141`（审核过滤）、`:182`（计划）、`:227`（后缀映射）、`:274`（串行流程及清理）、`:406`（下载与传输超时）。
- `internal/service/file_server/obs_version_images.go:30`（私有预检副本）、`:96`（同步推送）、`:122`、`:243`、`:297`（tar、manifest、bundle 校验及 layer 链接/reference 去重）。
- `internal/service/importdata/archive_import.go:44`（准备）、`:177`（Mongo URI）、`:192`（等待与取消）、`:237`（私有副本）、`:285`（SSH context）、`:334`、`:364`、`:413`（格式校验）、`:578`（日志脱敏）、`:639`、`:666`、`:687`（严格脚本）。
- `internal/service/importdata/importdata.go:57`（组件校验）、`importdataV2.go:92`、`:406`、`:419`（参数化 ES 与单次模板替换）、`:538`、`:631`（旧脚本边界）；`postgresql.go`、`starrocks.go:83`（复用生成器）。
- `internal/service/image_gateway/client.go:236`（前缀分页）；`internal/service/file_server/obs_executor.go:44`、`:60`、`:95`（异步受理、日志归属与统一终态）。
- `internal/transport/handler/log.go:28`；`internal/service/log/tail.go:69`（现有 PID WebSocket）。
- 本轮本地模拟链路、脚本、HTTP/WebSocket、race 定向测试、构建与 Swagger 校验结果；未保存原始会话、完整日志或实际认证值。

[返回案例索引](../README.md)
