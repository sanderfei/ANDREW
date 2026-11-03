# HELM-43：ES Chart混入AppleDouble元数据导致Helm拒绝加载

项目：g_kube_installer / g_web_installer。记录日期：2026-10-28。记录状态：214现场包污染已确认；来源及清理后安装待验证。

适用环境：KK调用目标master的Helm CLI加载 `/tmp/g_kube_installer/elasticsearch.tgz`，release为 `elasticsearch`、namespace为 `elastic`。本轮只读检查本地、121源码归档及214现场实际归档，没有清理、解压、重打包、安装、构建或发布。214实际Chart/ES版本和Helm CLI版本未读取；本地与121源码Chart为7.15.0，不能据此认定214也是7.15.0。Kubernetes/OS版本不决定这次tar成员路径错误。

## HELM-43 问题现象

Elasticsearch安装执行以下链路时报错，连续重试仍出现同一错误：

```text
helm upgrade --install elasticsearch /tmp/g_kube_installer/elasticsearch.tgz --namespace elastic ...
chart illegally contains content outside the base directory: "._elasticsearch"
```

错误发生在Helm读取Chart归档成员阶段，不是ES Pod调度、镜像插件、数据库认证或Service就绪错误；对同一个坏包重试不能改变成员结构。此根因与 [HELM-28](HELM-28.md)、[HELM-35](HELM-35.md)、[HELM-37](HELM-37.md) 的插件、调度或Service问题分别记录。

## HELM-43 最终定位与现场证据

214实际使用的tgz混入macOS AppleDouble元数据，顶层存在普通成员 `._elasticsearch`。它没有正常Chart顶层目录后的相对路径，触发Helm对包外内容的保护检查。

| 实物位置 | 大小 / 成员 | SHA-256与结构 |
|---|---|---|
| 214 `/tmp/g_kube_installer/elasticsearch.tgz` | 34854字节，186成员 | `51194b5e01bd2ed844b96f671aadbfc1b73d53bb927e188e3f6da9b2922b61b4`；roots为 `._elasticsearch`、`elasticsearch`，含93个AppleDouble条目。 |
| 本地KK源码 `cmd/kk/pkg/component/elasticsearch.tgz` | 32108字节，93成员 | `f1636765b957c10028e38bdbe071990c904ee9ede09a7727921c9d7e847c1379`；root仅 `elasticsearch`，无 `._*`、`__MACOSX` 或 `.DS_Store`。 |
| 121 `/root/wfkk/g_kube_installer/cmd/kk/pkg/component/elasticsearch.tgz` | 32108字节，93成员 | 与本地同一SHA-256及干净结构。 |

214首条 `._elasticsearch` 的前8字节为 `0005160700020000`，确认AppleDouble magic/version，不只是从名称猜测。其他样本包括 `elasticsearch/._Chart.yaml`、`elasticsearch/._Makefile`、`elasticsearch/._values.yaml`。该现场tgz与本地/121干净源码包不同，直接解释本次成员名报错；不意味着本地源码包也损坏。

本地KK与121源码均为 `test/9a73986d8382ce2830273c2c01ba7f404598b5fc`。本地另有无关 `pinpoint.tgz` 改动，本轮保留未动；121源码tracked状态为空。121的 `/g_web_installer/kk` 仅确认文件存在及stat，未审计其内嵌归档；因此坏包具体来自哪次打包、哪个KK二进制或哪次传输仍待核对，不能归因于当前121源码或某次已知发布。

## HELM-43 为什么会被Helm拒绝

Helm v3.9.4官方归档loader跳过目录/PAX头后，对普通文件成员去掉首段Chart根目录，再校验剩余路径。顶层 `._elasticsearch` 没有 `/` 后的路径，清理后为 `.`，因而报 `outside the base directory`；loader不会自动忽略 `._*`。读取现成tgz时不应用目录的 `.helmignore`，仅补一个ignore文件并重试旧tgz不会修复其成员。这里以官方代码解释机制；项目Go依赖的Helm SDK v3.9.4不代表现场外部Helm CLI就是该版本。

KK源码链路已确认：`tasks.go:39` 通过 `go:embed` 嵌入tgz，`:1690-1705` 释放到runtime工作目录，`:1713-1717` Scp为目标 `/tmp/g_kube_installer/elasticsearch.tgz`，`:1802-1825` 直接让Helm加载该tgz。最终消费的是二进制释放并同步的归档；相邻解压工作树或当前源码干净，不能证明现场执行的KK二进制内嵌包干净。该制品边界另见 [REL-01](../09_构建制品与发布/REL-01.md)。

## HELM-43 解决方案与可执行步骤（建议，未执行）

1. 在实际执行Helm的机器核对出错tgz及执行中KK的来源、构建版本；先读取现场 `Chart.yaml` 与业务成员，确认需保留的版本和配置，不用本地较旧的干净7.15.0包直接覆盖未知现场版本。
2. 从匹配现场目标版本的可信源创建干净Chart工作树，排除AppleDouble、`__MACOSX`、`.DS_Store` 等元数据，再按单一 `elasticsearch/` 根目录重打包；防止在macOS打包时重新附加资源元数据。不要仅修改解压目录而保留原tgz。
3. 对新tgz重新列成员、检查根目录，再执行 `helm show chart` / `helm template` 加载验证。示意命令需替换为实际修正包，模板参数沿用现场真实配置：

