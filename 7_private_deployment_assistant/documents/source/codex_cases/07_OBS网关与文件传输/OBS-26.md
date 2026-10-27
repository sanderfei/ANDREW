# OBS-26：V3用户权限配置在线读取与整体覆盖接口

项目：g_web_installer。记录日期：2026-10-23，后续更新：2026-10-26。开发基线为本地 `release/8afe3ab`，实现提交为 `f932ef97217010135bd7cd5ebe849f90d18ebaa8`，Go 1.24.0/toolchain 1.24.5；Web后端通过Image Gateway操作OBS。PR421已合并为 `196d64038d8df7490b2c8b8ce327ee5670907512`，121已完成该提交的Web编译、替换及启动命令。2026-10-26用户反馈users读取接口触发all权限拒绝，后续分析见本文对应章节。Kubernetes、OS和在线/离线安装模式不决定该接口协议。完整真实OBS及IAM功能仍未验证。

## OBS-26 问题与表现

用户需要两个Web V3接口：读取OBS的 `config/users.json`，解析为JSON对象返回；编辑时将提交的完整JSON对象覆盖到同一OBS文件。已有V3登录和目录列表每次读取远端权限，但缺少用于完整配置查看、编辑的专用接口。

本轮未收到现场报错，属于新增管理能力。历史本地users.json热加载问题见[WEB-05](../05_Web配置鉴权与任务/WEB-05.md)，不能将其本地文件与watcher机制套用于当前V3远端权限来源。

## OBS-26 已确认实现与权限边界

- 唯一对象key是 `config/users.json`，网关请求不带前导 `/`。新增接口直接读取远端，不读取 `configs/users.json`、`data/config/users.json` 或OBS本地缓存，不持久化下载文件。
- 从既有 `GetUserPrivilegesV3` 提取 `ReadUserPrivilegesV3`，共享完整映射解析和对象key。原有按用户取权限的调用继续保持每次在线读取，以及未知用户、空权限的返回语义。
- 路由位于原有V3分组，要求有效Web JWT、Ops身份和当前JWT绑定的V3 IAM会话；请求头不能替代缺失会话。
- 沿用现有仅 `all` 用户可见 `config/` 的约定，两个新接口都读取OBS当前权限表，校验当前用户具有 `all` 后才返回完整表或允许覆盖。更新请求中的新权限不参与本次授权，普通用户无法通过提交自己为 `all` 获得写权限。
- 编辑是整体替换，不做增量合并。请求遗漏的用户会被移除；`{}` 是明确清空，允许有权用户执行，随后该用户也失去本接口要求的 `all` 权限。
- 请求必须为单个JSON对象，key为非空白用户ID，value为非null字符串数组，权限项不能为空白。允许空数组表示无权限；拒绝根值null、数组根值、非法类型、空正文、尾随JSON或其他内容。
- 原始请求体限制16MiB；编码后的配置也不得超过16MiB，避免写出后续无法读取的配置。原始请求超限返回413，配置内容校验失败返回400。
- 更新前先读取当前配置完成授权，再以 `application/json` 和准确Content-Length上传。复用元数据超时和网关客户端，只有收到HTTP201且返回key、size匹配时才返回保存对象。
- 使用既有进程内 `obsMetadataMuV3` 协调新接口的读取、当前权限校验和覆盖上传。该锁不协调其他Web实例或外部写入者；整体覆盖采用最后成功写入的内容，没有跨实例合并或ETag条件写保证。

## OBS-26 接口与可执行接入步骤

1. 确认OBS已经存在合法的 `config/users.json`，当前操作者在其中拥有 `all`，且其IAM身份可读取、覆盖该对象。权限示例仅使用虚构用户ID：

```json
{
  "id_admin": ["all"],
  "id_user": ["部门A", "部门B"]
}
```

2. 沿用Web现有本地登录、V3 IAM登录流程，使用V3 JWT或 `GWebInstallerToken` Cookie调用 `GET /api/v3/obs/users`。无需请求参数，成功返回 `{"code":10000,"msg":"OK","data":{...}}`，data为完整配置对象。
3. 调用 `POST /api/v3/obs/users/update`，Content-Type为 `application/json`，请求体直接使用修改后的完整对象，没有 `users` 外层字段。成功响应同样在data中返回保存的对象。
4. 保存成功后再次GET检查新内容；V3登录和目录列表在下一次请求中重新读取最新权限。只提交局部用户会删除未提交用户，提交前应按整体配置准备正文。
5. 401时重新建立有效V3会话；403时核对当前远端表中的 `all` 及IAM权限；404或远端JSON损坏时核对、修正OBS原对象。新接口不会使用旧本地配置回退，也不会在读取失败后默认创建空表覆盖。

