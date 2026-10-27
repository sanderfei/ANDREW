# KK-O04：离线制品的宿主机路径与容器路径不一致

项目：g_web_installer / g_kube_installer。记录状态：代码已验证（2026-10-20 双路径选包已合并 release，未部署）。来源会话起始日期：2026-10-13（含之后续问，不是本次现场检查日期）。本次补充日期：2026-10-20。

实现阶段适用环境：本地 Web `test` 分支，以 HEAD `e982a0f51e557d00caf4e6d66c7cc5820314eba2` 为基线完成本地修改。已 fetch 两个 remote，并执行 `git pull --ff-only upstream refs/heads/test`，确认当时中央仓库 `upstream/test` 已是该提交；随后按项目默认提交约定转到 `release` 完成交付，详见下文。没有连接测试服务器。路径由 Web 进程工作目录决定，宿主机运行和容器运行均应核对实际 cwd；容器外路径另外取决于挂载关系。

适用标签：Kubernetes any；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## KK-O04 问题与表现

包已复制到服务器，但 Web 提示缺少 artifact 或 please run InitRegistry first。

2026-10-20 续问：确认目前 OBS 离线集群安装使用的离线镜像包路径。本轮没有收到新的现场报错；当前代码中的缺包提示为 `obs离线安装包未下载`。

同日用户进一步要求拉取最新代码并优化：先用共享 OBS 本地包，不存在时使用对应集群目录内的同名包。此前只检查共享目录，导致仅保留旧集群包的环境被拒绝；本轮没有新的现场失败日志。

## KK-O04 最终根因或已确认边界

历史版本按进程工作目录读取 `data/cluster/<cluster>/g_kube_installer-artifact.tar.gz`；文件存在于别的目录或未映射的宿主机路径时不可见。历史提示不等于必须重复初始化仓库。

同日续问修改前目录时，已对照提交 `e901e0f` 及其父版本确认，原路径完整形式为 `<Web进程工作目录>/data/cluster/<集群名>/g_kube_installer-artifact.tar.gz`。父版本 `PushImages` 与 `OfflineInstallCluster` 都通过 `filepath.Join(clusterDir, "g_kube_installer-artifact.tar.gz")` 取包，因此每个集群从自己的目录读取；该提交将这些消费者改为共享 OBS 本地路径。

2026-10-20 最初核对时，基线源码统一读取共享 OBS 本地制品：

```text
<Web进程工作目录>/data/obs/local/kk/g_kube_installer-artifact.tar.gz
```

`GET_DATA_DIR()` 使用 `os.Getwd()` 加 `/data`，`GetOfflineArtifactPath()` 再拼接固定子目录和文件名。基线中的初始化离线仓库、推送镜像、离线安装集群和离线加节点均只使用该共享文件，因此仅有历史集群包时会缺包；这是本轮双路径选包优化所处理的源码边界。

## KK-O04 双路径选包优化（2026-10-20，已合并 release，未部署）

新增 `ResolveOfflineArtifactPath(clusterName)`，按下列顺序选择普通文件，并返回绝对路径供 KK 的 `-a` 参数使用：

```text
1. <Web进程工作目录>/data/obs/local/kk/g_kube_installer-artifact.tar.gz
2. <Web进程工作目录>/data/cluster/<集群名>/g_kube_installer-artifact.tar.gz
```

- 共享文件存在时始终优先使用；仅在文件不存在时查找对应集群，不能使用其他集群的包。
- 两个文件都不存在时，保留 `obs离线安装包未下载`。读取失败或路径不是普通文件时直接报出具体错误，不将其当成缺失继续选包。
- 初始化仓库、推送镜像、离线安装、离线加节点，以及初始化/推送脚本生成器均使用此解析函数。加节点预检和命令参数使用同一次选择结果。
- 推送脚本的集群目录和配置路径改为绝对路径并加引号，避免切换目录后再次相对解析，也支持工作目录包含空格。
- 只选择已有文件，不复制或自动下载制品；没有修改接口 URL、入参或前端。原有 `swag.json` 工作区改动保持不变。

## KK-O04 处理方案

1. 核对 Web 进程 cwd；容器部署时同时核对 Mounts。历史 root 安装脚本的映射为 `/root/g_web_installer_data` 到 `/g_web_installer/data`，具体部署以实际映射为准。
2. 使用 OBS 本地下载接口 `POST /api/v3/obs/file/download/local` 时，指定 `path` 为 `kk/g_kube_installer-artifact.tar.gz`，`real_path` 填实际 OBS 对象 key。若对象 key 正是 `kk/g_kube_installer-artifact.tar.gz`，两者可填写相同值；本地 `path` 不带前导 `/`。等待任务日志确认下载完成及正式文件落盘，PID 或 `success:true` 不能单独证明完成。
3. 在 Web 的实际工作目录执行 `ls -lh data/obs/local/kk/g_kube_installer-artifact.tar.gz data/cluster/<集群名>/g_kube_installer-artifact.tar.gz`，分别核对两个候选位置。应用本轮修改后的 Web 可直接使用已有集群包作为第二选择；优先位置有文件时仍使用优先位置。人工复制时任选一个符合目标版本的候选位置，避免共享旧包覆盖预期选择。已有共享镜像仓库仍需提供安装所用 artifact。