```bash
tar -tzf /path/to/fixed/elasticsearch.tgz
helm show chart /path/to/fixed/elasticsearch.tgz
helm template elasticsearch /path/to/fixed/elasticsearch.tgz --namespace elastic
```

4. 修复权威嵌入归档后，按另行授权的范围构建/发布实际执行的KK，再释放同步修正包并重试；只清理目标临时目录可能在下一次KK执行时再次被旧内嵌坏包覆盖。确认Chart可加载后还需检查实际组件任务、Pod/Endpoints及ES认证读写，不能把模板通过当成安装恢复。

上述操作均为建议，没有执行包清理、重打包、Helm加载验证、安装或KK发布。

## HELM-43 验证结果与遗留事项

- 已有214实际tgz成员、AppleDouble头部、两种根目录及与本地/121源码归档的大小/hash差异证据，确认本次Chart加载错误由现场包内AppleDouble成员触发。
- 只读取证未解压或改包，未修改业务源码或无关制品，没有执行测试、构建、部署、重启或安装。
- 坏包生成来源、实际执行KK内嵌包、214实际Chart/ES和Helm CLI版本仍待核对；清理后的Chart加载、安装及真实ES功能未验证。
- 不能将包结构定位或干净源码归档写成功能恢复，metadata保持 `unverified`。

## HELM-43 2026-11-03 后续：RabbitMQ 与 ES 包再次出现同类问题

用户提供214安装组件的日志：`DeployRabbitmq` 读取 `/tmp/g_kube_installer/rabbitmq.tgz` 时连续5次报 `chart illegally contains content outside the base directory: "._rabbitmq"`，组件流水线失败。该日志只证明 RabbitMQ 的 Chart 加载失败，不能证明已经执行了 ES 安装。

本次对214只读取证：Helm CLI为 `v3.18.5+gb78692c`；现场 RabbitMQ 包 SHA-256 为 `013fb844621c9052fd93df4637c1604c1205b996c269f4572e536203de117bda`，包顶层存在 `._rabbitmq`；现场 ES 包 SHA-256 为 `51194b5e01bd2ed844b96f671aadbfc1b73d53bb927e188e3f6da9b2922b61b4`，包顶层存在 `._elasticsearch`。在214执行 `helm show chart` 读取这两个包均报对应的根目录错误，确认 ES 现场包也不能被 Helm 加载；此读取不代表安装或业务测试。

本次本地 KK 源码归档与2026-10-28历史检查不同：当前 `elasticsearch.tgz` 与214现场ES包 SHA-256相同，含 `._elasticsearch`；当前本地 `rabbitmq.tgz` SHA-256 为 `5bb7be57c2be0d717445c1893e4a2f0d8a78ab35cbeadc4950a7f2fe10f3f5bd`，不含 `._`，与214现场RabbitMQ包不同。历史对比仅适用于当时的 test 版本，不能代替本次版本比较。未确认现场坏包如何生成，也未核实实际执行的KK二进制内嵌内容。

当前KK源码 `cmd/kk/pkg/component/tasks.go` 使用 `go:embed` 嵌入Chart，并在任务中释放和复制至目标机后调用Helm；因此应先确定实际运行KK版本和其嵌入包，修正对应权威制品中的两个污染包并重新构建交付，随后验证新包能通过 `helm show chart` 和模板渲染。只修现场 `/tmp` 文件，后续任务可能再次被KK释放的旧包覆盖；不要以不同版本的Chart直接替换。对新制品完成交付后，另行执行组件任务并检查终态及组件功能。

本次没有清理、覆盖现场包，没有修改业务代码、构建、发布、重启或重试；两个坏包的加载错误已确认，修复与ES/RabbitMQ安装功能仍待验证。

## HELM-43 2026-11-03 后续：本地 ES 内嵌包清理

已从本地 KK `cmd/kk/pkg/component/elasticsearch.tgz` 中剔除93个 `._` 元数据条目；其余93个条目的路径、类型、权限、链接和内容哈希与清理前一致。原同级解压目录的 `values.yaml` 有未打包修改，本次保留且未覆盖，也未把它加入归档。

用214现场 Helm 3.18.5 对清理后的包经匿名内存文件执行 `helm show chart` 与 `helm template` 均成功，模板渲染8个YAML文档。这证明清理后的ES包可被该版本 Helm 加载和渲染，不证明安装或实际功能恢复。本轮未构建或发布 KK，未安装组件；214现场旧包与实际运行的KK尚未修复，RabbitMQ权威制品及现场处理也仍待确认。

## HELM-43 来源定位

- 本轮214 `/tmp/g_kube_installer/elasticsearch.tgz` 只读stat/hash/tar成员与AppleDouble首8字节结果。
- 本地与121 `test/9a73986` 实际 `cmd/kk/pkg/component/elasticsearch.tgz`、`cmd/kk/pkg/component/tasks.go:39`、`:1690-1705`、`:1713-1717`、`:1802-1825`；`go.mod`。
- [Helm v3.9.4归档loader](https://github.com/helm/helm/blob/v3.9.4/pkg/chart/loader/archive.go#L114-L165)：普通成员路径与根目录校验。
- [Helm v3.9.4目录loader](https://github.com/helm/helm/blob/v3.9.4/pkg/chart/loader/directory.go#L52-L89)：目录打包读取ignore规则的独立路径。
- [libarchive tar reader](https://github.com/libarchive/libarchive/blob/master/libarchive/archive_read_support_format_tar.c#L882-L885)：AppleDouble元数据识别。

[返回案例索引](../README.md)
