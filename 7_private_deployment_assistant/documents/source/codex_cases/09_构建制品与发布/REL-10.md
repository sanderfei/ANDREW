# REL-10：Web脚本容器部署与121宿主机部署及containerd配置来源

项目：g_web_installer / g_kube_installer / base_installer。记录日期：2026-10-15。记录状态：源码结论（部署方式已由用户明确，脚本已只读审查，未实际执行部署）。

适用环境：当前 121 使用宿主机后端进程；Gitee base_installer release 1.0 当前提供 Kubernetes v1.32.8 资源对应的 Web 容器部署。具体 OS 和部署主机以实际支持范围为准。外部脚本附件和 latest 镜像可变化，本记录是 2026-10-15 的内容快照，后续操作前应重新核对。当前本地 Web HEAD 为 00a0d61，存在其他未提交工作，不代表发布镜像包含相同代码。

## REL-10 问题与表现

用户询问：Web 安装脚本是否会提前安装 containerd，导致 Web 所在机器保留 config_path / hosts.toml，而普通 worker 使用 KK 生成的内联 config.toml；同时要求后续区分 121 手动部署与脚本容器部署。

## REL-10 最终定位与部署边界

两种部署是不同的运行方式，不应混用更新目标：

| 项目 | 121 宿主机后端进程 | 脚本容器部署 |
|---|---|---|
| Web 启动对象 | `/root/wfweb/g_web_installer/server` | 镜像中的应用，容器名 `g_web_installer` |
| 启动工具 | `/root/wfweb/web_start.sh` | 首次安装使用 containerd / nerdctl |
| 持久数据 | `/root/wfweb/g_web_installer/data` | 宿主机 `~/g_web_installer_data` 挂载到容器 `/g_web_installer/data` |
| 更新方式 | 在仓库编译并替换 server 后重启目标进程 | 更新镜像并重建容器，保留原数据挂载 |
| KK 更新边界 | 宿主机 `/g_web_installer/kk` 独立准备 | 本地 Dockerfile 将 KK 放入镜像，实际镜像内容需核实 |

## REL-10 脚本安装流程

用户指定入口为：

```bash
bash <(curl -sL https://gitee.com/panwpp/base_installer/releases/download/1.0/install.sh)
```

本次仅下载、阅读 install.sh 和 installer.sh，没有执行上述安装命令。

1. 入口远程模式使用 `/tmp/base_installer` 缓存目录，下载同 release 的 installer.sh、containerd 1.7.13、nerdctl 1.7.6、CNI 1.2.0、runc 和 `g_web_installer_k8s_v1.32.8.tgz`。installer.sh 强制刷新；其他非空已有依赖复用。指定本地目录且依赖齐全时可直接运行本地文件。
2. 主菜单 1 设置 v1.32.8，并依次调用运行时安装、Web 容器启动。该选择准备 Web 与安装资源，不等于执行 Kubernetes 集群安装。
3. 运行时函数解压并复制二进制到 `/usr/bin`，写 `/etc/systemd/system/containerd.service`，安装 CNI/runc，写 containerd 主配置及仓库 hosts.toml，然后 enable/restart containerd。这条初装路径会重写配置，已有环境更新 Web 时应选择更新菜单。
4. 默认镜像为 `registry.digiwincloud.com.cn/ops/g_web_installer:latest-amd64`。首次启动先复用本地精确 tag；没有时支持 images/iamges 目录 tar、自定义 tar 或用户选择的云端拉取，并允许选择实际导入的镜像名。
5. 在 k8s.io namespace 重建同名 Web 容器，使用 host 网络、Asia/Shanghai 和持久数据挂载：

```bash
# 仅为当前脚本关键启动参数说明，不是本次已执行的命令。
nerdctl -n k8s.io run -d --restart=unless-stopped \
  --name=g_web_installer --network host -e TZ=Asia/Shanghai \
  -v ~/g_web_installer_data:/g_web_installer/data \
  registry.digiwincloud.com.cn/ops/g_web_installer:latest-amd64
```

6. 将 Kubernetes 资源包解压到宿主机 `$HOME/g_web_installer_data/resource`，映射到容器 `/g_web_installer/data/resource`，Web 使用宿主机 8080。之后用户在 Web 上发起集群安装，由 Web 调用 KK 完成。

脚本启动前还会删除同名容器、清理相关 nerdctl 网络残留；不能将它视为纯读取脚本。当前主菜单在函数调用后显式 exit 0，未完整传播函数失败，因此还需看直接错误输出，不能只凭入口退出 0 宣称成功。

