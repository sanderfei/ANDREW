# OBS-27：V2与V3目录列表按前缀和分隔符列举单层内容

项目：g_web_installer。记录与更新日期：2026-10-26。开发基线为本地 `release/f932ef9`，V2依赖 `github.com/huaweicloud/huaweicloud-sdk-go-obs v3.25.9+incompatible`，V3经Image Gateway访问OBS。先分析两个既有列表接口，随后实现 `GET /api/v3/obs/folder/top/list`，返回全部一级目录名。4个Go文件提交为 `5f148d0d292142d54a96993a8d3384d93497b22f`，已推送origin/release并经PR423合并中央release为 `014f0a1c33462ea8f6141d5240ce76753f5587f8`。开发定向测试及后端构建通过；121已完成Web编译、替换及启动命令，真实OBS功能未验证。Kubernetes、OS和在线/离线安装方式不决定列举协议。

## OBS-27 问题与表现

用户希望只获取OBS一级目录，或获取指定目录下的直接子目录、文件，避免把子目录内部对象也列出来，随后追问V3是否也支持，并要求新增返回一级目录字符串列表的V3接口。实现期间用户明确不做权限过滤，返回所有一级目录，并质疑额外排序；最终实现不读取users.json、不做目录权限过滤或排序。本轮没有现场报错或性能测量，不能把源码上的列举范围直接描述为已复现的线上慢请求。

## OBS-27 已确认原因与能力

- V2请求体 `ObsObjectsRequest` 当前只有必填 `userId`，没有用于选择目录的 `prefix` 或 `path`。
- `ListObjects` 固定使用空Prefix、MaxKeys=1000，未设置Delimiter，只调用一次 `obsClient.ListObjects`，再遍历 `output.Contents` 做权限过滤和字段组装。SDK没有在此处逐个目录发起递归请求；实际是获取桶内跨层级对象的第一页。
- 当前实现没有处理 `IsTruncated`、`NextMarker`。当OBS返回结果被截断时，后续对象不会出现在当前接口响应中，不能将它描述为完整桶列表。
- 当前SDK已经支持 `ListObjsInput.Prefix` 和 `Delimiter`，不必为单层列举升级SDK。SDK把这两个字段转换成请求参数，由OBS服务端按前缀筛选并按分隔符归组。
- 指定Delimiter为 `/` 时，`CommonPrefixes` 返回当前前缀下一层的目录前缀，`Contents` 返回该层未被归组的对象。无需下载文件内容，也无需在应用中枚举每个子目录的内部对象再过滤。
- OBS对象桶的目录是对象key前缀形成的分组。`CommonPrefixes` 是字符串列表，不含目录汇总大小或最后修改时间，不能把它当成完整文件元数据。空目录须有对应目录标记对象才能被列举。

## OBS-27 可执行方案（未实现）

| 目标 | Prefix | Delimiter | 使用返回字段 |
|---|---|---|---|
| 桶根目录的一级目录 | 空字符串 | `/` | `CommonPrefixes` |
| 桶根目录的文件 | 空字符串 | `/` | `Contents` |
| 部门目录的直接子目录和文件 | `部门A/` | `/` | 两个字段一起组装 |
| 指定版本目录的直接子目录和文件 | `部门A/时间戳-版本-noisrev/` | `/` | 两个字段一起组装 |

示例仅展示SDK参数，不是对现有接口的修改：

```go
input := &obs.ListObjectsInput{
    Bucket: bucket,
    ListObjsInput: obs.ListObjsInput{
        Prefix:    "部门A/",
        Delimiter: "/",
        MaxKeys:   1000,
    },
}
output, err := obsClient.ListObjects(input)
```

1. 如果后续获准实现，在保留既有用户权限校验的前提下，为请求增加目录前缀参数。访问具体前缀时也要校验所属一级目录权限，不能只在根列表过滤。
2. 根层查询使用空Prefix；指定父目录时使用实际OBS key前缀，目录前缀保留末尾 `/`，避免 `部门A` 误匹配 `部门AB/`。示例key没有前导 `/`，根层查询不能用 `/` 代替空字符串；历史实际key如含特殊前导字符，应按真实key处理。
3. 将CommonPrefixes组装成目录项，Contents组装成当前层文件项；如Contents包含当前Prefix对应的目录标记，应跳过该自身项。仅需要目录时读取CommonPrefixes即可，但不存在单独的“只返回目录”布尔参数。
4. 每页最多1000项，仍需处理 `IsTruncated`；为true时把 `NextMarker` 传给下一次的 `Marker`，保持相同Prefix和Delimiter继续取页。取下一页属于当前层分页，不表示递归进入子目录。
5. SDK没有通用的 `depth=N` 参数。已知父目录可直接查询该父目录下一层；若要全桶所有第N层条目，需逐层枚举父前缀到目标层，避免继续进入目标层下面的内容。
6. 如需保持现有OptUrl、RevUrl、IsPass字段，继续按实际目录key关联配置；CommonPrefixes本身不会携带这些业务信息。没有实际性能测试，不承诺服务端内部扫描方式或固定性能提升比例。

