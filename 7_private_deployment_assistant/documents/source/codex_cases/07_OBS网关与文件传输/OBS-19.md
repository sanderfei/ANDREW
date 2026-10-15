# OBS-19：本地未提交改动范围包含OBS落盘离线安装与镜像归档重命名

项目：g_web_installer / g_kube_installer。记录日期：2026-10-15。记录状态：源码结论（当前工作区 diff 核对，未运行功能验证）。

适用环境：Web release 工作区 HEAD 为 00a0d61，核对时为 11 个已跟踪文件修改、7 个未跟踪 Go 文件，暂存区为空；分支比本地 origin/release 引用多 1 个已提交记录，这不属于未提交 diff。结论只覆盖当前快照，不等同远端部署版本。

## OBS-19 问题与表现

用户确认当前所有未提交代码是否只涉及“OBS 下载到本地后接通离线安装包路径”与“离线镜像仓库导入本地已下载包”。

## OBS-19 最终定位与范围

Web 大部分改动属于这两条链路，但还包含已有镜像归档上传接口的可选 registry 重命名。完整业务范围为三组：

| 分组 | 当前源码行为 | 主要文件 |
|---|---|---|
| OBS 本地下载、列表及离线制品路径 | 下载到 Web 工作目录下 data/obs/local；本地列表返回相对 path；初始化离线仓库、推送制品镜像、离线建集群和离线加节点共用 kk/g_kube_installer-artifact.tar.gz | constants.go、service/cluster/node.go、service/offline/offline.go、obs_v3_local_download.go、obs_v3_local_list.go 及对应 handler |
| 本地镜像包导入固定 Zot | 接受 path 数组，只读取本地文件并异步导入固定离线 Zot；保留源文件，配套文件占用、路径限制、临时解压和取消/超时传递 | obs_v3_local_import.go、对应 handler、common/registry.go |
| 镜像归档上传 OBS 时可选改名 | 原 registry/upload 接口增加 is_rename、registry_name；按源引用拉取，在归档标签中替换 registry，保留仓库路径/tag；不向改名目标执行远端 push | request/obs.go、file_server_v3_registry.go、file_server_v3_upload.go、handler/file_server_v3.go |

reply/obs.go、obs_v3_middleware.go、router.go 是这些功能的模型、网关需求判断、HTTP 错误映射及路由配套；handler/offline.go 的变化为路径语义对应注释。没有在本轮差异中看到普通 OBS 上传超时修复、权限读取或应用配置重构等独立功能变更；已有相关历史提交不应算入未提交范围。

## OBS-19 具体路径与接口

```text
POST /api/v3/obs/file/download/local
  real_path：OBS 实际对象 key
  path：Web 本地 data/obs/local 下的相对文件路径

GET /api/v3/obs/file/local/list
  返回 [{"path":"相对路径"}, ...]

POST /api/v3/registry/images/import
  请求 [{"path":"相对路径"}, ...]
  目标 digiwin.gkubeinstaller.local:444，类型 Zot

POST /api/v3/obs/registry/upload
  新增可选 is_rename、registry_name
```

离线制品统一路径为：

```text
<Web进程工作目录>/data/obs/local/kk/g_kube_installer-artifact.tar.gz
```

它替代旧的按集群目录存放制品路径。下载调用者需把本地 path 指定为上述相对 kk 路径，下载接口本身不会把所有文件自动识别为 KK 制品。该安装制品与供 images/import 使用的 Docker-save 镜像归档是不同用途，不能把任意下载包直接当成可导入镜像。

## OBS-19 关键行为边界