## REL-10 两套 containerd 配置来源

脚本写入的关键设置为：

```text
/etc/containerd/config.toml
  root = /data/containerd
  registry.config_path = /etc/containerd/certs.d
  sandbox_image = registry.cn-beijing.aliyuncs.com/kubesphereio/pause:3.9

/etc/containerd/certs.d/digiwin.gkubeinstaller.local:444/hosts.toml
  HTTPS 内置离线私仓，跳过证书校验

/etc/containerd/certs.d/<用户指定仓库>/hosts.toml
  HTTP 自定义仓库
```

`digiwin.gkubeinstaller.local:444` 是带端口的完整仓库目录名。脚本主配置仍存在，只是将仓库主机及 TLS 设置拆到 hosts.toml。当前脚本的公网 pause:3.9 与 KK 针对集群生成的离线 pause 镜像尚未统一，不能把“已配置离线私仓”等同于所有镜像均已离线。

当前 KK 默认同样为 1.7.13，但模板将 registry.mirrors、认证和 TLS 参数直接写入 config.toml；证书文件如有引用仍在独立路径。ContainerdExist 检测到二进制及 socket 后，会跳过 containerd 安装和配置生成。

因此，“Web 所在节点先装好并启动 containerd → KK 保留脚本配置；干净 worker → KK 生成模板配置”的机制成立。这是配置来源差异，不是 master/worker 必须采用不同模板。214/215 版本均为 1.7.13，来自用户输出；两台 SSH 认证失败，未确认各自历史安装文件，因此不得将上述机制写成两台现场来源已实证。

## REL-10 处理与后续部署规则

- 121：遵循当前 AGENTS.md，先核实目标提交已合并，在 `/root/wfweb/g_web_installer` 保留 data 和禁用 Vue 的本地调整，构建替换 server，精确定位旧 Web 进程并按约定启动 `/root/wfweb/web_start.sh`。发布阶段不自行扩充测试或多轮探测。
- 脚本初装：菜单 1 安装运行时并启动 Web 容器。已有 Web 容器更新使用菜单 2，支持本地镜像、本地 tar、云端拉取；不调用运行时重装函数。
- 菜单 2 检测到活跃 Docker 时优先更新 Docker 容器并映射 8080；否则走 nerdctl / containerd 的 host 网络路径。均保留原数据挂载，不能将 Docker 分支混同首次安装的 nerdctl 路径。
- 本地 Dockerfile 的工作目录为 `/g_web_installer`，将 app、kk、ui 放入镜像，入口为 `./app`。更新宿主机 server、源码或 KK 文件不会自动更新已运行镜像中的内容；需要确认所需变更已进入目标镜像。
- 普通脚本安装固定选择 containerd 1.7.13，更新 Web 容器不等于升级宿主机 containerd。有公网也不代表自动安装最新版本。客户 2.2.1 的配置冲突和版本溯源见 [KK-C11](../02_集群运行时与网络/KK-C11.md)。

## REL-10 优化建议（未实现、未发布）

统一 Web 脚本和 KK 的仓库配置策略，按支持的运行时版本生成；将 sandbox 镜像、认证和 TLS 与集群目标参数对齐。对已有运行时执行版本及 CRI 检查，保留其他仓库和数据设置；避免初装脚本重复覆盖。外部脚本的失败状态应向入口传播，部署输出与真实功能验证分开记录。

## REL-10 验证证据与限制

已只读审查远程两个脚本及本地 KK、Web Dockerfile，并按用户明确要求区分部署方式。没有执行容器安装、升级、121 发布或镜像构建；没有现场验证镜像内二进制、数据迁移、服务功能。元数据保持 unverified。

## REL-10 来源定位

- 用户在 2026-10-15 指定脚本入口并明确两种部署约定；仅保存整理后的规则。
- [install.sh](https://gitee.com/panwpp/base_installer/releases/download/1.0/install.sh)：缓存及依赖下载、调用 installer.sh。
- [installer.sh](https://gitee.com/panwpp/base_installer/releases/download/1.0/installer.sh)：install_container_manager、start_container_service、update_container_service 和主菜单；审查时关键位置为 39、108、128、151、278、286、312、479 行。
- `g_web_installer/Dockerfile:113`；当前项目 AGENTS.md 的 121 发布流程。
- `g_kube_installer/cmd/kk/pkg/container/prepares.go:99`、`container/module.go:187`、`container/templates/containerd_config.go:67`。
- 旧配置路径排查背景见 [REG-06](../04_Zot_Harbor与镜像仓库/REG-06.md)。

[返回案例索引](../README.md)
