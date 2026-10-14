# REG-16：manifest镜像清单与实际嵌入Chart不一致

项目：g_kube_installer / g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-09-21（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes 1.32.8；系统 any；安装模式 offline。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REG-16 问题与表现

离线包包含旧镜像，缺Neo4j等实际安装镜像；5.3.0与5.26.28被混为同一版本。

## REG-16 最终根因或已确认边界

Chart.version、appVersion和最终image.tag不同；真正安装取go:embed tgz与运行时override，不取同级解压目录/样例默认值。

## REG-16 处理方案

将所有启用组件、initContainer及正常升级Hook用真实参数helm template，按最终镜像集合对照manifest。历史保留kubesphereio项，清理23旧项并补Neo4j，84→62。Nacos nginx Helm test镜像不等于常规运行依赖。改manifest后重新export。

## REG-16 验证证据与限制

24 Chart渲染、镜像集合比对、未涉及配置/归档一致性检查通过；当轮未提交/部署。数字只属于历史快照。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REG-16 来源定位

- Codex 会话 `01a0c17e-ab67-7921-86c1-df12b82bd17d`；始于 2026-09-21。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
