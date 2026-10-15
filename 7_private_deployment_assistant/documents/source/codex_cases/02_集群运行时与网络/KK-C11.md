# KK-C11：离线节点重新加入时containerd2.2.1仓库配置冲突导致CRI缺失

项目：g_kube_installer / g_web_installer。记录日期：2026-10-15。记录状态：待验证（直接故障原因已确认，修复后拉取及重新加入未验证）。用户提供的关键启动日志发生于 2026-10-14。

适用环境：客户 worker 曾加入集群、移除后再次加入；运行中的 containerd 为 2.2.1，配置格式为 version = 2。对照环境 214/master、215/worker 的服务端版本均为 1.7.13。客户 Kubernetes、OS 的准确版本未提供，不能仅根据 pause:3.10 推断。当前本地 KK test 源码 HEAD 为 9094b52；客户执行的 KK 与离线包内容未核实。

## KK-C11 问题与表现

添加节点在 AddNodesPipeline 的 PullModule / PullImages 阶段失败，crictl pull 尚未访问离线私仓就退出：

```text
unknown service runtime.v1.ImageService
```

用户提供的 ctr version 确认 Client、Server 均为 2.2.1；查询 CRI 插件没有输出。config.toml 没有显式 disabled_plugins = ["cri"]，但存在旧式 registry.mirrors 及 registry.configs 下的 auth、tls。

与 [KK-C01](KK-C01.md) 的“显式禁用 CRI”根因不同，不能仅凭相同 ImageService 报错合并处理。

## KK-C11 最终根因或已确认边界

日志明确出现以下插件加载错误：

```text
invalid cri image config: `mirrors` cannot be set when `config_path` is provided
unable to load CRI image service plugin dependency
```

同时存在旧 registry TLS 字段被忽略的警告。containerd 主进程最后仍报告启动成功。

containerd 2.2.1 的镜像插件默认 ConfigPath 为 `/etc/containerd/certs.d:/etc/docker/certs.d`；用户文件没有写这一项，不代表生效值为空。它与非空 Mirrors 同时存在时，ValidateImageConfig 返回错误。

```text
旧 mirrors 与生效 config_path 冲突
→ CRI 镜像插件加载失败
→ CRI gRPC 服务依赖失败
→ containerd 主进程和 socket 仍存在
→ crictl 调用不存在的 ImageService
→ 拉取阶段退出，尚未进入 kubeadm join
```

这次已有明确插件日志，不能再将报错归为私仓缺镜像、域名解析、账号密码或旧数据损坏。version = 2 本身也不是直接故障原因；2.2.1 有旧格式迁移逻辑，不能只修改版本数字而保留不匹配的配置块。

## KK-C11 KK 复用旧运行时的机制

- 当前 `ContainerdExist.PreCheck` 只检查命令是否存在及 `/run/containerd/containerd.sock` 是否存在，不检查运行版本和 CRI 状态。
- 当前安装模块的同步二进制、生成 service、生成 config.toml、启用服务均受这一条件限制。已有运行时可能连同旧配置被直接保留。
- 当前移除节点流程清理 Kubernetes、CNI 等文件，保留 containerd 配置与数据，随后尝试重启 containerd；重启命令错误未向上返回。本次日志是主进程成功但插件失败，因此只检查重启退出状态仍不足。
- “此前二进制被替换，移除时重启才使新版本生效”是可排查的时间线，尚无证据确认。本次不能断言移除操作把 1.7.13 升级成 2.2.1，也未证实客户当时执行的 KK 与本地源码完全一致。

## KK-C11 处理方案

建议保留现场当前的 2.2.1，迁移仓库配置。保留 `/data/containerd`、既有运行时设置、正确的离线 sandbox_image 及原认证值；不要清空数据或直接降级。

1. 确认运行中进程的启动参数和实际配置路径。以下命令是排查示例，本案例没有在客户机器执行。

```bash
ctr --address /run/containerd/containerd.sock version
systemctl show containerd -p MainPID -p ExecStart -p FragmentPath -p DropInPaths
ps -ww -C containerd -o pid,args
ctr --address /run/containerd/containerd.sock plugins ls | grep -i cri
journalctl -u containerd -b --no-pager -n 150
```

2. 对本次用户提供的 version = 2 配置，移出全部旧 registry.mirrors，删除被忽略的旧 registry.configs 下的 tls；在原 registry 节下设置以下内容。此处只是配置节选，不可用它覆盖整个文件。

```toml
[plugins."io.containerd.grpc.v1.cri".registry]
  config_path = "/etc/containerd/certs.d"
```

保留现有 `registry.configs."digiwin.gkubeinstaller.local:444".auth` 子节及原认证值；本文件不保存实际凭据。其他仍需使用的 HTTP 仓库或镜像加速地址，应分别迁移对应 hosts.toml，不要把本次离线专用处理泛化成所有环境都可直接删除。