- 本地下载使用临时文件完整写入后 rename；HTTP 成功响应还要满足完整下载与长度检查，任务 PID 返回不等于文件已下载完成。
- 本地列表跳过下载/导入临时文件、临时解包目录和符号链接，提供导入所需的相对 path。
- 导入先校验并占用整批文件，拒绝空数组、重复、占用、缺失或不合格文件；顺序处理各包，单包失败后继续，任一包失败时总体任务失败。源包保留，只清理临时产物。
- common/registry.go 新增带 Context 的入口，并把 Context 传递到 copy.Image；旧入口仍以 Background 调用，属于导入任务的配套变更，不是额外的 runtime 安装逻辑。
- is_rename 未开启时保持原标签；开启且未指定 registry_name 时采用默认离线仓库主机。拒绝 digest 改名、无效 registry 和不同源映射到同一目标。历史行为说明见 [OBS-17](OBS-17.md)，历史已归档不等于本地代码已提交。

## OBS-19 归档重命名对原前端的兼容性补充（2026-10-15）

用户继续确认可选 registry 重命名是否为增量功能、前端不修改是否影响原流程。本轮对照当前 diff 核对了请求绑定、分支、归档写入和响应，没有读取或修改前端代码，也没有执行接口回归。

- DockerPushV3Request 匿名嵌入原 DockerPushRequest，原 path、images、dingding、tar_name 仍位于请求 JSON 顶层，原 required 约束不变。
- 新增 IsRename bool、RegistryName string 均无 required；请求省略时分别为 false、空字符串。
- prepareRegistryArchiveImagesV3 先令 target = source，只在 IsRename 为 true 时校验目标 registry、检查 tag 引用并替换目标主机。false 时 registry_name 被忽略，归档使用原引用。
- saveImagesToTgz 仍按 source 获取远端镜像和原认证，以 target 为归档引用；未启用改名时两者相同。gzip/Docker-save 写入方式、原文件命名函数、OBS 上传目标拼接和返回 success/pid 的结构未改变。
- 新增非法目标 registry、digest 改名和目标碰撞的错误，仅在启用改名时发生。原有镜像引用合法性检查被提前到准备映射阶段；错误输入的校验先后可能变化，不应声称所有异常输入返回顺序完全相同。

| 请求情况 | 当前代码行为 |
|---|---|
| 旧前端不传新增字段 | 默认不改名，沿用原引用 |
| is_rename 为 false | 不改名，忽略 registry_name |
| is_rename 为 true 且指定 registry_name | 归档内仅替换 registry，源拉取地址及认证不变 |
| is_rename 为 true 且未指定 registry_name | 归档使用默认离线仓库主机 |

结论是：就镜像归档重命名这一项，原前端无需修改才能继续原流程；要启用新功能才需要提交对应参数。这是源码兼容性结论，不是当前工作区已完成真实打包、上传回归的证明。

不能将这一结论扩大为整个未提交变更均对旧流程无影响：离线安装链路已改为固定共享制品路径，旧流程若只在 data/cluster/<cluster>/ 中保留安装包，会触发“obs离线安装包未下载”；需确认新路径已备好完整制品。本轮未修改该业务逻辑。

补充源码：internal/model/request/obs.go:85-95；internal/transport/handler/file_server_v3.go:206-220；internal/service/file_server/file_server_v3_registry.go:25-60；file_server_v3_upload.go:246-333、355-400。

## OBS-19 其他仓库状态与处理方案

核对时 KK test 工作区另有 `cmd/kk/pkg/component/pinpoint.tgz` 已跟踪文件修改。本轮只读取 Git 状态，没有展开或比较该包，不声称其具体行为变更；它不是 Web 的上述 18 个文件之一。

andrew 另有案例及元数据、索引和 evaluations 等未提交内容，应与业务代码区分并保留。用户未要求提交、修复、发布，因此本轮只核对业务代码，按持续归档约定更新本地文档。

若后续要求提交，先按这三组业务范围确定提交集合，不能因文件名都包含 OBS 就把镜像归档重命名当成未涉及的功能；不能顺带提交 KK 的 Pinpoint 包或其他无关文档。此次审查不是接口契约完整性、测试、构建或发布验收。

## OBS-19 test 分支交付与本地验证补充（2026-10-15）

用户随后明确要求新建 test 分支并推送当前 Web 全部未提交代码。本次从 Web 当前 HEAD 新建本地 test，提交 `e901e0f2ff06cb0fe840dec0db17b7ddc0f6b384`，推送个人仓库 origin 的 `refs/heads/test`，并核对远端分支 SHA 与本地一致。Web 当前工作区与暂存区为空。