## KK-O04 验证证据与限制

2026-10-13 源码分析确认历史存在性检查，未验证当时客户路径。

2026-10-20 最初只核对源码路径；随后按用户明确要求实现双路径选包，并完成以下本地验证：

- `CGO_ENABLED=0 go test -count=1 -v -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' ./internal/constants ./internal/service/offline ./internal/service/cluster` 退出 0，无需关闭 vet。临时测试覆盖共享包独有、集群包独有、两者都有时共享优先、都缺失、其他集群隔离、目录误放和 stat 异常；覆盖六个入口/脚本生成器的缺包错误。另用无效配置阻止实际 KK 执行，确认离线安装和离线加节点在只有集群包时已通过选包检查并进入配置读取阶段。
- `CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o <临时目录>/server ./cmd/server` 退出 0，临时构建产物已清理。
- 修改文件的 `gofmt` 和 `git diff --check` 通过。两个临时测试文件在测试通过后按用户约定删除；最终仅保留三个后端 Go 文件改动。原有 `swag.json` 内容与本轮开始时一致。

未检查远端部署版本和真实制品完整性，未执行 OBS 下载、真实仓库初始化/镜像推送或集群安装。上述测试使用临时占位文件，仅证明路径选择和前置错误处理；元数据保持 `unverified`。实现阶段尚未提交，后续交付结果如下；没有部署本轮修改。

## KK-O04 提交与合并证据（2026-10-20）

用户随后要求“提交代码”，按项目默认流程从个人仓库 `wangfei/g_web_installer:release` 提交 PR，合入中央仓库 `Installation-package/g_web_installer:release`。

- 提交前核对中央 `release` 已包含此前的 `test` 功能，且三个目标 Go 文件及 `swag.json` 的基线内容一致；将本次修改带到最新 `release` 基线 `20b54475fd4f7375338765b3bf293a7715526225`。只暂存三个相关 Go 文件，原有 `swag.json` 改动保留在工作区，未纳入提交。
- 业务提交为 `b0030273199eaff4517f9ad4d468ad56a38cfd03`，共三个文件、48 行新增、19 行删除，已推送个人 `origin/release`。
- [PR #415](http://192.168.3.34/Installation-package/g_web_installer/pulls/415) 的文件列表再次核对为上述三个文件。提交状态接口返回零条 CI 检查记录，没有将其描述为 CI 通过；使用普通合并接口成功，PR 状态为 closed、merged=true，合并提交为 `e93910b4715970f7d883cb79b2757503c31148dc`。
- 合并后 fetch 并 fast-forward 本地 `release`，同步个人 `origin/release`；通过 `git ls-remote --heads` 确认个人与中央仓库的 `release` 均为该合并提交。业务提交是合并提交的祖先，合并后三个文件内容与业务提交一致。
- 本次提交复用实现阶段已通过的定向测试和服务构建，没有重复编译或测试。暂存差异、敏感信息及改动范围检查通过，最终 Web 工作区只剩原有 `swag.json` 修改。
- 本次完成 commit、push、PR 合并及远端代码核验，没有发布、重启、真实离线安装或将 andrew 案例文档提交到远端。

## KK-O04 来源定位

- Codex 会话 `01a1335b-0dc5-78f2-8722-2aa5f948ef7d`；始于 2026-10-13。可按本条标题及关键错误定位相关提问与后续结论。
- 2026-10-20 最终实现：`g_web_installer/internal/constants/constants.go:32-51`；`internal/service/offline/offline.go:16,53,92,152,197`；`internal/service/cluster/node.go:15-22,63-66`。
- OBS 本地下载路径：`g_web_installer/internal/service/file_server/obs_v3_local_download.go:24-34,67-76`。
- 修改前路径的 Git 证据：`git show 'e901e0f^:internal/service/offline/offline.go'` 第 48-51、88-91 行，以及 `git show e901e0f -- internal/service/offline/offline.go internal/constants/constants.go` 的路径替换差异。
- 交付证据：`git show b003027 --stat`；Gitea PR #415 的文件列表、普通合并响应与最终状态；个人及中央仓库 `refs/heads/release` 的 `git ls-remote --heads` 结果。

[返回案例索引](../README.md)