3. 在 `/etc/containerd/certs.d/digiwin.gkubeinstaller.local:444/hosts.toml` 配置离线私仓：

```toml
server = "https://digiwin.gkubeinstaller.local:444"

[host."https://digiwin.gkubeinstaller.local:444"]
  capabilities = ["pull", "resolve"]
  skip_verify = true
```

这里沿用用户原配置跳过证书校验的行为；已有可信 CA 的环境应按实际证书配置 ca。完整目录名是“域名:端口”，不是单独的 444 目录。

4. 在授权维护范围内重启并验证，成功后再重新添加节点：

```bash
systemctl restart containerd
ctr --address /run/containerd/containerd.sock plugins ls | grep -i cri
crictl --runtime-endpoint unix:///run/containerd/containerd.sock \
  --image-endpoint unix:///run/containerd/containerd.sock \
  pull digiwin.gkubeinstaller.local:444/kubesphereio/pause:3.10
```

预期 CRI 相关插件正常，且目标镜像实际拉取成功。之后还需单独确认节点加入与网络就绪；单次拉取成功不能证明完整集群恢复。

## KK-C11 版本来源与公网排查

本地 KK 默认值及 manifest-v1.32.8.yaml 都为 containerd 1.7.13；已审查 Web 安装脚本也固定安装 1.7.13。普通安装路径没有发现自动选择最新 containerd 的逻辑。KK 根据 artifact 参数选择离线分支，不根据能否访问公网选择版本；缓存缺失时的下载 URL 同样带指定版本。

但这不证明客户机器没有其他软件更新。系统包管理、自定义 pre/postInstall、system.debs/rpms、其他脚本及人工覆盖都需要根据客户实际记录核对，不能只靠源码排除。可从实际启动路径及包日志追查：

```bash
systemctl show containerd -p ExecStart -p FragmentPath
type -a containerd
dpkg -l | grep -i containerd
dpkg -S /usr/bin/containerd /usr/local/bin/containerd
zgrep -hi containerd /var/log/dpkg.log*
```

这些是 Debian/Ubuntu 的排查示例；手工覆盖二进制可能没有包日志。没有版本变化记录时，只能确认“当前运行 2.2.1”，不能确认它在首次安装前就存在还是后来升级。

## KK-C11 优化建议（未实现、未发布）

1. 将“是否安装二进制”与“配置是否匹配、CRI 是否正常”分开。已有 containerd 不再跳过后两项。
2. 先读取服务端版本、执行路径、实际配置；无运行时则安装指定版本，有运行时则校验支持范围。未知版本提前给出明确错误，不自动降级或覆盖。
3. Web 脚本和 KK 统一使用 config_path / hosts.toml；针对已验证的 1.7.13 与 2.2.1 分别处理配置格式、插件路径、认证和 TLS，不泛化为所有 2.x 都兼容。
4. 仅合并本次集群需要的仓库和 sandbox 设置，保留其他仓库、运行时和数据目录。变更后重启，再验证 CRI RuntimeService、ImageService、实际私仓拉取，最后执行 join。
5. 新节点尚无 CNI 配置时允许网络暂未就绪；CRI 服务可用与 CNI Ready 分开判断。移除流程的重启错误应返回，重启成功后仍需检查插件。

## KK-C11 验证证据与限制

- 用户提供的版本输出及插件启动日志确认直接故障原因；本地源码与 containerd v2.2.1 上游源码支持配置冲突链。
- 未收到修改后的插件、镜像拉取、重新加入结果；元数据保持 unverified。
- 214、215 的版本为用户提供；固定 SSH 别名的连接尝试均认证失败，未现场确认各自配置来源。相关两种配置生成方式见 [REL-10](../09_构建制品与发布/REL-10.md)。
- 本次仅写脱敏文档，没有修改客户配置、部署、清理数据、提交或写入向量库。

## KK-C11 来源定位

- 2026-10-15 本轮用户提供的版本、配置和插件日志，经整理后只保留故障机制，不保存原始会话、完整配置或凭据。
- `g_kube_installer/cmd/kk/pkg/container/prepares.go:99`、`container/module.go:187`、`container/templates/containerd_config.go:79`。
- `g_kube_installer/cmd/kk/pkg/bootstrap/os/tasks.go:231`、`:277`；`pipelines/add_nodes.go:44`；`apis/g_kube_installer/v1alpha2/default.go:47`；`cmd/kk/manifest-v1.32.8.yaml:37`。
- [containerd v2.2.1 默认镜像配置](https://github.com/containerd/containerd/blob/v2.2.1/internal/cri/config/config_unix.go#L26)、[配置冲突校验](https://github.com/containerd/containerd/blob/v2.2.1/internal/cri/config/config.go#L452)、[旧格式迁移](https://github.com/containerd/containerd/blob/v2.2.1/plugins/cri/images/plugin.go#L151)。

[返回案例索引](../README.md)
