# OBS-30：121版本包下载ENOSPC与保留组件的磁盘清理

项目：g_web_installer。记录日期：2026-10-29（Asia/Shanghai客户端日期）；故障日志保留原2026-10-28时间。记录状态：5个历史版本下载目录已清理，history/config保留；业务恢复未验证。

适用环境：用户最终确认清理目标为121，固定使用 `codex-test-121`；Web工作目录 `/root/wfweb/g_web_installer`，根文件系统XFS，总102,432,555,008字节。用户最初提到214，纠正前仅只读，未在214清理。本条为本地文件系统ENOSPC，与 [OBS-29](OBS-29.md) 的HTTP2对端断流分别记录，不沿用其网关根因。

## OBS-30 问题现象与原因

用户 `k8s_test` 版本导入日志于2026-10-28 21:10:12开始，21:11:27首包写 `/root/wfweb/g_web_installer/data/cluster/k8s_test/obs-import/<本次PID>/packages/*.part` 时报 `no space left on device`。121初次只读已匹配该精准任务终态：downloaded、validated、images及data计数全0，未进入后续包预检或导入。

这是本地临时下载文件写入空间不足，不是OBS对象审核、HTTP2 peer、数据库认证或组件安装状态错误。检查时根分区 `df -h` 显示约96G总量、94G已用、98%使用率、可用约2.3G；实际清理前可用2,425,769,984字节，inode使用率24%，没有inode耗尽证据。

后续检查时history已为空，原因未确定，本轮没有删除history日志；该21:10失败任务packages也为空。因此保留最初精准日志核对结论，不把后来目录空缺归因为本轮清理，也不虚构旧任务结果。

## OBS-30 首轮已执行清理范围

用户要求清盘且保留组件/K8s。操作前确认没有go/compile/link构建进程；Web为PID2084894，docker/containerd/zot active，kubelet原本inactive。组件、数据库、PV、registry、运行时images/volumes、配置及源码均保护，没有执行prune。

第一阶段：

```bash
GOTOOLCHAIN=local GOCACHE=/root/.cache/go-build /usr/local/go/bin/go clean -cache
```

命令退出0，仅清Go编译缓存，Go module下载zip约1.34GiB和解压源码保留。另精确删除旧01:54版本任务下无任何进程FD引用的 `.v3-download-3682732193.part`，逻辑大小354,991,548字节、分配354,992,128字节。两项后可用空间从2,425,769,984增至3,757,170,688字节，增1,331,400,704字节。

第二阶段先完整inspect旧06:32:48版本任务packages，确认以下3个tgz为regular、nlink=1、大小固定、无进程打开，3个version锁均无人持有；只删除这3个历史镜像下载副本：

| 镜像包版本后缀（业务前缀脱敏） | 逻辑字节 | 分配字节 |
|---|---:|---:|
| `1.6.7-20261022.tgz` | 4,520,712,744 | 4,520,714,240 |
| `1.6.7-20261027.tgz` | 1,038,003,091 | 1,038,004,224 |
| `1.6.7.tgz` | 7,157,593,887 | 7,157,600,256 |

分配合计12,716,318,720字节。历史终态日志已缺失，只能称无活跃引用的历史镜像下载副本，不能断言该旧任务曾成功。保留同目录ElasticSearch/MongoDB两个原始数据包，以及除精确3个tgz外的其他完整原包。第二阶段前后可用空间为3,757,121,536→16,473,444,352字节。

Docker build cache仅1.543MB，未清；没有删除Docker/containerd images、volumes、registry、K8s/PV、组件或DB数据。只对本轮自身慢du统计进程发送TERM停止扫描，没有停止服务进程；未进行代码修改、构建或发布。

## OBS-30 首轮结果与验证边界

- 最终 `df -h` 根分区约96G总量、81G已用、16G可用、84%使用率；实际可用16,473,444,352字节（约15.34GiB），比最初清理前增加14,047,674,368字节（约13.08GiB）。
- 后验Web仍为PID2084894，cwd/exe归属保持，未重启；docker/containerd/zot仍active，kubelet仍为原先inactive。本轮没有操作组件存储或运行时资源，这些状态检查不等同全部组件业务读写验证。
- 清盘目标已实际完成；没有重新触发版本包下载或数据/镜像导入，不能称该任务已恢复，也不能保证剩余空间覆盖所有包、工作副本和解包峰值。
- 后续重试前应按该版本的完整包与工作空间需求确认容量；是否重试及进一步清理按用户授权执行。metadata保持 `unverified`，不把空间释放或服务进程未变写成导入成功。