## OBS-27 V3后续分析：网关支持，既有Web列表未改

V3没有直接调用华为OBS SDK，而是由Web服务调用Image Gateway。需要分别判断网关协议和Web公开接口，不能将下游支持表述为现有Web接口已经可用。

| 层次 | 当前情况 | 证据 |
|---|---|---|
| 网关 `GET /api/v1/objects` | 文档支持 `prefix`、`delimiter=/`、`max_keys`、`marker` | `g_web_installer/docs/API.md:135-173` |
| 网关分层响应 | `common_prefixes` 为子目录，`objects` 为对象，`truncated/next_marker` 用于分页 | 同一节参数表与返回字段说明 |
| Web `POST /api/v3/obs/folder/list` | 请求模型只有必填userId，不能选择父目录或单层模式 | `internal/model/request/obs.go:3`、V3 handler |
| V3服务 | 固定以空前缀调用ListAll，再过滤权限并关联版本链接 | `internal/service/file_server/file_server_v3.go:163-243` |
| Web网关客户端的既有ListAll | 有prefix入参，但不发送delimiter，也不解析common_prefixes | `internal/service/image_gateway/client.go:237-265` |
| 新增Web接口 `GET /api/v3/obs/folder/top/list` | 只查根层，以delimiter=/取全部分页的common_prefixes，再返回名称数组 | `ListTopFolders`、`ListTopFoldersV3`、`ListObsTopFoldersV3` |

当前V3与V2的一个区别是，V3的ListAll已经按 `truncated/next_marker` 循环分页，并拒绝空或重复的后续游标。因此V3会按网关的分页结果取完整列表，再在Web中做权限过滤；不能把V2“只读第一页”的限制套到V3。这里的“完整”以网关正确履行分页协议为前提，未做真实OBS数据量验证。

若后续扩展为任意父目录的单层浏览，建议（当前新增接口仅覆盖根层）：

1. 在V3接口请求中增加父目录前缀参数，根层为空字符串，指定目录为实际key加末尾 `/`；这是方案，现有接口未提供该参数。
2. 新增用于单层浏览的网关客户端方法，发送 `delimiter=/`，同时解析并跨页收集 `common_prefixes` 和 `objects`。分页时保持prefix和delimiter不变；不能只在现有ListAll请求上补delimiter，否则目录分组会因未解析而丢失。
3. 将common_prefixes转换为 `is_directory=true` 的目录项，objects转换为本层文件项，过滤自身目录标记，并以真实目录key关联IsPass、OptUrl、RevUrl。
4. 如扩展既有受权限控制的列表，保持其JWT身份和目录权限约束；当前新建一级目录接口按用户明确要求返回全部目录，不套用既有权限过滤。既有列表仍用obsContext中的身份覆盖客户端传入的userId。
5. 保留现有ListAll的跨层级行为：V3目录删除和目录重命名也复用ListAll，需要获取全部后代对象；全局改为单层会使这两类操作遗漏文件。

private-service当前 `internal/app/pkg/util/obs_artifact.go` 的版本目录查找也已按同一网关协议发送 `delimiter=/` 并解析common_prefixes，可作参数用法的源码旁证；该代码存在不等于本轮真实网关功能已经验证。

## OBS-27 新增全部一级目录接口（PR423已合并，121启动命令成功）

路由：`GET /api/v3/obs/folder/top/list`，无需请求参数或请求体。复用V3现有Web JWT、Ops身份和当前JWT绑定的IAM会话校验；不读取users.json做业务目录权限过滤，包括config在内的一级目录均可返回。

成功响应示例（顺序取决于网关，不做额外排序）：

```json
{
  "code": 10000,
  "msg": "OK",
  "data": ["数采平台", "config", "IndepthAI"]
}
```

