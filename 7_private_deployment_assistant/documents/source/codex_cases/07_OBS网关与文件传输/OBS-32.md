# OBS-32：版本镜像导入Registry层PATCH触发Zot读超时

项目：g_web_installer / Zot。记录日期：2026-10-29（Asia/Shanghai）。记录状态：push容错PR429已合并并启动121；Zot超时未修，真实容错导入待验证。

适用环境：121 Web版本导入任务（PID尾7c272993）向214:444离线Zot推送镜像。Zot为 `v2.1.21-0-g6429ce6`。121日志采用UTC-04；01:39:41对应UTC05:39:41、上海13:39:41，不把原时间当CST。最初故障取证为只读；随后Webworker容错经290fd15/PR429交付121，没有修改214Zot配置、重启或重新上传。

## OBS-32 问题现象与失败阶段

首镜像tgz通过CDN完整下载4,520,712,744字节并预检通过，随后按包内7个tag串行copy。121原时间01:37:59开始copy，前三tag在进入下一条前已成功返回；01:38:37开始rag-parse，01:39:41报告其某层PATCH `connection reset by peer`，约64秒后整包失败。汇总downloaded=1、validated=1、images_imported=0、databases_imported=0。

`images_imported=0`计的是整个镜像包完成数，不代表没有镜像或层写入；前三tag copy已成功，失败层也可能留下部分远端副作用。数据库阶段未执行。本次是Web向Registry上传层失败，不是CDN下载失败；包结构预检和前三copy通过，尚无结构错误证据，但也不能据此认定包中所有镜像或最终导入均成功。

## OBS-32 已确认根因与服务端闭环

214 `/etc/zot/config.json` 的http仅显式address/port444，没有readTimeout/writeTimeout等覆盖值；与实际2.1.21版本匹配的官方文档说明HTTP读写默认60秒。

服务端同goroutine474、同上传连接与客户端失败UUID形成闭环：

| Zot主日志UTC | 现场结果 |
|---|---|
| 05:39:32.193119 | `read tcp 214:444 -> 121:33462: i/o timeout`；Zot自身时间为13:39:32.192919+08，记录unexpected error并移除该上传临时文件。 |
| 05:39:32.685698 | 与客户端相同上传UUID的PATCH返回500，latency为1m0s；Zot自身时间13:39:32.449415+08。另一个并发UUID也有同类PATCH500/1m0s和read timeout。 |

因此本次直接失败点是Zot读取upload body超过默认60秒，随后连接重置被Web看到。尚未确定该层为何未在60秒内完成；不能进一步无证据定为链路限速、丢包、包损坏或OOM。客户端tag开始到最终错误的64秒也不是该PATCH精确耗时：containers/image会等待并发层结束后返回错误，超时判断以Zot单请求latency和同UUID/连接为准。

源码确认包/tag串行，但containers/image单镜像默认最多6层并发；当前没有带body PATCH的自动重试或offset保存。readiness的10秒context与copy父context隔离，客户端没有对应60秒写总期限。121配置白名单值metadata=30、transfer=21600、async=43200秒，与当前发布源码一致，不是这次一分钟body读超时的来源。

## OBS-32 其他现场边界

121失败后work已清、packages只保留该原包，检查时空闲约52.42GiB。214 Zot NRestarts=0、自10月21日运行，所查kernel窗口无事件；当前存储余约54.86GB、可用inode6,244,993。后两项仅为检查时快照，不倒推故障时磁盘状态；现有直接证据是同请求read timeout，不把当前容量或没有重启作为独立的全局无故障保证。

## OBS-32 处理建议（未执行）

可评审提高Zot `http.readTimeout` / `http.writeTimeout`，例如30m作为大镜像/慢传输的待审起点，再按实际配置生效机制处理并在需要时重启Zot、核对生效后有限重试失败镜像。本轮没有config-watch取证，不承诺修改JSON会自动生效，也不建议以禁用超时替代有界配置。

现一键入口重跑会生成新PID并重新下载，不提供自动断点续传或现成的原包复用；“复用保留原包重试失败镜像”仅是运维/后续代码建议，不能写为已实现。完整恢复仍需目标manifest/镜像可用性及整包任务终态证据，前三tag/层成功不等于全版导入通过。

214Zot超时配置未修改，没有重启或重传；下节Web容错已交付121，不修复60秒读超时，也未验证整体导入恢复，metadata保持 `unverified`。

## OBS-32 2026-10-29 普通镜像push失败继续（PR429已交付121）

用户要求推送失败输出日志并继续后续数据，本地仅放宽 `importImage` 普通非context错误：记录Error、按镜像包计 `images_failed`，完成cleanup后继续下一镜像包和数据阶段。不是按tag/层计失败，也不增加重试；readySkip不计为push失败。下载、prepare、cleanup、DBRun真实错误及context取消/截止仍终止，父取消优先，不改单PID或通用ObsExecutor。

summary保持旧字段顺序、末尾追加images_failed，无DB也由defer输出；有失败时额外Error：`[镜像推送汇总] N个镜像包推送失败，后续步骤执行结果见上述日志；流程结束不代表所有镜像均已导入。` 若后续无fatal则run返回nil只表示调度流程结束，通用executor输出文案不变，不能据其结束/成功文字宣称所有镜像均成功，须读失败明细及汇总。

仅 `obs_v3_version_import.go` 本地改动。定向测试覆盖push失败→cleanup→后续包/DB顺序、多失败/无DB、汇总、readySkip、各fatal及context边界；focused、整包race、CGO0三tags server构建、gofmt/diff均通过，临时测试与构建产物删除。随后已commit/push并经PR429合并、完成121编译替换启动，见下节；未做新容错流程真实导入，214Zot60秒配置未动，metadata仍为 `unverified`。

## OBS-32 2026-10-29 PR429交付

仅该业务源码提交 `290fd150f03af9f72c5a825fd2d89eb9ac5ccc37` 并推送origin/release；[中央PR429](http://192.168.3.34/Installation-package/g_web_installer/pulls/429) 合并为 `98af373bfb6b836221987290cce8347027fd0440`，fetch/merge-base确认祖先。121固定SSH从a024faf经ff-only更新到98af373并确认含源提交，保留data、router后端模式和users本地变更；CGO0三tags构建server.next并mv成功。一次ss定位8080旧PID2689696、一次exe/cwd核对后kill9，立即web_start.sh，输出 `server started, pid=2715819`、`startup_command_succeeded:true`，SSH退出0。没有追加API/端口/日志/哈希检查或触发导入，KK及214Zot未改；服务启动不代表真实故障后继续数据已验证，metadata保持 `unverified`。

## OBS-32 来源定位与相关案例

- 121精准版本execute及packages/work结果，214实际zot版本、http配置白名单、同goroutine/上传UUID和连接的PATCH500/read-timeout日志；只存脱敏摘要，不存上传会话参数或凭据。
- 当前 `internal/service/file_server/obs_version_images.go`、`internal/common/registry.go` 及containers/image上传实现：包/tag顺序、层并发、copy错误等待与重试边界。
- [Zot v2.1.21安全配置说明](https://zotregistry.dev/v2.1.21/articles/security-posture/)：默认读写60秒及大镜像/慢网络调整http.readTimeout/writeTimeout。
- [OBS-29](OBS-29.md) 是下载HTTP2正文重置、[OBS-30](OBS-30.md) 是本地ENOSPC、[OBS-31](OBS-31.md) 是组件配置，均非本次Registry PATCH读超时；[OBS-05](OBS-05.md) 的前端同步窗口也不能代用。

[返回案例索引](../README.md)
