# OBS-07：外层镜像包嵌套tar不能直接docker load

项目：g_web_installer。记录状态：历史功能验证。来源会话起始日期：2026-04-20, 2026-06-01, 2026-10-12（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## OBS-07 问题与表现

docker load缺manifest/layer或报找不到JSON，合包下载后不能直接加载。

## OBS-07 最终根因或已确认边界

旧合包是每镜像Docker-save tar再装一个外层tar，外层不是可直接load的结构；另有归档writer格式演进。扩展名tar/tgz不证明内层格式。

## OBS-07 处理方案

按当前版本核对tar成员：直接load归档应有manifest.json/config/layers/RepoTags；嵌套包需按其合同先取内层。历史后续改兼容Docker-save writer，V3外层gzip可直接dockerload，零layer走兼容分支。旧OBS对象不随代码自动转换，需重新生成。

## OBS-07 验证证据与限制

121实际保留V3三镜像tgz，dockerload退出0并恢复MongoDB/MySQL/Nacos标签。上传按用户要求中止，不能把load通过描述为OBS上传成功。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## OBS-07 来源定位

- Codex 会话 `019e811b-2e53-7192-969c-410a25d2be34`；始于 2026-06-01。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `019da8f6-435c-7673-8dfe-09956eaf3dd3`；始于 2026-04-20。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a12e08-2388-76a1-8436-3d9d3c519720`；始于 2026-10-12。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