## OBS-26 验证结果与遗留事项

- `CGO_ENABLED=0 go test -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./internal/service/file_server ./internal/service/login ./internal/transport/handler` 退出0；file_server与handler测试通过，login包编译通过，其按用户读取函数由服务测试调用验证。
- 相同范围使用 `CGO_ENABLED=1 go test -race` 和上述tags退出0。
- 本地HTTP网关替身验证连续读取反映外部更新，损坏本地旧文件被忽略且不被修改，没有创建OBS本地缓存；覆盖后旧用户被删除，原有权限读取函数立即读到新用户权限。
- 验证普通用户不能读取完整表或给自己授予 `all`，原有all权限被远端撤销后下一次编辑拒绝且不上传；显式空对象确实替换为 `{}`，随后读取返回权限不足。
- 覆盖404、401、403、503及空文件、非法JSON、null、数组、类型错误、尾随内容等10种远端读取失败场景，均不发生上传；上传403及错误key响应不会报告成功。
- Handler验证成功响应中的data是JSON对象；错误输入、null权限数组或权限项、尾随内容和超过16MiB均被拒绝。缺失JWT返回401、缺失Ops身份返回403、缺失V3会话返回401；补充IAM请求头仍不能替代会话，验证中未访问真实网关。
- 使用项目tags、`CGO_ENABLED=0` 构建真实 `./cmd/server` 成功，临时产物160272760字节并已清理。临时测试源码按约定删除；格式和差异检查无输出。
- 根据 `internal/AGENTS.md`，在现有被Git忽略的根目录 `swag.json` 补充两个接口和一个配置对象schema，原有10条路径、16个定义保留，补充后共12条路径、17个定义；未增加handler Swagger注释或修改其他接口说明。
- 测试只使用本地HTTP替身与虚构身份，不能证明真实IAM、OBS权限或配置编辑已通过。后续提交、合并与121发布结果见下一节；元数据继续保持 `unverified`。

## OBS-26 提交、合并与121发布结果（2026-10-23）

用户要求提交代码并发布121，本轮只发布Web，KK未构建或替换。实现提交 `f932ef97217010135bd7cd5ebe849f90d18ebaa8` 的标题为 `feat(obs): add remote users configuration APIs`，包含本任务5个Go代码文件；`git commit`、`git push origin release` 均退出0。根目录被忽略的 `swag.json` 与andrew案例没有进入此次提交。提交阶段没有重复格式化、测试或构建。