## OBS-30 2026-10-29 第二轮扩大清理与保护校验

用户追加要求保留 `/root/wfkk`、`/root/wfweb` 及相关运行资源，并在异步答复中明确允许删除整个旧 `/root/code`，包含未提交源码和旧data；本轮不只是缓存清理。执行前核对全/proc的cwd/exe/fd、全部6个Docker容器及额外containerd/moby挂载、181个systemd路径、两个保护树的symlink、Git common-dir/alternates、Go local-replace/go.work及构建/启动脚本，均无旧code引用；没有嵌套mount。nfs-server active但 `/proc/fs/nfsd/exports` 为空，NFS/Samba配置及已安装工具链接也无code引用。

| 批次 | 实际删除范围 | 可用字节前后 |
|---|---|---|
| 第一批，11个精确路径 | 旧VSCode Stable/Go扩展0.55和0.56、VSCode缓存/日志、Antigravity日志、nvm/npm/pip下载缓存、dnf缓存及旧 `/tmp/velero-install`。已确认mc/obsutil/velero独立安装于 `/usr/local/bin`。 | 16,472,838,144→17,005,641,728，增532,803,584。 |
| 第二批 | 获授权的整个 `/root/code`、旧模块缓存 `/root/temp/build-temp`、`/root/kubekey` 的8个executables调试ELF及 `/root/deploy-backups` 的2个旧KK ELF；后两目录只删精确文件，其他子目录/YAML保留。 | 17,004,863,488→31,636,381,696，增14,631,518,208。 |

运行中挂载的 `/root/kuboard-spray-data`、`/root/kuboard` 以及runtime/registry/PV/DB保留；`/root/go` 模块源码、ZIP、工具链，当前Node/IDE、账户和SSH等必要配置保留。没有停止或重启服务、prune、删除镜像/volume、修改保护两树或进行业务代码/Git发布操作。

最终 `df -h` 显示约96G总量、66G已用、30G可用、70%使用率；statvfs可用31,636,402,176字节（约29.46GiB）。相对本轮起点16,468,910,080字节，额外净增15,167,492,096字节（约14.13GiB）；首轮98%→84%，本轮84%→70%。分批空间为各自检查快照，当前可用以最终statvfs为准。

后验6个关键文件（wfweb的server/router/start、wfkk的bin/kk与manifest/kk、`/g_web_installer/kk`）SHA与本轮baseline一致；Web仍PID2084894，docker/containerd/zot/nfs-server active，5个running Docker的ID/name与baseline相同、全部容器仍6个，备份的两个YAML仍在。清理及保护校验已完成，没有触发版本导入，也没有组件业务读写或解包峰值验证；历史ENOSPC与HTTP2结论不变，metadata继续为 `unverified`。

## OBS-30 后续任务：下载完成后第三镜像解压预检再次ENOSPC

用户日志原时间2026-10-28 21:59:55开始的 `k8s_test` 版本任务，选择台湾 `url_tw` / CDN线路；22:08:05五个包全部下载完成，前两个镜像预检成功，22:14:55第三镜像写 `work/003/.version-image-1455738661.tar` 报 `no space left on device`。精准execute末尾与用户日志匹配：packages=5、downloaded=5、validated=2、images/data=0、skipped=9、unapproved=4。

本次五包CDN下载确已通过；失败是本地完整展开tar的写入，不是CDN下载失败或ES/Mongo导入脚本错误。尚未开始镜像推送和数据库导入，整体任务仍失败；本次121下载事实也不证明 [OBS-29](OBS-29.md) 的214旧HTTP2问题已经恢复。

源码 `prepareVersionImageArchive` 先将gzip完整解压、`io.Copy` 到私有未压缩tar，再验证；总流程先下载全部原包，预检后保留每个imagePath，单包cleanup延迟到总函数结束。因此即使串行预检，磁盘上也会叠加所有原包、已预检的未压缩tar和当前正在展开的tar，并不是任一时刻只占一个镜像包。

