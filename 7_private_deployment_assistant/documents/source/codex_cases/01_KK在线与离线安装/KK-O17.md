# KK-O17：轻量化离线安装因已有 Docker 数据目录不一致被预检阻止

项目：g_kube_installer。记录日期：2026-11-04。记录状态：现场预检结果已确认，安装及镜像推送待验证。

适用环境：测试机 121，CentOS 8，Docker 26.1.3，KK `tiny` 分支提交 `da595f9`；轻量化离线安装，配置使用 `kind: Docker`。机器已有 Docker、containerd 和 Zot 服务以及业务容器，不能视为空节点。

## KK-O17 问题与表现

已有 Docker 正常运行，实际数据目录为 `/var/lib/docker`；轻量化配置为目标节点指定 `dataDir: /data/tiny`。使用单节点配置和已构建的轻量化离线包执行：

```bash
./kk install docker-compose -f config-tiny.yaml -a tiny-artifact.tar.gz
```

流程在 `DockerPreflight` 阶段报已有 Docker 数据目录与配置目录不同，并拒绝迁移已有数据；命令退出码为 1。尚未进入 Docker/Compose 安装、Zot 初始化或镜像推送。

## KK-O17 已确认原因和边界

轻量化安装检查正常 Docker 的实际数据目录；当其与指定 `spec.hosts[].dataDir` 不一致时，会停止流程，避免自动切换或迁移已有 Docker 数据。该案例为安全预检阻断，不是 Docker 服务故障，也不是镜像推送失败。

另有只读发现：机器已有 Zot 服务和 444 监听，轻量化固定仓库域名已有非回环 hosts 映射；离线包包含 Ubuntu ISO，而目标系统为 CentOS 8。这些是继续安装前需要单独核实的条件，本次流程未进入对应预检或系统包安装，不能当作实际触发的错误；是否需要匹配的 CentOS 系统包 ISO 取决于节点缺少哪些依赖。

## KK-O17 处理建议

1. 优先使用独立空白节点验证完整轻量化安装及镜像推送，避免测试改变已有 Docker 的容器、网络或仓库配置。
2. 确需复用已有主机时，先核实目标 Docker 数据目录、正在运行的业务、仓库域名/端口和节点系统依赖。与现有数据目录一致只能消除本次预检冲突，不代表其他检查或后续安装必然成功。
3. 不为通过预检而直接停止 Docker、迁移或清理数据目录，也不覆盖正在使用的仓库域名解析。完整方案需结合实际业务和环境确认。
4. 如离线安装需要目标机缺失的系统包，提供匹配目标操作系统及架构的离线依赖；仅有其他系统的 ISO 不能保证满足依赖。

## KK-O17 验证证据与限制

- 同一执行机上先用只含一个 BusyBox 镜像的 manifest 构建轻量化包；构建成功，包内 Docker、Compose、Zot、两份 Ubuntu ISO 与 OCI 镜像内容和校验已检查。包内容检查不等同安装、镜像推送或业务运行成功。
- 安装命令实际停在 Docker 数据目录预检，未执行后续安装和推送；不能据此判断后续阶段的功能。
- 预检后只读检查显示 Docker、containerd、Zot 仍为 active，运行中 Docker 容器数量仍为 5；未重启或修改这些既有服务。
- 相关源码：`cmd/kk/pkg/compose/docker_engine.go` 的 Docker 预检、`cmd/kk/pkg/pipelines/install_docker_compose.go` 的模块顺序，以及 `cmd/kk/pkg/tinyzot/zot.go` 的本地仓库检查。实际后续行为需在安全目标节点验证。

[返回案例索引](../README.md)
