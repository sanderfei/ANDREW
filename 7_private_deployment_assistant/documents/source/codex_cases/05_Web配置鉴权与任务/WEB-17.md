# WEB-17：离线三步骤复用 PID WebSocket 推送结束状态与自动衔接

项目：g_web_installer。记录日期：2026-10-21。记录状态：源码结论与方案设计（未实现），功能待验证。

适用环境：本地 `release` 工作区，HEAD 为 `e93910b`；本轮核对后端离线服务、通用命令执行器和日志 WebSocket，未连接测试服务器。适用于由 Web 后端进程启动 KK 的离线三步骤；Kubernetes/OS 版本不决定通知协议，容器或宿主机方式仍需按实际 Web 工作目录定位 `data`。工作区存在其他任务改动，本轮未修改业务代码。

## WEB-17 问题与表现

用户希望 `init registry` 真正执行成功或失败后主动通知前端；初始化成功时由前端自动调用镜像推送，再按需要衔接离线安装。候选方式为新增 SSE，或复用现有 PID WebSocket。

这是通知和流程设计需求，没有本次现场失败日志，不能将其描述为某个已复现的部署故障。

## WEB-17 已确认机制与边界

1. `InitRegistry`、`PushImages`、`OfflineInstallCluster` 都创建 `command.Execute` 异步任务并返回 `OfflineResponse.pid`。执行器在外部命令启动后释放调用方；HTTP 成功响应代表启动阶段成功，不代表 KK 已经执行结束。离线包缺失、前置脚本生成失败或命令启动失败仍直接通过原 HTTP 响应报错。
2. `internal/service/offline/offline.go:37` 已按 `ExecuteExitStatus.Success` 返回 `Registry initialized successfully` 或 `Failed to initialize registry`，镜像推送和离线安装也有类似提示。它们是结束提示文字，尚无专用的机器事件协议。
3. `internal/service/command/execute.go:202` 等待外部命令，使用等待结果判断命令成功；`PostExec` 返回错误还会将最终结果改为失败。现有 `Command Finished` 写在 `PostExec` 前面，不能把它当作最终成功事件。
4. `GET /api/v1/logs/cluster/{cluster}/tail/{pid}/execute.log` 经 `TailLog` 找到 `data/cluster/<cluster>/history/<pid>/execute.log`，由 `internal/service/log/tail.go:76` 逐行发送 WebSocket 文本消息。因此现有结束文字已能经日志通道送达在线订阅者。
5. tail 对超过 10000 字节的日志从末尾 10000 字节开始，较小日志从头开始。首次晚订阅和重连都会读取一定历史内容，结束事件可能再次到达；传输协议本身不保证后续业务只执行一次。
6. `success.json` 只保存成功记录；现有 `ReadTaskHistory` 没有按 PID 完整记录失败、取消等终态。`lock_owner.go` 的文件锁调用被注释，不能把 `processing` 或现有锁文件当作可靠的并发去重保证。

## WEB-17 补充：现有固定成功和失败日志（2026-10-21）

本轮复核环境：Web 本地 `release`，HEAD `1329551`。用户提供了三步的 `Command Finished` 与成功提示片段，希望找到固定的成功/失败文本用于识别；未提供本轮失败日志。下面列出当前已有输出，后文专用 JSON 事件仍是未实现建议。

| 步骤 / 任务类型 | 固定成功标记 | 固定失败标记 |
|---|---|---|
| 初始化仓库 / `init_registry` | `[ Registry initialized successfully ]` | `[ Failed to initialize registry ]` |
| 推送镜像 / `push_images` | `[ Images pushed successfully ]` | `[ Failed to push images ]` |
| 离线安装集群 / `offline_install` | `[ Cluster installed successfully (offline mode) ]` | `[ Failed to install cluster (offline mode) ]` |

已确认机制：

- 三组文本定义在 `internal/service/offline/offline.go:37`、`:76`、`:136` 的 `PostExec` 中，由 `ExecuteExitStatus.Success` 二选一返回，字符串内容固定且末尾有换行。成功前缀为 ANSI `\033[32m`，失败前缀为 `\033[31m`，方括号文本后带 `\033[0m` 复位符。
- `internal/service/command/execute.go:202` 等待外部命令；`:208` 先写 `Command Finished ************************************************`，成功或失败均会经过该处；`:212` 以 `waitErr == nil` 判断命令成功；`:247` 写入上述步骤提示。失败时还会写 `Command failed with error: <动态错误>`，动态部分不能当成固定整行。
- `internal/service/log/tail.go:77` 将每行日志加换行后作为 WebSocket 文本消息发送。匹配方括号固定片段可以避开颜色控制符；整行相等匹配前需去掉 ANSI 颜色与首尾空白。

可执行识别步骤：订阅本次接口返回 PID 对应的 `execute.log`，按该任务类型匹配表内完整成功或失败标记；成功标记表示该外部命令按现有退出判断成功。不要仅凭 `Command Finished`、任意 `success` 单词或连接关闭决定结果。日志重放可能再次出现同一 PID 的标记，自动发起后续操作仍需防重复。

