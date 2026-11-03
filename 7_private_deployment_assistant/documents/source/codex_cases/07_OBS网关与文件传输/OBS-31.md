# OBS-31：版本导入因数据组件配置缺失而全量预检失败

项目：g_web_installer。记录日期：2026-10-29（Asia/Shanghai）；日志原时间2026-10-28。记录状态：按组件跳过PR428已发布121；旧版配置缺失事实保持，新业务未验证。

适用环境：121 k8s_test、control-plane214，实际失败任务为PR427/bc6旧二进制、PID尾83109a4c。现场组件配置未修改；新策略已随PR428完成121编译替换启动，新流程实际导入尚未验证。

## OBS-31 旧版真实失败

22:38:22开始，22:45:46台湾/CDN五包下载完成，三个镜像预检通过；22:54:35第4/5个ES包报 `component elastic is not configured in cluster k8s_test`。汇总packages5、downloaded5、validated3、images/data0、skipped9、unapproved4，整体失败，监控已退出。

121配置组件为mariadb、neo4j、rabbitmq、nacos、seata，缺elastic/mongodb。214只读确认MongoDB Chart18.6.24/app8.2.6、Running/Ready且重启0，未见ES release/Pod，外部ES未探测。安装存在不等于目标已登记或凭据正确，不能猜连接信息。

旧版全量预检屏障下，ES失败终止整版，镜像和Mongo导入均未开始，并非独立跳过Mongo。此为旧任务事实；用户随后明确要求按组件跳过，覆盖此前严格整版策略，不能将新策略反写为旧任务已执行。

## OBS-31 用户明确的新执行策略（PR428已交付121）

先镜像：离线仓库不可用时日志跳过镜像下载；可用时逐包下载→prepare一次→同步import→cleanup。再按mysql→mongodb→mariadb→elastic→postgresql→starrocks，对有包组件先检查配置、Helm/健康，不满足依赖日志跳过继续；合格才下载→prepare→Run→cleanup。

当前公开 `ValidateArchiveImportTarget` 复用配置及完整只读readiness；此前未发布的纯配置全版gate `ValidateArchiveImportTargetConfig`已删除。准备时目标漂移的 `ErrArchiveImportTargetUnavailable` 可识别跳过，真实格式错误不带该sentinel；父context取消优先停止，真下载/格式/import或清理错误仍失败终止。不会自动补ES/Mongo配置或猜凭据。

新策略移除全版写入屏障，前面的镜像/合格数据库可以已完成，后面缺依赖只跳过；不是所有错误都被忽略，也不表示组件已修好。一个PID串行、审核、出口选路、原压缩包保留不变；每包清工作产物，全部跳过不触发GeoIP或创建obs-import目录，history日志正常。

联合normal、file_server/importdata两包race及server构建、格式/diff通过，覆盖镜像优先/六DB顺序、readiness后本包下载、依赖跳过后续继续、取消/目标漂移/真实错误及清理。3临时测试和构建产物删除；随后已提交42bbcb8，经PR428/a024faf合并并完成121编译替换启动；未执行新流程真实导入，metadata保持 `unverified`。

用户另行明确要求删除该旧终态任务，history/obs-import路径已删、cluster config保留，Web未重启；删除不代表导入恢复，见 [OBS-30](OBS-30.md)。空间及流程变更见 [OBS-28](OBS-28.md)。

## OBS-31 来源定位

- 121原精准任务终态与组件配置、214管理员Helm/Pod只读结果；未保存姓名段PID、凭据或完整配置。
- `internal/service/file_server/obs_v3_version_import.go`、`obs_version_images.go`；`internal/service/importdata/archive_import_target.go`、`archive_import.go` 的当前本地实现。
- 本轮normal/race/build与测试清理仅为开发证据；PR428交付详情见OBS-28，现场已完成a024faf编译启动但未跑新流程导入。

[返回案例索引](../README.md)