创建并正常合并 [PR421](http://192.168.3.34/Installation-package/g_web_installer/pulls/421)，目标为中央 `release`，源为 `wangfei:release`。Gitea提交和文件列表确认仅本次1个提交、5个文件，合并前head为 `f932ef9`，mergeable为true；合并后返回 `merged=true`，合并提交为 `196d64038d8df7490b2c8b8ce327ee5670907512`。fetch中央release后通过祖先关系确认该分支包含本次实现。未强推、未强制合并，也没有将mergeable或本地测试描述为CI通过。

121通过固定别名 `ssh codex-test-121`，在 `/root/wfweb/g_web_installer` 使用登录Shell发布：

1. 发布前确认目标在 `release/96c8cf3`，存在持久化data目录、后端专用router改动，且现场 `configs/users.json` 已删除。保留该删除状态，不恢复旧权限示例文件。
2. 首轮辅助脚本使用了目标机Python 3.6不支持的 `subprocess` 参数 `text=True`，在分支读取阶段退出1，尚未修改源码或停止服务。调整为 `universal_newlines=True` 并兼容旧版字符串处理后继续。
3. 核对router本地改动仅为禁用Vue import与 `vue.ServeVue` 后，暂时恢复该文件以便执行 `git pull --ff-only origin release`，随后基于新源码重新应用同样两行调整；没有覆盖data或配置现状。
4. 代码从 `96c8cf3` 快进到 `196d640`，HEAD等于 `origin/release`，并确认包含本次中央合并。中央此前已合并的 `059b087`、`5406138` 工作负载更新也随最新release拉取；它们不属于PR421的5文件提交范围。
5. 执行 `CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o server.next ./cmd/server`，成功后 `mv -f server.next server`，直接输出编译与替换完成。
6. 二进制准备完成后，仅通过一次 `ss` 查询8080监听PID并核对一次归属：旧PID2832810，cwd为目标Web目录，exe归属目标server。对该PID执行SIGKILL后立即运行 `/root/wfweb/web_start.sh`，脚本返回 `server started, pid=3027537`，发布命令退出0。

发布阶段复用开发验证，没有重复测试，也没有追加接口探测、日志关键字匹配、多轮进程/端口检查或自动回退。以上证明源码合并、远端编译、二进制替换和启动命令成功，不证明真实OBS权限读取、整体覆盖、IAM会话或业务功能已验证。案例仅本地更新，未向量入库或提交andrew文档。

## OBS-26 后续：读取接口提示all权限不足（2026-10-26）

用户反馈 `/api/v3/obs/users` 返回 `all permission is required to manage OBS users config`。未提供本次请求的实际用户ID、远端权限配置或HTTP抓包，本轮没有读取真实用户配置、调用线上接口或修改业务代码。

按当前源码，错误由Web业务函数readObsUsersForAdminV3主动返回，对应HTTP403。触发顺序为：

1. ReadUserPrivilegesV3通过当前V3会话读取并解析OBS的 `config/users.json`；失败时返回另一类读取错误，不会进入本次权限判断。
2. 以ObsV3Context.userId查找配置项；该身份来自JWT经中间件传入，不取请求体中的userId或显示名。
3. 遍历该用户的权限数组，仅精确字符串 `all` 可通过。用户ID没有匹配项、数组为空或只有部门权限，以及 `ALL`、` all`、`all ` 都会触发当前报错。

因此可以确认这是源码中的应用权限拒绝条件；按该调用链，读取和JSON对象解析已通过。仅凭当前错误无法判断是实际用户缺少all，还是登录身份与配置key不一致，也无法证明配置编辑、其他用户权限或完整OBS功能正常。

该all限制是此前实现users配置读写接口时加入的设计，读取和覆盖两个接口均要求。用户后来要求“不做权限过滤”针对新增 `GET /api/v3/obs/folder/top/list`，该接口已按要求去掉业务目录权限过滤；本次users读写接口的all判断尚未收到移除指令，未修改。

处理步骤：先核对当前JWT绑定的实际userId，再核对OBS原文件中同名key的权限数组是否包含精确小写all。若需要授予管理权限，应由有权限的管理者修改对应条目并保留其他用户配置；服务每次重新读取，下一次请求使用新内容。若需求是普通已登录用户也可读写完整权限表，需要明确变更这两个接口的授权规则，不能把新一级目录接口的行为当成已经改变了users接口。

验证边界：已复查GetObsUsersV3、UpdateObsUsersV3、readObsUsersForAdminV3、ReadUserPrivilegesV3和403错误映射。未获取实际用户或配置，未作修改、测试、构建或服务器操作；身份与配置具体不匹配原因待核对，metadata继续unverified。

## OBS-26 来源定位

- `g_web_installer/internal/service/login/ops_user.go`：`UserPrivilegesObjectKeyV3`、完整权限读取与按用户权限读取。
- `g_web_installer/internal/service/file_server/obs_v3_users.go`：两个服务函数、当前all授权、数据校验及覆盖上传。
- `g_web_installer/internal/transport/handler/obs_v3_users.go`：HTTP接口、完整正文解析和大小限制。
- `g_web_installer/internal/transport/router.go`、`internal/transport/handler/obs_v3_middleware.go`：原V3分组、会话要求和400/403错误映射。
- `g_web_installer/internal/service/file_server/file_server_v3.go`：既有config可见性、元数据锁、元数据上传和列表权限来源。
- `g_web_installer/internal/service/image_gateway/client.go`：16MiB读取上限、会话双token请求以及上传201/key/size校验。
- `g_web_installer/internal/AGENTS.md`、被忽略的根目录 `swag.json`：接口说明维护约定与本轮两个接口定义。
- 本轮本地HTTP替身断言、定向测试、race、构建、格式与差异检查的直接结果；不保留临时测试、真实用户配置或凭据。
- 本次Git提交/推送输出、PR421提交及文件范围和合并结果、中央Git祖先关系；121登录Shell的ff-only拉取、编译替换、单次8080归属确认和启动脚本直接输出。

[返回案例索引](../README.md)