- 网关客户端新增ListTopFolders，固定空prefix、delimiter=/、max_keys=1000。按truncated和next_marker读取全部根层分页，拒绝空、重复或循环游标；不请求子目录内容，不取文件正文。
- 服务新增ListTopFoldersV3，只处理common_prefixes，排除根标记、非目录和非一级前缀，去掉一个末尾 `/` 后返回目录名。保留原始大小写和空格；跨页重复名称仅保留第一次，顺序按网关返回，不调用sort.Strings。
- 没有目录时返回 `data: []`，不会编码成null。后续页失败时返回错误，不把前面已获取的部分目录包装成成功响应。
- 不读取users.json、pass.json或versionUrl.json，不创建本地缓存，下一次请求重新列举。所有目录范围由当前配置桶与网关列举结果决定。
- Handler沿用统一code/msg/data结构及现有网关错误转换。IAM会话校验保持在原V3中间件内，当前身份凭据不由请求参数覆盖。
- 原有POST列表、ListAll、目录删除和目录重命名的全后代查询保持原实现。
- 按internal/AGENTS.md在本地被Git忽略的swag.json补充1条GET路径，原12条路径与17个定义保留，现为13条路径、17个定义；没有新增Swagger代码注释。

## OBS-27 实现验证结果

- `CGO_ENABLED=0 go test -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./internal/service/image_gateway ./internal/service/file_server ./internal/transport/handler` 退出0。临时测试位于handler包，通过真实本地HTTP网关替身贯通handler、服务和客户端；前两个包本身没有独立测试文件，但相关函数由handler用例调用覆盖。
- 验证无需请求体、全部一级目录包含config、不读取用户权限或其他元数据、不进入子目录，特殊字符分页游标正确传递，重复目录去重并保留网关顺序，目录名大小写与空格原样保留，根文件和异常深层前缀不成为目录名。
- 验证空桶与仅有根文件时data为数组，第一页面只有文件但仍有后续页时继续列举；空、重复或循环游标拒绝，后续403不返回部分成功，非法网关JSON和401/503正确返回错误。
- 连续两次请求反映网关目录变更；ListAll仍不传delimiter且返回后代对象；已取消context会终止新目录查询。
- 临时测试源码按用户约定在通过后删除。上述HTTP用例注入本地业务上下文，未模拟真实IAM登录或实际网关，不将它描述为线上鉴权验证。
- 使用相同tags与CGO_ENABLED=0构建真实 `./cmd/server` 退出0，临时二进制160283323字节，已自动删除。格式检查和git diff --check无输出，Swagger JSON及路径、定义数量校验通过。
- 无新增共享并发状态，开发验证没有额外执行race。后续提交、合并及121发布结果见下一节；没有连接真实OBS，metadata保持unverified。实际网关目录标记、隐式目录及大目录分页仍待联调验证。

## OBS-27 提交、合并与121发布结果（2026-10-26）

用户明确要求提交代码并发布121，本轮仅发布Web，KK没有编译、复制或重启操作。