预检失败后首次只读核对root/data/task/packages均为同一根文件系统（st_dev=64768），总102,432,555,008字节；该快照可用18,841,202,688字节（约17.55GiB）。当时五个原包全在：三个镜像逻辑大小4,520,712,744、1,038,003,091、7,157,593,887字节，加两个数据包6,231及86,270字节，合计12,716,402,223字节（约11.84GiB），分配12,716,412,928字节。work当前已不存在，与总目录失败后 `defer RemoveAll` 清理一致。

当前空闲空间不能当作故障瞬间余量，未测得解压后各tar的准确GB，不编造峰值。前轮清盘后的29.46GiB仅是当时结果，未保证足够覆盖原包加全部预检展开峰值。

此前全量预检后二次准备的本地原型未发布，已被用户新要求覆盖；现改为镜像每包一次prepare后立即导入/清理，再逐数据组件检查后执行，不再保留全版预检屏障。原包/DB副本/内层bundle仍需空间，纯流式验证仍需另行设计。

本轮仅分析与只读取证，没有改代码、删除文件、清盘、发布或触发重试，保护目录wfkk/wfweb没有写入。直接重发会生成新PID并重新下载，旧原包仍保留，可能继续累积；应先处理预检空间峰值，不把重复提交当成修复。CDN五包下载是局部已验证事实，整体导入未成功，metadata继续为 `unverified`。

## OBS-30 2026-10-29 继续清理及精确删除失败任务原包

用户明确要求121测试机保留wfkk/wfweb，继续清除非必要内容，并追加要求删除刚才任务已下载本地文件。完成关联预检后实际清理如下；保护目录、运行依赖及配置保持：

| 范围 | 已完成动作 |
|---|---|
| 闲置目录 | 删除无proc/mount/NFS或保护树关联的 `/root/bak`、`/root/repository`、`/root/kubekey`、`/root/component`、`/root/temp`、`/root/deploy-backups`；新授权不再保留其旧配置样本/ISO缓存。另删无引用旧 `/root/k8s_test`、`/root/rabbitmq`、`/root/golang`、`/root/linux_amd64_v1_56_0`，其中k8s_test是旧测试拷贝，不是当前WF data集群。 |
| Docker旧镜像/构建缓存 | 逐个non-force image rm无容器引用的旧测试镜像和3个无引用旧WF版本，默认dangling image prune及unused builder prune；未使用image prune -a。镜像48→7，实际清41个旧镜像，保留current latest与全部6容器引用；build cache42→0。未删container、volume或registry存储。 |
| 闲置IDE服务器二进制 | 删除无引用 `/root/.vscode-server/cli/servers`、`/root/.antigravity-server/bin`；User/Machine、账户及必要配置保留。 |
| 精准失败任务packages | 先确认21:59任务execute为failure/completed、downloaded=5而images/data=0，五文件大小匹配且无FD引用；按用户追加授权删除该PID的3个tgz与ES/MongoDB两个tar.gz原包，逻辑12,716,402,223字节、分配12,716,412,928字节。packages现空，任务日志及当前cluster配置保留。 |

本轮起点可用18,840,227,840字节（约17.55GiB），最终statvfs可用61,737,250,816字节（约57.50GiB），净增42,897,022,976字节（约39.95GiB）；df约96G总、38G已用、58G可用、40%使用率。该空间结果是实际清理完成事实，不是只提出预检优化建议。

后验6个受保护文件SHA仍一致，wfkk/wfweb及当前cluster配置保留；Web仍PID2084894，docker/containerd/zot/nfs-server active，5个running容器ID与总6容器不变，没有停止或重启服务。`/root/go`/工具链、运行挂载数据和账户SSH/.kube/.docker等必要配置保留。没有业务代码、Git发布或新下载/导入操作；五包CDN成功和第三tar预检失败的历史仍成立，删除原包不等于导入恢复，metadata仍为 `unverified`。

## OBS-30 2026-10-29 新任务跟踪与本地空间优化

