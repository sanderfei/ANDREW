# HELM-42：KK可安装组件的功能分类与基础组件边界

项目：g_kube_installer / g_web_installer。记录日期：2026-10-22。记录状态：源码功能概览，现场安装与业务功能未验证。

适用环境：本地 KK test 分支 HEAD `9a73986d8382ce2830273c2c01ba7f404598b5fc` 的组件 Module 与任务实现，以及本地 Web 组件目录。未指定现场 Kubernetes/OS 版本；清单表示当前源码支持的安装入口，不代表目标集群已经安装全部组件。

## HELM-42 问题与表现

用户希望简述 KK 安装的各个组件有什么功能。本轮没有提供故障现象，不涉及部署变更。

## HELM-42 最终结论与组件功能

基础组件模块包含以下 3 项：

| 组件 | 主要功能 |
|---|---|
| Ingress-Nginx | 将外部 HTTP/HTTPS 请求按域名、路径转发到集群内服务 |
| NFS Provisioner | 基于 NFS 为持久化卷申请动态创建存储目录 |
| Headlamp | 提供 Kubernetes 资源的可视化管理界面 |

KK 另有以下 20 个按需组件安装分支：

| 组件 | 主要功能 |
|---|---|
| MySQL | 关系数据库，保存订单、用户等结构化业务数据 |
| MariaDB | 关系数据库，也供部分其他组件存放状态或配置数据 |
| PostgreSQL | 关系数据库，支持丰富的数据类型和扩展能力 |
| pgvector | PostgreSQL 向量扩展，用于向量存储与相似度检索 |
| Redis | 内存数据存储，常用于缓存、计数等 |
| MongoDB | 文档数据库，保存 JSON 风格的文档数据 |
| Neo4j | 图数据库，查询实体关系和多跳关联 |
| StarRocks | 分析型数据库，用于报表、聚合和 OLAP 查询 |
| RabbitMQ | 消息队列，支持业务消息路由和异步处理 |
| Kafka | 事件流平台，用于高吞吐事件传输与消费 |
| RocketMQ | 消息中间件，用于业务异步处理和服务解耦 |
| MQTT / EMQX | MQTT 消息服务，连接设备并进行发布订阅消息传输 |
| Apollo | 配置中心，集中管理和发布应用配置 |
| Nacos | 服务注册发现和配置管理 |
| Seata | 协调跨服务、跨数据库的分布式事务 |
| Harbor | 镜像仓库，集中保存和管理容器镜像 |
| Elasticsearch | 全文检索与搜索分析 |
| Cadence | 持久化业务工作流，编排步骤并处理重试和故障恢复 |
| Milvus | 向量数据库，用于向量相似度检索 |
| Pinpoint | APM 与调用链追踪，分析请求路径和性能瓶颈 |

## HELM-42 名称及职责边界

- KK 的 `mqtt` 组件分支实际安装 EMQX；`elastic` 对应 Elasticsearch。
- pgvector 是 PostgreSQL 扩展，不是独立于 PostgreSQL 的数据库。KK 任务检查 PostgreSQL 依赖，并执行相应镜像升级和扩展初始化 Job。
- 当前 Web 目录列出其中 19 项，MySQL 行被注释；这不改变 KK 仍有 MySQL 安装分支的源码事实。不能将 Web 可选列表、KK 支持清单与现场已安装清单混为一谈。
- 容器运行时、etcd、Kubernetes、CNI 和 CoreDNS 属于创建集群的核心流程，不计入上述 20 项业务组件。Zot 属于单独的镜像仓库初始化路径，也不计入此清单。
- 安装中间件后，应用仍需完成连接、认证、客户端或 Agent 接入及业务配置。安装完成不代表缓存、消息、调用链或分布式事务已被具体业务使用；Seata 接入边界另见 [HELM-41](HELM-41.md)。

## HELM-42 处理方案与后续检查

先按业务需要选择组件，再确认目标环境实际安装项、运行配置和应用接入。涉及功能验收时，应执行对应的数据读写、消息收发、检索、工作流或事务测试，不能用安装入口存在、Helm deployed 或 Pod Running 代替业务验证。本轮没有执行这些后续操作。

## HELM-42 验证结果与限制

已只读核对 KK 基础模块、20 项组件分支、MQTT 别名、pgvector 任务与 Web 目录。未修改业务代码或安装包，未连接目标集群、安装、重启或执行功能测试。metadata 保持 unverified；仅新增本地案例、元数据与索引，未提交、推送或写入向量库。

## HELM-42 来源定位

- `g_kube_installer/cmd/kk/pkg/component/module.go:42`：基础组件模块；`:55`：20 项按需组件分支。
- `g_kube_installer/cmd/kk/pkg/component/tasks.go:578`：pgvector 依赖；`:605`：PostgreSQL 升级及扩展 Job；`:1088`：MQTT/EMQX 部署实现。
- `g_web_installer/internal/service/component/component_list.go:44`：Web 目录及被注释的 MySQL 项。
- `g_kube_installer/cmd/kk/pkg/pipelines/create_cluster.go:75`：集群核心流程；独立 `init_registry` 路径用于镜像仓库初始化。
- 基本产品职责参考：[Cadence 工作流](https://cadenceworkflow.io/docs/concepts/workflows)、[StarRocks 简介](https://docs.starrocks.io/docs/introduction/StarRocks_intro/)、[EMQX 文档](https://docs.emqx.com/en/emqx/latest/)、[Milvus 概述](https://milvus.io/docs/overview.md)。产品功能说明不代表本项目已启用其全部功能，也不用于推断现场版本或企业版授权。

[返回案例索引](../README.md)
