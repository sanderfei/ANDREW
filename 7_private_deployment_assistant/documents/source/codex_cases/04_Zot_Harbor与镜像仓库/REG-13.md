# REG-13：HarborStatus端口可连不等于镜像仓库功能正常

项目：g_kube_installer / g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-09-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-13 问题与表现

页面HarborStatus成功，但pull/push仍失败。

## REG-13 最终根因或已确认边界

最终用户限定的离线健康检查只探测444 TCP，超时3秒；早期API检查草稿后来被简化。

## REG-13 处理方案

把页面结果理解为可达性。另核对/v2/、认证、具体repository/tag、节点crictlpull。在线仍按其原路径，不能把离线TCP结论推广到在线Harbor的应用健康。

## REG-13 验证证据与限制

Harbor/Zot端口开放、关闭、超时场景已测试；不证明具体镜像可拉。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-13 2026-10-29：查询 444 仓库中的 Neo4j 指定标签

问题：确认离线仓库是否已有源镜像 `registry.digiwincloud.com.cn/bitnami/neo4j:5.26.28`，用户要求提供带项目默认认证的命令。本轮核对本地源码，随后用户回传终端截图；没有直接连接目标仓库。适用环境为 Web 固定离线 Zot 导入路径，具体客户 Web/KK、Kubernetes、操作系统和 Zot 运行版本尚未核实。

源码证据：Web 的 `internal/service/file_server/obs_v3_local_import.go:21-25` 定义固定地址 `digiwin.gkubeinstaller.local:444` 及该路径使用的认证，`:33-38` 的 `ImportLocalImagesV1` 使用这一配置。`internal/common/registry.go:351-383` 中 `rewriteImageToRegistry` / `stripSourceRegistry` 仅去掉源 registry，保留 `bitnami/neo4j:5.26.28`。因此按该导入规则，目标镜像为 `digiwin.gkubeinstaller.local:444/bitnami/neo4j:5.26.28`。这只是名称映射依据，不证明已经导入。

用户回传截图显示，多行命令粘贴后行间出现空行，终端依次报 `curl: no URL specified!`、`-u: command not found`、`-H: command not found`，URL 被当作独立命令并报 `No such file or directory`。已确认本次 Shell 将查询拆成多条命令：curl 没有接收到 URL，后续参数和 URL 各自被执行，未取得仓库 HTTP 响应。因此本次截图不能判断镜像是否存在、认证是否正确或网络是否可达。

处理步骤：在能解析、连通该仓库的主机，将以下代码块整行复制执行，中间不手动按回车。将认证占位符替换为目标仓库实际配置；本文不保存截图中的明文密码：

```bash
curl --noproxy '*' -ksSI --connect-timeout 5 --max-time 15 -u 'admin:<仓库密码>' -H 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json' 'https://digiwin.gkubeinstaller.local:444/v2/bitnami/neo4j/manifests/5.26.28'
```

如自行改为多行写法，续行反斜杠 `\` 必须紧接换行，后面不能有空格，续行之间不能插入空行。终端显示宽度导致的自动折行不需要手动增加换行。

`-I` 请求 manifest 响应头，不下载镜像层；`--noproxy '*'` 使请求直连；`-k` 跳过证书验证，用于当前命令的证书排查场景。已有可信 CA 时可将 `-k` 替换为 `--cacert <CA文件路径>`。状态按实际仓库 API 响应解释：

| 结果 | 可确认的结论 |
|---|---|
| `200` | 目标仓库中该标签的 manifest 存在且当前身份可读；不能据此证明全部镜像层可拉取或 Neo4j 可运行 |
| `404` | 该仓库 API 未找到指定 repository/tag；不代表源 registry 中不存在该镜像 |
| `401` / `403` | 认证或授权未通过，不能判断目标镜像是否存在 |
| DNS、连接、TLS、超时错误或无 HTTP 响应 | 请求未取得可判断镜像存在性的仓库响应 |

项目固定认证与 Zot 产品默认认证需区分：KK 的 `cmd/kk/pkg/common/zot.go:69-77` 要求显式提供对应 `registry.auths` 的非空用户名和密码；不能将 Web 当前源码常量称为任意 Zot 环境通用密码。现场如已变更认证，应使用实际配置，且不从历史会话提取凭据。

验证结果与遗留事项：源码映射与查询命令已核对；用户截图确认首次粘贴被拆成多条 Shell 命令，尚无修正为整行执行后的 HTTP 响应。本轮没有直接查询实际仓库、导入镜像、拉取镜像或启动 Neo4j，镜像是否存在仍待用户回传结果；元数据继续为 `unverified`。未修改业务代码、部署或重启服务。

协议依据：[Distribution API：Existing Manifests](https://distribution.github.io/distribution/spec/api/#existing-manifests)，规定 `HEAD /v2/<name>/manifests/<reference>` 的查询方式与成功/不存在响应。

## REG-13 来源定位

- Codex 会话 `01a0bca9-a5c7-7c81-bf16-7ef6acbf6739`；始于 2026-09-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