错误边界：离线包不存在、前置任务失败或命令启动失败可能直接通过 HTTP 接口返回，未进入 `PostExec`，因此不能保证所有失败都出现表内失败提示；Web 进程中断也可能来不及写最终标记。尚未看到终态标记时，不能自动归类为失败。现有三步没有共用的一条结构化 `SUCCESS`/`FAILED` 终态行。

验证结果：用户提供的三条成功文本与当前源码一致，六个固定标记及其产生条件已核对；失败分支未现场执行，未修改业务代码或验证集群功能。现有文本能用于按 PID、按步骤识别命令结果；新增结束事件、幂等和自动衔接依旧未实现，元数据保持 `unverified`。

## WEB-17 建议方案（未实现）

优先复用 PID WebSocket，在现有文本日志末尾追加带固定前缀、单独一行的 JSON 事件。普通日志继续按原方式展示，消费者仅识别专用前缀。

示例为协议建议，不是当前接口的实际输出：

```text
__TASK_EVENT__:{"event":"task_finished","owner_type":"cluster","owner_name":"cluster-a","pid":"<本次初始化返回的pid>","task_type":"init_registry","status":"success","exit_code":0,"message":"Registry initialized successfully"}
```

失败使用同一事件结构，`status` 为 `failed`，携带实际退出码或无法取得时的空值，以及简明错误信息。不要把所有失败统一编造成退出码 1。消息必须在外部命令等待、`PostExec` 和最终结果处理后产生，不能在任意 KK 日志出现 `success`、HTTP 返回成功、WebSocket 关闭或 `Command Finished` 出现时提前产生。

建议的执行和消费步骤：

1. 调用已有初始化接口 `GET /api/v1/clusters/{cluster}/offline/init/registry`，记录返回 PID，订阅该 PID 的日志。
2. 执行器确定最终结果后，仅为本次任务写入一次结束事件；现有日志 tail 将该行推送给订阅者。
3. 消费者核对 `owner_name`、本次 PID、`task_type=init_registry`、`status=success` 和当前流程是否已处理；全部满足后调用 `GET /api/v1/clusters/{cluster}/offline/image/push`，记录新的 PID 并订阅其日志。
4. 初始化失败时停止流程并显示错误。镜像推送也使用同样协议；若需要三步全自动，仅在推送成功后调用 `GET /api/v1/clusters/{cluster}/offline/install`。
5. 关闭连接只表示通知链路中断，不能自动判为成功或失败。重连或打开历史日志时只更新展示，不应无条件重新启动后续操作。

把事件写入任务日志，可利用当前历史读取机制覆盖“任务先完成，浏览器后订阅”的普通情况。该机制不等于消息可靠投递保证：日志删除、事件后追加大量内容、服务异常退出前未写出终态等情况仍需独立处理；若需要完整按 PID 查询结果，可补充独立结果文件/查询接口。

当前页面内可按本次 PID 与流程状态防重复触发；要覆盖刷新、多标签页和重复请求，后端下一步接口还需要以来源任务 PID 做幂等校验，现有锁文件不提供该保证。这是进一步可靠性要求，不是已实现能力。

若要求浏览器关闭后仍继续推送或安装，应由后端串联步骤，WebSocket 负责展示进度。由前端调用下一步时，页面关闭就无法发起下一步。

## WEB-17 SSE 适用性

SSE 可通过独立 `text/event-stream` 接口发送同样的结束事件，使用 `event`、`data` 和可选的 `id`。浏览器 `EventSource` 支持重连及 `Last-Event-ID`，但服务端仍需维护事件或任务结果才能补发；单靠换成 SSE 不会获得业务去重、完整回放或脱离页面的流程执行能力。

本需求已有按 PID 展示日志的 WebSocket，复用日志通道的改动更集中。SSE 可用于将来单独的任务状态订阅，当前无需为同一个结束通知额外建设一套连接。

## WEB-17 验证结果与遗留事项

- 已核对当前后端启动返回、退出判断、结束文字、WebSocket 日志发送和历史读取路径，并核对 WHATWG SSE 与 Go `Cmd.Wait` 官方资料。
- 本轮只完成分析与本地案例归档；没有实现结束事件、后端幂等或自动串联，没有执行前端分析、业务测试、编译、部署或远端写操作。
- 后续实现需要验证初始化成功/失败、命令启动失败、快速结束后才订阅、重连重复事件、历史日志展示及下一步触发次数；取消/超时应按最终失败处理，服务进程中断不能伪造任务终态。
- 本轮没有真实自动衔接功能证据，元数据为 `unverified`。

## WEB-17 来源定位

- `g_web_installer/internal/service/offline/offline.go:16`、`:37`、`:53`、`:76`、`:92`。
- `g_web_installer/internal/transport/handler/offline.go`、`internal/model/reply/offline.go`。
- `g_web_installer/internal/service/command/execute.go:107`、`:199`、`:230`、`:247`。
- `g_web_installer/internal/transport/router.go:42`、`:70`；`internal/transport/handler/log.go:28`；`internal/service/log/tail.go:76`、`:94`。
- `g_web_installer/internal/service/command/read_task_status.go`、`success_tasks.go`、`lock_owner.go:19`。
- [WHATWG：Server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html)。
- [Go：os/exec.Cmd.Wait](https://pkg.go.dev/os/exec#Cmd.Wait)。

[返回案例索引](../README.md)
