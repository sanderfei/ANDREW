# HELM-39：Helm搜索StarRocks 3.5及kube-starrocks与starrocks Chart选择

项目：g_web_installer / g_kube_installer 相关组件部署。记录日期：2026-10-21。记录状态：用户查询已确认；Chart组成已核对，部署功能未验证。

适用环境：用户在 manifest 目录查询名为 starrocks 的 Helm 仓库；输出包含 kube-starrocks、starrocks、operator、warehouse，最新 Chart version 为 1.11.7，kube-starrocks、starrocks、warehouse 的 appVersion 为 4.1-latest。后续已核对 v1.11.4 的官方 Chart 定义与文档。用户未指定目标主机、Helm/Kubernetes/OS 版本，也未说明已部署数据库的版本。适用于 Helm 仓库查询和 Chart 选择；不代表已执行安装或升级。

## HELM-39 问题与表现

执行 `helm search repo starrocks` 只看到最新 Chart；继续执行 `helm search repo starrocks | grep 3.5` 没有匹配结果，用户希望搜索 StarRocks 3.5。

## HELM-39 最终根因或已确认边界

- `helm search repo` 默认显示每个 Chart 的最新稳定版本。未使用 `-l` / `--versions` 时，后续 grep 只能筛选已显示的最新条目，无法检索被省略的历史版本。
- CHART VERSION 是安装包版本，APP VERSION 是 Chart 声明的应用版本。StarRocks 3.5 是应用版本范围；`--version` 约束 Chart 版本，不能将 `--version 3.5` 当作应用版本过滤条件。
- 本轮直接读取官方仓库 `index.yaml`：kube-starrocks 和 starrocks 的 Chart 1.11.0、1.11.1、1.11.2、1.11.3、1.11.4 均声明 `appVersion: 3.5-latest`；索引中的最新条目为 Chart 1.11.7 / appVersion 4.1-latest，与用户提供的最新版本一致。
- `3.5-latest` 没有固定到某个 3.5.x 补丁版本。仓库元数据查询不能证明已安装镜像、运行版本或数据库功能，也不能据此推断 Chart 与任意集群环境兼容。

## HELM-39 处理方案

在用户当前配置了 starrocks 仓库的环境执行：

```bash
helm repo update starrocks
helm search repo starrocks -l | grep '3\.5'
```

`-l` 等价于 `--versions`。如需仅按第三列 APP VERSION 筛选并保留表头：

```bash
helm search repo starrocks -l | awk 'NR == 1 || $3 ~ /^3[.]5([.-]|$)/'
```

按照本轮官方索引，结果应包含以下对应关系；这两行是索引整理示例，不是目标机执行输出：

```text
NAME                       CHART VERSION   APP VERSION
starrocks/kube-starrocks    1.11.4          3.5-latest
starrocks/starrocks         1.11.4          3.5-latest
```

后续如需下载上述 kube-starrocks 包，应使用 Chart 版本，例如 `helm pull starrocks/kube-starrocks --version 1.11.4`。是否部署、选择何种补丁镜像、资源/存储配置与版本兼容性须另行确认；本轮没有执行下载、安装、升级或重启。

## HELM-39 验证证据与限制

- 已阅读 Helm 官方 search repo 文档，核对默认最新稳定版本、`-l` 和 `--version` 的含义。
- 已通过 Python 标准库 HTTP 客户端读取官方 StarRocks 仓库索引，并用 YAML 解析器筛选 kube-starrocks / starrocks 的 appVersion，确认上述五个 Chart 版本对应 3.5-latest。
- 首轮本地没有 helm 可执行程序，未连接目标机执行查询。后续用户提供了带 `-l` 的成功查询结果，查询问题已确认解决；证据来源是用户命令输出，详见下面的补充记录。
- 没有数据库连接、查询或读写证据，metadata 保持 unverified。仅新增本地文档及索引，未修改业务代码、提交、推送、发布或录入向量库。

## HELM-39 补充：用户查询成功与两种Chart的区别（2026-10-21）

