# REL-06：错误发布仓库路径或构建旧分支

项目：g_kube_installer / g_web_installer。更新日期：2026-10-19。记录状态：历史状态验证；2026-10-19 已完成 Web test 分支构建、替换及启动命令，业务功能待验证。历史来源会话起始日期：2026-08-04, 2026-09-28（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REL-06 问题与表现

按旧目录拉代码/编译后发现实际Web调用的仓库与二进制不是该份。

## REL-06 最终根因或已确认边界

历史121存在多份checkout、多个发布路径，旧规则和当前服务cwd可不同。git当前分支不代表运行进程使用版本。

## REL-06 处理方案

发布前确认已合并目标、源checkout和实际执行路径。当前约定KK /root/wfkk/g_kube_installer、Web /root/wfweb/g_web_installer；保留data/config及目标本地变更。编译复制启动成功只算交付，需专项业务验证才算功能通过。

## REL-06 验证证据与限制

历史误路径还原及正确121发布记录；2026-10-19 的实际发布结果另见下节。

以上为历史归档结论。以下补充来自 2026-10-19 的 121 现场操作，不将新记录计入历史扫描统计。

## REL-06 121 切换 test 发布 V3 local 业务（2026-10-19）

### 问题表现与适用环境

用户先询问 Web V3 新增 local 业务是否已经发布到 121，随后明确要求将 121 Web 切换到 test 分支并发布。目标是 `ssh codex-test-121` 上的宿主机后端进程，源码及持久数据位于 `/root/wfweb/g_web_installer`，启动脚本为 `/root/wfweb/web_start.sh`。本轮未核实 OS 或 Kubernetes 版本，不据此扩大适用范围。

### 已确认原因与关键证据

- 发布前 121 源码位于 release，HEAD 为 `00a0d614f96919ca05d7036478c24f76ac453081`；中央仓库 `Installation-package/g_web_installer` 的 test 分支指向 `e901e0f2ff06cb0fe840dec0db17b7ddc0f6b384`。前者是后者的祖先，但尚未包含这次 local 新增提交。源码检出状态不能独立证明旧进程实际二进制包含哪些功能，本轮没有反向审计旧二进制。
- `git diff HEAD refs/remotes/origin/test -- internal/transport/router.go` 确认目标分支新增 `POST /api/v3/obs/file/download/local`、`GET /api/v3/obs/file/local/list`、`POST /api/v3/registry/images/import`；同一提交还接通共享离线制品路径。业务范围见 [OBS-19](../07_OBS网关与文件传输/OBS-19.md)。
- 121 原有 `configs/users.json` 修改，以及 router.go 中移除 Vue import、`vue.ServeVue` 的后端专用调整；data、server、server.pid 为目标机已有文件。本轮保留配置内容和 data，只基于 test 最新 router.go 重新应用两处 Vue 调整。
- 该 checkout 原本只配置 `+refs/heads/release:refs/remotes/origin/release`。首次为 test 设置跟踪时出现 `Cannot setup tracking information; starting point 'origin/test' is not a branch`；补充 test fetch 映射后成功。仓库另有同名 test 标签，后续拉取明确使用 `refs/heads/test`，避免短名称选中标签。

### 已执行解决步骤

1. 核对中央仓库的 `refs/heads/test`，并在 121 获取为 `refs/remotes/origin/test`。仅在缺少映射时补充：

   ```bash
   git config --add remote.origin.fetch '+refs/heads/test:refs/remotes/origin/test'
   git fetch origin refs/heads/test:refs/remotes/origin/test
   ```

2. 保留现有配置及 router.go 两处本地调整后，创建并切换本地 test，基于新分支 router.go 重新移除 Vue import 和 `vue.ServeVue`；没有把旧 router.go 整文件覆盖到新分支。随后执行 `git pull --ff-only origin refs/heads/test`，核对 HEAD 与 origin/test 均为 `e901e0f2ff06cb0fe840dec0db17b7ddc0f6b384`。配置内容保留检查及 `git diff --check` 通过。
3. 在登录 Shell、Web 目录构建并替换，构建成功前保留旧进程：

   ```bash
   CGO_ENABLED=0 go build -tags 'exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp' -o server.next ./cmd/server
   mv -f server.next server
   ```

4. 通过 `ss -H -ltnp 'sport = :8080'` 找到旧 PID，仅核对一次 cwd 和 exe 归属。确认是目标 Web 后执行 `kill -9`，随后立即运行 `/root/wfweb/web_start.sh`。本轮发布对象仅为 Web。

### 验证结果与遗留事项

- test 源码与中央分支一致；提交新增内容的敏感字面量粗查没有命中候选，不作为不存在敏感内容的完整证明。
- Go 编译和 `mv` 替换命令退出 0，直接输出 `BUILD_AND_REPLACE_OK`。
- 8080 旧 PID 为 `3419697`，cwd 为 `/root/wfweb/g_web_installer`，exe 为该目录 `server (deleted)`，与替换后的旧运行进程相符。
- 启动脚本退出 0，直接输出 `server started, pid=692339`。这只确认启动命令成功，不代表已验证业务功能或后续进程存活。
- 按发布约定未重复执行测试、接口请求、日志关键字检查或多轮进程/端口探测；未执行 OBS 下载、local 列表、Zot 导入或离线安装的实际功能验证。元数据保持 `unverified`；后续需要对应业务任务、文件或镜像结果才能认定功能通过。

## REL-06 来源定位

- Codex 会话 `019fca60-203c-77e3-aede-263fd60b5a7a`；始于 2026-08-04。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a0e6f2-f37c-73c2-b321-b2dc9fa01916`；始于 2026-09-28。可按本条标题及关键错误定位相关提问与后续结论。
- 2026-10-19：本地 `git ls-remote upstream refs/heads/test`、121 的 Git 分支/远端/差异结果及构建、替换、启动命令直接输出；仅记录脱敏后的结论。
- `g_web_installer/AGENTS.md` 的 121 发布约定，以及用户本轮明确要求切换 test 分支的指令。
- 121 `/root/wfweb/web_start.sh`：从目标 Web 目录启动已编译的 server，写入 logs/server.log 和 server.pid。

[返回案例索引](../README.md)