清盘后22:38任务（PID尾 `83109a4c`）用旧PR427/bc6运行，五包于22:45:46全部下载、三镜像预检全部通过，本次没有再次ENOSPC；22:54:35在ES数据包因 `component elastic is not configured in cluster k8s_test` 终止，downloaded=5、validated=3、images/data=0。该配置根因独立归档 [OBS-31](OBS-31.md)，不能继续归因磁盘或将Mongo未执行称为单独跳过。

旧代码三份展开tar同时保留，采样分配最多24,977,657,856字节（约23.26GiB）、采样空闲最少24,040,017,920字节（约22.39GiB）；失败后work为0、空闲49,019,375,616字节（约45.65GiB）。这些是采样及结束后状态，不是新优化效果；本次所有原包和日志保留，未再次清盘/重试或修改远端环境。

逐镜像下载/一次prepare/import/cleanup及逐组件readiness跳过策略已通过PR428合并并完成121编译替换启动；开发normal/race/build证据见OBS-28，没有新流程现场导入。旧两阶段准备原型已撤回，原ENOSPC及后续旧版配置失败分别保留。

新策略现已提交、合并并发布121；旧版终态由配置缺失触发，与此前ENOSPC分别记录，新流程业务和导入恢复仍未验证。

## OBS-30 2026-10-29 明确授权删除83109a4c任务

用户单独要求删除刚结束的83109a4c PID及对应下载，已精确删除 `cluster/k8s_test/history/<pid>` 和 `obs-import/<pid>` 两个目录，路径已不存在，当前 `config.yaml` 保留。空闲约45.65→57.49GiB；Web仍PID2084894，无重启，进程原持终态execute.log FD继续存在。这不是新流程自动删除history，也没有重跑导入。旧任务五包下载成功、配置失败及本轮清理事实均保留，metadata为 `unverified`。

PR428/`a024faf`发布使用新Web PID2689696，原data和配置本地改动保留；没有重新下载、导入或追加清理，本案例的空间及83109a4c删除记录保持历史事实。

## OBS-30 2026-10-29 再次按接口范围清理历史下载

用户要求删除121版本导入接口的历史下载，仅精确删除 `k8s_test/obs-import/` 下5个旧任务目录（PID脱敏尾缀9cbcbe01、84d952cb、c808436d、58978c3f、7c272993）。其中2个有Completed结束记录；3个为无对应cluster/obs日志的旧孤立目录，递归最新mtime早于当前Web启动，不能据此判定其历史导入成功。5目录均通过realpath安全检查且无/proc cwd/exe/fd引用，再删除下载/工作目录。

SSH退出0，5路径现均不存在；移除分配空间约4.210GiB，空闲约52.41→56.62GiB。现有2份history execute.log的inode/size保持，config.yaml的inode/size/mtime_ns保持；Web仍PID2715819，未kill/restart、修改代码或触发新导入。此次与先前单独授权删除83109a4c历史日志不同，history日志明确保留；不代表新流程自动删除原包或业务恢复，metadata仍为 `unverified`。

## OBS-30 来源定位

- 继续清理的实际删除清单、Docker image/container/cache前后IDs与数量、精准21:59任务终态及文件FD/大小核对、最终statvfs/df与保护文件/服务后验；[Docker image prune官方说明](https://docs.docker.com/reference/cli/docker/image/prune/)（默认只处理dangling）。

- 后续任务的精准execute及packages/work/df同设备结果；故障版本 `internal/service/file_server/obs_version_images.go:55-79`（完整解压tar）、`obs_v3_version_import.go:325-330`（全部下载）、`:352-355`（延迟清理）、`:363`（保留imagePath）、`:316`（work总目录清理）。

- 用户首包 `.part` 写入ENOSPC日志及121最初精准execute终态只读核对；后续history空缺原因未定。
- 121根XFS的df字节/inode结果，清理前构建进程、Web归属与服务状态；旧01:54part和06:32packages的stat、FD及version锁核对。
- 实际 `go clean -cache` 退出0与精确删除文件清单、两阶段空间及最终服务状态结果；不保存原始完整日志、姓名段PID或业务对象前缀。
- [OBS-28](OBS-28.md) 说明版本任务、私有packages/work与包导入阶段；本条记录独立磁盘故障和实际清理，不修改其已发布功能事实。

[返回案例索引](../README.md)
