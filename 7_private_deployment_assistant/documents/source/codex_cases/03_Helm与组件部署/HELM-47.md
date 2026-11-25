# HELM-47：RabbitMQ 4.2 拒绝业务创建旧版镜像队列策略

记录日期：2026-11-10。适用环境：用户称站台安装 RabbitMQ 4.2.1，业务通过 AMQP 长连接使用消息队列；实际版本、部署方式、节点数和队列类型尚未在客户现场核验。状态：截图和官方版本资料可解释策略校验失败，客户修复及业务功能待验证。

## 问题表现

客户提供的 Java `RegisterController.register` 日志显示注册 vhost 后执行 `ha-all` 操作失败，返回 `bad_request`，关键原因为：

```text
Validation failed: ha-mode=all, ha-sync-mode=automatic are not recognised policy settings
```

这是 RabbitMQ 拒绝旧策略字段的反馈，日志显示失败发生在 vhost 的 `ha-all` 策略设置阶段；它本身不能证明 AMQP 长连接建立失败或排除其他后续连接问题。截图未展示请求 URL、完整请求体，也未证明 vhost 创建最终成功。

## 问题原因与证据

`ha-mode` 和 `ha-sync-mode` 是旧版经典镜像队列策略，RabbitMQ 4.0 开始删除经典队列镜像功能，因此 4.2.1 不再接受这类新建策略设置。经典队列仍受支持，但它不再通过镜像实现跨节点复制。上述原因与截图中的未识别策略字段直接吻合；触发策略的具体应用代码、请求 URL、实际部署版本和客户运行状态未核验。

本机 `g_kube_installer` 的 `install_tiny` 分支 `da595f94c304`，`cmd/kk/pkg/component/rabbitmq.tgz` 是 `tasks.go` 中 `go:embed` 的包，Chart 版本 16.0.18、appVersion 4.2.1、默认 `replicaCount=1`。这只是当前本机包的证据，不证明客户实际安装的包、运行版本、Pod 数、覆盖值或队列类型。

## 处理方向

1. 由业务系统维护方定位注册时提交 `ha-all` 的代码或配置，对 RabbitMQ 4.x 停止提交 `ha-mode`、`ha-sync-mode` 等旧镜像策略；若策略仅含这些设置，应跳过创建该策略。若策略含其他有效字段，应按用途逐项保留，不能盲目删除。更改前确认实际请求及失败后的注册流程是否可安全重试。
2. 确认队列是否需要跨节点高可用。不需要复制时可评估继续使用经典队列；需要复制时评估 quorum queue，确认节点及多数派、持久性、队列声明参数和业务特性兼容。单节点或单副本并不能提供跨节点容错；更换队列类型和删除旧策略都不会自动迁移或复制既有消息。
3. 先盘点现有队列、策略、消息积压和客户端声明方式，再在测试环境验证迁移和故障恢复。经典队列不能原地转换成 quorum queue；对于既有数据，按官方迁移指引设计消息转移、业务切换和回退，切勿直接删除或重建生产队列，也不建议未验证地降级 RabbitMQ。
4. 检查客户实际 RabbitMQ 版本、vhost、策略、队列类型、节点数和注册请求的 HTTP 响应；修正后重新验证注册、AMQP 建连及发送消费，再按需求验证节点故障恢复。

## 验证边界

本次依据用户截图、官方文档及本机内嵌包只读分析，未访问客户环境、修改业务代码或运行配置，也未发布、重启、重试或执行业务消息测试；未确认客户实际修复或恢复。此案例保持 `unverified`。

## 来源

- 用户提供的脱敏业务日志截图。
- 本机 `g_kube_installer/cmd/kk/pkg/component/tasks.go:39` 和 `g_kube_installer/cmd/kk/pkg/component/rabbitmq.tgz`，仅说明本机仓库制品。
- RabbitMQ 官方：[4.0 变更说明](https://www.rabbitmq.com/docs/4.0/whats-new)、[经典镜像队列](https://www.rabbitmq.com/docs/3.13/ha)、[迁移至 quorum queue](https://www.rabbitmq.com/docs/3.13/migrate-mcq-to-qq)。

[返回案例索引](../README.md)