- 本次提交共 19 个文件：上述 18 个 Go 文件以及根目录 swag.json。swag.json 原来被 .gitignore 忽略，本次按内部 AGENTS.md 要求显式纳入；确认 basePath=/api/v3、新增三条路由和 registry/upload 参数已存在，definitions 无悬空引用，改名参数不属于 required。
- 本地临时行为测试使用 httptest 镜像仓库实际推送、拉取并生成 gzip/Docker-save 归档，核验 manifest.json 中 RepoTags：旧请求、不启用改名时忽略无效目标、显式改名、默认离线目标、零层镜像均通过。未访问真实 OBS 或离线 Zot。
- 文件生命周期测试确认下载长度不符时保留旧文件、完整文件发布后可被列表读取、重复占用导入被拒绝、释放后源文件保留。测试文件按约定在通过后删除，没有提交测试文件。
- changed Go files 的 gofmt、暂存 diff 检查通过。`CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o /tmp/g-web-installer-test-branch-20261015 ./cmd/server` 成功。
- 常规相关包 go test 遇到 internal/common/registry.go:109-110 的动态格式字符串 vet 报错；已对照 HEAD 证实这两行原先就存在，未修改。随后 `CGO_ENABLED=0 go test -vet=off -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./...` 通过；不能描述为所有 vet 检查通过。
- 仓库有同名 test 标签，短引用第一次推送产生歧义；改用 `git push -u origin refs/heads/test:refs/heads/test` 后成功。没有修改或覆盖标签，没有强推。
- 本次授权为 Web test 分支提交推送，没有合并 release、部署、更新 KK 的 Pinpoint 包，或提交 andrew 文档。历史功能验证和新测试分支交付分开记录。

### OBS-19 中央仓库目标补充（2026-10-15）

用户随后截图显示实际查看的是中央仓库 `Installation-package/g_web_installer`，而此前已推送的位置是个人仓库 `wangfei/g_web_installer`。两个 remote 指向不同仓库；个人仓库返回 Everything up-to-date 不能证明中央仓库已存在 test。

按用户澄清的目标，先查询 upstream 的 refs/heads/test 确认不存在，再执行 `git push upstream refs/heads/test:refs/heads/test`，成功在中央仓库创建 test 分支。随后用 `git ls-remote --heads upstream refs/heads/test` 核对远端提交为 `e901e0f2ff06cb0fe840dec0db17b7ddc0f6b384`，与本地一致。中央分支入口为 `http://192.168.3.34/Installation-package/g_web_installer/src/branch/test`。

这次只补推既有提交，没有产生新代码变更、合并 release 或部署。后续交付需明确报告仓库所有者和分支，不能只写“已推远端 test”。

## OBS-19 验证证据与限制

最初范围核对只读取 git status、完整已跟踪差异及全部 7 个新增 Go 文件，核对路由与实际消费路径，没有执行测试或构建；随后按用户新指令完成上述本地回归、构建与 test 分支交付。没有执行真实 OBS 网络请求、真实离线 Zot 推送、KK 安装或线上部署，完整业务链仍未验证，元数据保持 unverified。没有保存实际认证值到案例文档。

## OBS-19 来源定位

- 2026-10-15 本轮用户关于未提交代码范围的提问，以及本地 Git 工作区读取结果。
- `g_web_installer/internal/constants/constants.go:26`、`internal/service/cluster/node.go:15`、`internal/service/offline/offline.go:16`。
- `internal/service/file_server/obs_v3_local_download.go:25`、`obs_v3_local_list.go:17`、`obs_v3_local_import.go:34`、`file_server_v3_registry.go:25`、`file_server_v3_upload.go:246`。
- `internal/model/request/obs.go`、`internal/model/reply/obs.go`、`internal/common/registry.go:133`、`internal/transport/router.go:208` 及对应 handler。

[返回案例索引](../README.md)