用户提供 `helm search repo starrocks -l | grep '3\.5'` 的实际查询结果：kube-starrocks、starrocks、warehouse 均列出 1.11.0～1.11.4，对应 APP VERSION 3.5-latest。因此版本搜索已确认恢复预期，不能继续描述为现场查询待验证。用户随后询问两个 Chart 的区别；因提问中重复书写 starrocks/starrocks，结合上下文按 kube-starrocks 与 starrocks 的对比解释，尚未得到对比较对象的单独确认。

已核对官方 v1.11.4 的 Chart.yaml、README 和父 Chart values：

| Chart | 默认安装范围 | 选择条件 |
|---|---|---|
| starrocks/kube-starrocks | 同时包含 operator 与 starrocks 两个子 Chart，默认启用 Operator 并创建 StarRocks 集群配置 | 首次安装且尚未部署 Operator，可一起管理 Operator 和数据库集群 |
| starrocks/starrocks | 创建 StarRocks 集群配置，不安装 Operator | 已有可用、能管理目标命名空间的 Operator 和所需 CRD，或计划将 Operator 单独安装管理 |
| starrocks/operator | 单独部署 Operator | 与 starrocks Chart 配合，将管理控制器与数据库集群分开管理 |

Operator 是 StarRocks 在 Kubernetes 上的管理控制器，负责 FE、BE/CN 等组件的部署、扩缩容和升级。starrocks Chart 的安装前提仍包括已安装 Operator；它创建的集群由 Operator 管理。相同 Chart 1.11.4 下，kube-starrocks 与 starrocks 均声明 appVersion 为 3.5-latest，主要区别是打包与管理范围。

证据：父 Chart dependencies 明确列出 operator 1.11.4 与 starrocks 1.11.4；父 values 的 `operator.starrocksOperator.enabled=true`，Operator 默认镜像为 `starrocks/operator:v1.11.4`；独立 starrocks Chart README 将安装 Operator 列为前提；项目 README 说明可将 Operator 和数据库 Chart 分开部署。

以上为官方版本源码与文档结论，没有核对用户集群是否已有 Operator、CRD 或数据库实例，未执行安装/升级，也没有数据库查询或读写证据。metadata 保持 unverified；案例编号和总数不变。

## HELM-39 来源定位

- 用户提供的 Helm 查询摘要：最新 Chart 1.11.7 / APP VERSION 4.1-latest，未带 `-l` 的 grep 查询无结果。
- [Helm 官方 helm search repo 命令文档](https://helm.sh/docs/helm/helm_search_repo/)：默认输出与参数说明。
- [StarRocks 官方 Helm 仓库索引](https://starrocks.github.io/starrocks-kubernetes-operator/index.yaml)：本轮直接读取并解析的 Chart/appVersion 对应关系。
- [StarRocks 官方 kube-starrocks 安装说明](https://github.com/StarRocks/starrocks-kubernetes-operator/blob/main/helm-charts/charts/kube-starrocks/README.md)：仓库地址及更新命令。
- 用户后续提供的带 `-l` 查询摘要：kube-starrocks、starrocks、warehouse 的 1.11.0～1.11.4 均显示 APP VERSION 3.5-latest。
- [v1.11.4 kube-starrocks Chart.yaml](https://github.com/StarRocks/starrocks-kubernetes-operator/blob/v1.11.4/helm-charts/charts/kube-starrocks/Chart.yaml)：两个子 Chart 依赖及父 Chart 版本。
- [v1.11.4 kube-starrocks values.yaml](https://github.com/StarRocks/starrocks-kubernetes-operator/blob/v1.11.4/helm-charts/charts/kube-starrocks/values.yaml)：默认启用的 Operator、镜像与嵌套子 Chart 配置。
- [v1.11.4 starrocks Chart 安装说明](https://github.com/StarRocks/starrocks-kubernetes-operator/blob/v1.11.4/helm-charts/charts/kube-starrocks/charts/starrocks/README.md)：预先安装 Operator 的要求。
- [v1.11.4 项目 README](https://github.com/StarRocks/starrocks-kubernetes-operator/blob/v1.11.4/README.md)：Operator 职责与合并/分开安装方式。

[返回案例索引](../README.md)