1. 提交阶段确认当前release分支、origin/release推送目标和本次4文件范围，暂存区原先没有其他改动。只暂存这4个Go文件，`git commit` 生成 `5f148d0d292142d54a96993a8d3384d93497b22f`，标题为 `feat(obs): list all top-level folders`；`git push origin release` 退出0，源分支从f932ef9推进到5f148d0。没有在提交阶段重复修改、格式化、测试或构建。被忽略的swag.json及andrew案例未进入代码提交。
2. 中央release在本次合并前为 `2a0e5271c49c99c78111c863cb73b435efe03583`。通过现有Git凭据在进程内调用内部Gitea API，创建 [PR423](http://192.168.3.34/Installation-package/g_web_installer/pulls/423)，目标release、来源wangfei:release。核对head精确为5f148d0，仅1个提交、4个文件、67行新增，mergeable为true。正常合并后返回merged=true、merge_commit_sha为 `014f0a1c33462ea8f6141d5240ce76753f5587f8`；fetch中央release后确认包含实现与合并提交。没有强推、强制合并或将mergeable称为CI通过。
3. 固定使用 `ssh codex-test-121`，目标目录 `/root/wfweb/g_web_installer`。发布前HEAD为196d640，保留现场 `configs/users.json` 已删除状态、持久data目录，以及router中禁用Vue import与vue.ServeVue的两行本地调整。读取现有web_start.sh确认其只启动已构建server并写入logs/server.log与server.pid，没有修改启动脚本。
4. 目标Python使用兼容现有版本的 `universal_newlines=True`。核对router本地内容只含已知两行调整，暂时还原该文件以便 `git pull --ff-only origin release`，finally按新HEAD重新禁用这两行。拉取从196d640快进到014f0a1；HEAD等于origin/release，严格确认5f148d0与014f0a1均为当前HEAD祖先。数据目录原地保留，配置文件删除状态保持。中央此前PR422的已合并修改也随最新release拉取，不属于本次PR423的4文件范围。
5. 使用登录Shell执行 `CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o server.next ./cmd/server`，返回WEB_BUILD_OK后执行 `mv -f server.next server`，输出WEB_BINARY_REPLACED。编译和替换在停止旧服务之前完成，没有发布阶段重复测试、额外备份或二进制哈希比对。
6. 仅一次 `ss -ltnp 'sport = :8080'` 获取监听PID并核对一次归属：旧PID3027537，cwd和exe均属于目标Web目录。对该PID发送SIGKILL后立即执行 `/root/wfweb/web_start.sh`。脚本直接返回 `server started, pid=852376`，整体SSH命令退出0并输出WEB_RELEASE_COMMANDS_OK。

发布阶段没有追加接口请求、日志关键字匹配、多轮进程/端口检查或自动回退。以上证明代码合并、目标源码快进、编译、替换和启动命令成功，不能证明真实OBS一级目录接口或IAM会话功能已经通过。metadata继续为unverified；andrew仅本地归档，未提交、推送或录入向量库。

## OBS-27 验证结果与遗留事项

- 已核对本地V2路由、请求模型、handler、服务函数，以及当前锁定版本SDK的输入输出结构、请求参数转换和调用方法。
- 已在线核对华为云Go SDK官方“列举桶内对象”文档，确认Prefix、Delimiter、CommonPrefixes、Contents和分页字段语义。
- V3追问已核对本地网关协议文档、V3 handler与服务、客户端参数/分页/响应解码，以及目录删除和重命名的ListAll调用点。没有连接网关进行现场验证。
- 上述只读结论针对原有POST列表；后续新增的V3 GET接口实现和本地执行证据见前两节。既有V2、V3 POST列表未改为单层查询。
- 当前仅新增返回根层目录名的接口。任意父目录下的文件/目录混合浏览仍为方案；真实OBS及IAM联调、显式空目录与隐式目录、超过1000项分页待现场验证。

## OBS-27 来源定位

- `g_web_installer/go.mod:20`：实际SDK版本。
- `g_web_installer/internal/transport/router.go:153-159`：V2分组与目录列表路由。
- `g_web_installer/internal/model/request/obs.go:3`：当前请求仅userId。
- `g_web_installer/internal/transport/handler/file_server.go:21`：绑定请求并调用服务。
- `g_web_installer/internal/service/file_server/file_server.go:369`、`:450`、`:479`：权限校验、空Prefix单页请求及Contents处理。
- 当前SDK `obs/model_object.go:22-55`：ListObjsInput、ListObjectsInput、ListObjectsOutput；`obs/trait_object.go:27-40`：Prefix/Delimiter请求参数转换；`obs/client_object.go:26`：ListObjects方法。
- [华为云Go SDK：列举桶内对象](https://support.huaweicloud.com/sdk-go-devg-obs/obs_33_0406.html)，2026-10-26在线核对，页面标注更新时间2026-09-08。
- `g_web_installer/docs/API.md:135-173`：网关列对象协议与目录分组字段。
- `g_web_installer/internal/transport/router.go:188`、`internal/transport/handler/file_server_v3.go:26`：V3列表入口。
- `g_web_installer/internal/service/file_server/file_server_v3.go:163`、`:197`：V3列表固定空前缀查询和业务字段组装；`:328`、`:420`：目录删除与重命名依赖全后代列表。
- `g_web_installer/internal/service/image_gateway/client.go:237-265`：客户端ListAll查询、分页与响应模型。
- `private-service/internal/app/pkg/util/obs_artifact.go:90`：版本目录查找发送delimiter并解析common_prefixes的源码旁证。
- `g_web_installer/internal/service/image_gateway/client.go`：新增ListTopFolders；`internal/service/file_server/file_server_v3.go`：新增ListTopFoldersV3；`internal/transport/handler/file_server_v3.go`：新增ListObsTopFoldersV3；`internal/transport/router.go`：新增GET路由。
- 本轮本地HTTP替身用例、定向测试、真实cmd/server构建与格式/JSON检查直接输出；临时测试及构建产物已删除，未调用外部业务环境。
- 本次git commit/push直接输出、PR423提交/文件范围及正常合并结果、中央release fetch与祖先关系，以及121快进、编译替换、单次监听归属确认和启动脚本直接输出。

[返回案例索引](../README.md)
