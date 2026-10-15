# Web / KK 历史部署案例索引

整理日期：2026-10-14。内容来自本机可访问的 Codex sessions / archived_sessions 和相关历史摘要，已按问题改写、去重、合并后续修正。原始会话、完整客户配置、密码、Token、私钥、签名 URL 不进入本目录。

本次扫描 421 份 JSONL，合并同一会话的重复副本后共 378 个会话。范围为 2026-04-10 至 2026-10-13 的本地可见记录；远端账号其他设备、已删除记录、只有截图而无可读正文的问题不能保证完整恢复。问答内容均按历史上下文理解，未重新验证现场。

持续补充：截至 2026-10-15，当前共 172 个案例（历史扫描形成 167 个，后续新增 5 个）；上述历史扫描范围和会话统计保持不变。

当前项目支持约定：K8s 1.23.10 为 Ubuntu/CentOS，1.32.8 为 Ubuntu。历史其他组件/Kubernetes版本仅作迁移背景；实际引用时必须匹配目标 Web/KK 二进制、Chart、OS、运行时和制品。

每个问题独立 Markdown，旁边的 `.md.metadata.json` 对接现有文件入库接口。标 `verified` 仅表示历史有实际功能证据；编译、模板、源代码、Pod状态验证不等同业务通过，统一 `unverified`。未知版本标 any，检索命中后仍需核对适用条件。未确认的问题保留排查方案，不虚构最终修复。

仅添加本地文档和元数据：没有向 Qdrant/pgvector 写入、没有注册 tool、没有开发 Agent、没有提交或发布代码。索引/覆盖说明默认是普通文档，批量入库时可优先选择各案例文件，避免索引重复污染检索。

状态含义：历史功能验证=当时真实业务/数据或协议检查；历史状态验证=对象/进程状态；代码已验证=测试/编译/渲染；源码结论=只读分析；待验证=根因/最终处理未闭环；撤回方案=历史明确未采用。

## 01_KK在线与离线安装（15）

| 案例 | 问题 | 状态 |
|---|---|---|
| [KK-O01](01_KK在线与离线安装/KK-O01.md) | 在线与离线模式的实际开关及三步安装 | 源码结论 |
| [KK-O02](01_KK在线与离线安装/KK-O02.md) | 1.23.10与1.32.8的运行时和配置差异 | 源码结论 |
| [KK-O03](01_KK在线与离线安装/KK-O03.md) | Web初始化离线仓库仍尝试从OBS下载制品 | 代码已验证 |
| [KK-O04](01_KK在线与离线安装/KK-O04.md) | 离线制品的宿主机路径与容器路径不一致 | 源码结论 |
| [KK-O05](01_KK在线与离线安装/KK-O05.md) | Harbor离线初始化回退到GitHub下载 | 待验证 |
| [KK-O06](01_KK在线与离线安装/KK-O06.md) | 离线初始化NFS依赖解包后未配置 | 历史功能验证 |
| [KK-O07](01_KK在线与离线安装/KK-O07.md) | dpkg前端锁被unattended-upgrade占用 | 待验证 |
| [KK-O08](01_KK在线与离线安装/KK-O08.md) | Ubuntu24.04离线ISO缺项与按OS版本选择 | 代码已验证 |
| [KK-O09](01_KK在线与离线安装/KK-O09.md) | 离线新增节点APT依赖冲突发生在join之前 | 待验证 |
| [KK-O10](01_KK在线与离线安装/KK-O10.md) | add nodes未先安装socat和conntrack依赖 | 代码已验证 |
| [KK-O11](01_KK在线与离线安装/KK-O11.md) | KKZONE区域设置在新增节点时丢失 | 代码已验证 |
| [KK-O12](01_KK在线与离线安装/KK-O12.md) | artifact export累计两小时超时和缓存复用 | 源码结论 |
| [KK-O13](01_KK在线与离线安装/KK-O13.md) | 导出下载curl56连接重置及9字节Not Found | 待验证 |
| [KK-O14](01_KK在线与离线安装/KK-O14.md) | ISO同步校验时报远端文件不存在 | 待验证 |
| [KK-O15](01_KK在线与离线安装/KK-O15.md) | 两个离线集群复用同一个registry | 源码结论 |

## 02_集群运行时与网络（11）

| 案例 | 问题 | 状态 |
|---|---|---|
| [KK-C01](02_集群运行时与网络/KK-C01.md) | 已有containerd关闭CRI导致unknown service runtime.v1 | 待验证 |
| [KK-C02](02_集群运行时与网络/KK-C02.md) | CoreDNS1.9.3不支持kubeadm1.32生成的新Corefile | 代码已验证 |
| [KK-C03](02_集群运行时与网络/KK-C03.md) | Calico等待逻辑目标数错误及无法持续轮询 | 待验证 |
| [KK-C04](02_集群运行时与网络/KK-C04.md) | Calico Init0/3因宿主机缺少bpffs目录 | 待验证 |
| [KK-C05](02_集群运行时与网络/KK-C05.md) | 通配域名A正常但AAAA返回SERVFAIL（2026-10-15 复核源码，1.27 现场待验证） | 历史功能验证 |
| [KK-C06](02_集群运行时与网络/KK-C06.md) | DNS域名配置和k8s地址网段混用 | 源码结论 |
| [KK-C07](02_集群运行时与网络/KK-C07.md) | 多Master的API VIP不是业务Ingress VIP | 源码结论 |
| [KK-C08](02_集群运行时与网络/KK-C08.md) | scheduler和controller-manager因续租超时重启 | 待验证 |
| [KK-C09](02_集群运行时与网络/KK-C09.md) | NodePort在master超时而worker正常 | 历史功能验证 |
| [KK-C10](02_集群运行时与网络/KK-C10.md) | kubectl和Helm能SSH执行但无法访问API | 源码结论 |
| [KK-C11](02_集群运行时与网络/KK-C11.md) | 离线节点重新加入时containerd2.2.1仓库配置冲突导致CRI缺失 | 待验证 |

## 03_Helm与组件部署（37）

| 案例 | 问题 | 状态 |
|---|---|---|
| [HELM-01](03_Helm与组件部署/HELM-01.md) | another operation in progress与pending修订 | 历史状态验证 |
| [HELM-02](03_Helm与组件部署/HELM-02.md) | ingress admission证书not yet valid | 待验证 |
| [HELM-03](03_Helm与组件部署/HELM-03.md) | Redis包缺common子Chart | 代码已验证 |
| [HELM-04](03_Helm与组件部署/HELM-04.md) | Bitnami非标准私库镜像被allowInsecureImages拦截 | 代码已验证 |
| [HELM-05](03_Helm与组件部署/HELM-05.md) | 升级Chart后私有registry覆盖无效 | 代码已验证 |
| [HELM-06](03_Helm与组件部署/HELM-06.md) | MySQL首启探针过短与Pinpoint初始化SQL失败 | 代码已验证 |
| [HELM-07](03_Helm与组件部署/HELM-07.md) | Kafka KRaft Secret被错误绑定SASL条件 | 代码已验证 |
| [HELM-08](03_Helm与组件部署/HELM-08.md) | 数据库依赖配置bothDB导致Apollo和Cadence传空参数 | 代码已验证 |
| [HELM-09](03_Helm与组件部署/HELM-09.md) | 组件安装依赖顺序与Ready不是同一保证 | 源码结论 |
| [HELM-10](03_Helm与组件部署/HELM-10.md) | Nacos Pending因PVC storageClassName为空或local错配 | 代码已验证 |
| [HELM-11](03_Helm与组件部署/HELM-11.md) | Nacos3初始化数据库缺config_info_gray等表 | 代码已验证 |
| [HELM-12](03_Helm与组件部署/HELM-12.md) | Nacos单副本cluster模式导致Distro未Ready和Seata503 | 历史功能验证 |
| [HELM-13](03_Helm与组件部署/HELM-13.md) | Nacos3健康检查端口和URL前缀不兼容 | 历史功能验证 |
| [HELM-14](03_Helm与组件部署/HELM-14.md) | MariaDB探针报Access denied后排除密码确认连接数耗尽 | 历史功能验证 |
| [HELM-15](03_Helm与组件部署/HELM-15.md) | Apollo数据库名大小写与DeletedAt schema问题 | 历史功能验证 |
| [HELM-16](03_Helm与组件部署/HELM-16.md) | Apollo Helm覆盖hosts数组导致http paths缺失 | 代码已验证 |
| [HELM-17](03_Helm与组件部署/HELM-17.md) | Seata使用旧Nacos域名或写死namespace | 历史功能验证 |
| [HELM-18](03_Helm与组件部署/HELM-18.md) | Seata store.db键及MySQL8驱动超时不兼容 | 历史功能验证 |
| [HELM-19](03_Helm与组件部署/HELM-19.md) | Nacos和Seata IngressClass为空或端口指向错误 | 代码已验证 |
| [HELM-20](03_Helm与组件部署/HELM-20.md) | RabbitMQ管理入口404因classless Ingress被忽略 | 历史功能验证 |
| [HELM-21](03_Helm与组件部署/HELM-21.md) | Milvus Pending因CPU requests预约满而非镜像缺失 | 历史功能验证 |
| [HELM-22](03_Helm与组件部署/HELM-22.md) | Milvus历史失败Hook Pod使Web健康状态误判 | 历史功能验证 |
| [HELM-23](03_Helm与组件部署/HELM-23.md) | Milvus账号配置路径与旧etcd数据保留 | 历史功能验证 |
| [HELM-24](03_Helm与组件部署/HELM-24.md) | Milvus升级的Woodpecker与StorageV2兼容 | 历史功能验证 |
| [HELM-25](03_Helm与组件部署/HELM-25.md) | Pinpoint HBase等待ZooKeeper端口不能证明quorum就绪 | 代码已验证 |
| [HELM-26](03_Helm与组件部署/HELM-26.md) | Pinpoint HBase后台进程退出、锁超时与启动探针修复（2026-10-15 更新） | 代码已验证，现场升级待验证 |
| [HELM-27](03_Helm与组件部署/HELM-27.md) | Pinpoint内置MySQL初始化表缺失与依赖分支变动 | 代码已验证 |
| [HELM-28](03_Helm与组件部署/HELM-28.md) | Elasticsearch升级后analysis插件缺失 | 历史功能验证 |
| [HELM-29](03_Helm与组件部署/HELM-29.md) | Neo4j默认资源被Web低值覆盖触发Chart校验 | 代码已验证 |
| [HELM-30](03_Helm与组件部署/HELM-30.md) | Neo4j对NAS只读snapshot递归chown失败 | 代码已验证 |
| [HELM-31](03_Helm与组件部署/HELM-31.md) | Cadence初始化缺少schema版本基线 | 代码已验证 |
| [HELM-32](03_Helm与组件部署/HELM-32.md) | RocketMQ Proxy Service targetPort指向7001错误 | 历史功能验证 |
| [HELM-33](03_Helm与组件部署/HELM-33.md) | EMQX sysctl initContainer mount权限不足 | 待验证 |
| [HELM-34](03_Helm与组件部署/HELM-34.md) | 多release数据库端口和资源名称冲突 | 历史功能验证 |
| [HELM-35](03_Helm与组件部署/HELM-35.md) | Elasticsearch deployed但内存requests满导致无Endpoint | 历史功能验证 |
| [HELM-36](03_Helm与组件部署/HELM-36.md) | PostgreSQL镜像含扩展文件不等于每个数据库启用vector | 历史功能验证 |
| [HELM-37](03_Helm与组件部署/HELM-37.md) | Elasticsearch两版部署设计、Service兼容与手动升级 | 源码结论 |

## 04_Zot_Harbor与镜像仓库（19）

| 案例 | 问题 | 状态 |
|---|---|---|
| [REG-01](04_Zot_Harbor与镜像仓库/REG-01.md) | init registry成功后UpdateLocalHosts127或resource busy | 代码已验证 |
| [REG-02](04_Zot_Harbor与镜像仓库/REG-02.md) | Harbor初始化密码和auths推送密码不一致 | 历史功能验证 |
| [REG-03](04_Zot_Harbor与镜像仓库/REG-03.md) | Harbor缺少dmp和cloud项目导致push拒绝 | 代码已验证 |
| [REG-04](04_Zot_Harbor与镜像仓库/REG-04.md) | Harbor或Zot的HTTPS444被客户端当作HTTP | 代码已验证 |
| [REG-05](04_Zot_Harbor与镜像仓库/REG-05.md) | 证书错误x509与no basic auth credentials是两件事 | 待验证 |
| [REG-06](04_Zot_Harbor与镜像仓库/REG-06.md) | containerd1.x使用certs.d而非旧inline镜像配置 | 源码结论 |
| [REG-07](04_Zot_Harbor与镜像仓库/REG-07.md) | Zot缺少离线二进制不能靠init自动下载 | 代码已验证 |
| [REG-08](04_Zot_Harbor与镜像仓库/REG-08.md) | Zot已启动但v2空正文被就绪检查误判 | 历史功能验证 |
| [REG-09](04_Zot_Harbor与镜像仓库/REG-09.md) | Zot就绪检查节点缺curl | 待验证 |
| [REG-10](04_Zot_Harbor与镜像仓库/REG-10.md) | Zot允许匿名pull但push仍需认证 | 代码已验证 |
| [REG-11](04_Zot_Harbor与镜像仓库/REG-11.md) | Zot数据目录改为data-zot不自动迁移旧数据 | 待验证 |
| [REG-12](04_Zot_Harbor与镜像仓库/REG-12.md) | PushAppImages对Zot误调用Harbor项目API | 历史功能验证 |
| [REG-13](04_Zot_Harbor与镜像仓库/REG-13.md) | HarborStatus端口可连不等于镜像仓库功能正常 | 代码已验证 |
| [REG-14](04_Zot_Harbor与镜像仓库/REG-14.md) | Harbor数据库dirty82导致core与jobservice重启 | 历史状态验证 |
| [REG-15](04_Zot_Harbor与镜像仓库/REG-15.md) | 镜像push401与PUT blob403不能混为密码或满盘 | 待验证 |
| [REG-16](04_Zot_Harbor与镜像仓库/REG-16.md) | manifest镜像清单与实际嵌入Chart不一致 | 代码已验证 |
| [REG-17](04_Zot_Harbor与镜像仓库/REG-17.md) | Zot特殊字符认证参数及NAT IP证书SAN风险 | 待验证 |
| [REG-18](04_Zot_Harbor与镜像仓库/REG-18.md) | 新artifact无images但旧工作目录镜像被继续推送 | 待验证 |
| [REG-19](04_Zot_Harbor与镜像仓库/REG-19.md) | Harbor删除非空项目412与应用推送环境依赖 | 历史功能验证 |

## 05_Web配置鉴权与任务（15）

| 案例 | 问题 | 状态 |
|---|---|---|
| [WEB-01](05_Web配置鉴权与任务/WEB-01.md) | 全局app.yaml与集群config.yaml及容器数据挂载 | 代码已验证 |
| [WEB-02](05_Web配置鉴权与任务/WEB-02.md) | ComponentsStatus私钥路径没有透传 | 代码已验证 |
| [WEB-03](05_Web配置鉴权与任务/WEB-03.md) | 组件卸载SSH旧指纹和私钥支持缺失 | 代码已验证 |
| [WEB-04](05_Web配置鉴权与任务/WEB-04.md) | Velero及旧导入脚本仍写死root密码SSH | 待验证 |
| [WEB-05](05_Web配置鉴权与任务/WEB-05.md) | users.json更新后权限不生效 | 历史功能验证 |
| [WEB-06](05_Web配置鉴权与任务/WEB-06.md) | v3 login先被本地JWT拦截 | 待验证 |
| [WEB-07](05_Web配置鉴权与任务/WEB-07.md) | IAM401应用授权与实际网页应用不一致 | 历史功能验证 |
| [WEB-08](05_Web配置鉴权与任务/WEB-08.md) | 网关示例bucket不等于实际授权桶 | 历史功能验证 |
| [WEB-09](05_Web配置鉴权与任务/WEB-09.md) | TOKEN_INVALID需区分应用和用户凭据与会话 | 待验证 |
| [WEB-10](05_Web配置鉴权与任务/WEB-10.md) | runningProcesses并发注册和kill存在数据竞争 | 代码已验证 |
| [WEB-11](05_Web配置鉴权与任务/WEB-11.md) | NFS存储位置和任务远程执行位置是两个配置 | 代码已验证 |
| [WEB-12](05_Web配置鉴权与任务/WEB-12.md) | 下载兑换token落盘不能异步返回制造刚申请就失效 | 代码已验证 |
| [WEB-13](05_Web配置鉴权与任务/WEB-13.md) | 备份配置响应多一层config造成旧页面读不到 | 待验证 |

| [WEB-14](05_Web配置鉴权与任务/WEB-14.md) | InstallAppV1 的安装与镜像推送分支及文件格式 | 源码结论 |
| [WEB-15](05_Web配置鉴权与任务/WEB-15.md) | PushAppImages 的 plainHTTP 与 skipTLSVerify 只控制传输 | 源码结论 |

## 06_Web备份恢复与导入（32）

| 案例 | 问题 | 状态 |
|---|---|---|
| [BK-01](06_Web备份恢复与导入/BK-01.md) | backup config零字节导致unexpected end of JSON input | 历史功能验证 |
| [BK-02](06_Web备份恢复与导入/BK-02.md) | 备份工具安装在Web端而非只看数据库Pod | 历史功能验证 |
| [BK-03](06_Web备份恢复与导入/BK-03.md) | MariaDB mysqldump COLUMN_STATISTICS导致假成功小包 | 历史功能验证 |
| [BK-04](06_Web备份恢复与导入/BK-04.md) | Milvus备份名称前缀与字符限制 | 历史功能验证 |
| [BK-05](06_Web备份恢复与导入/BK-05.md) | Milvus备份141因awk早退触发SIGPIPE | 历史功能验证 |
| [BK-06](06_Web备份恢复与导入/BK-06.md) | 备份warning是最近任务失败不是组件健康 | 历史功能验证 |
| [BK-07](06_Web备份恢复与导入/BK-07.md) | cron未执行因按服务端EDT而非北京时间 | 历史功能验证 |
| [BK-08](06_Web备份恢复与导入/BK-08.md) | 同一分钟多个备份目标并发与锁范围 | 源码结论 |
| [BK-09](06_Web备份恢复与导入/BK-09.md) | 立即备份trigger传状态对象导致JSON解析失败 | 待验证 |
| [BK-10](06_Web备份恢复与导入/BK-10.md) | Images备份配置残留database_filter | 历史功能验证 |
| [BK-11](06_Web备份恢复与导入/BK-11.md) | MongoDB过滤误用mongodump不支持的ns参数 | 代码已验证 |
| [BK-12](06_Web备份恢复与导入/BK-12.md) | MongoDB config.system.sessions读取被拒 | 历史功能验证 |
| [BK-13](06_Web备份恢复与导入/BK-13.md) | 数据库列表空数组因kubectl exec未传stdin | 历史功能验证 |
| [BK-14](06_Web备份恢复与导入/BK-14.md) | ES过滤全部索引生成空包却显示成功 | 历史功能验证 |
| [BK-15](06_Web备份恢复与导入/BK-15.md) | Neo4j3.5不支持SHOW DATABASES及sh执行Bash数组 | 历史功能验证 |
| [BK-16](06_Web备份恢复与导入/BK-16.md) | Neo4j5.26.28新版Chart与旧离线dump路径不匹配 | 待验证 |
| [BK-17](06_Web备份恢复与导入/BK-17.md) | Neo4j离线备份缩容及失败恢复方案曾被撤回 | 撤回方案 |
| [BK-18](06_Web备份恢复与导入/BK-18.md) | MongoDB导入包伪装tar.gz且多套一层目录 | 待验证 |
| [BK-19](06_Web备份恢复与导入/BK-19.md) | MariaDB和Elasticsearch导入包合同不匹配 | 源码结论 |
| [BK-20](06_Web备份恢复与导入/BK-20.md) | MySQL导入不能复用为PostgreSQL/pgvector导入 | 历史功能验证 |
| [BK-21](06_Web备份恢复与导入/BK-21.md) | Web宿主机缺psql pg_restore与目标PG未Ready | 源码结论 |
| [BK-22](06_Web备份恢复与导入/BK-22.md) | Atlas no-change文本写入SQL导致apply语法错误 | 历史功能验证 |
| [BK-23](06_Web备份恢复与导入/BK-23.md) | MariaDB schema-sync缺USE和完全限定表名风险 | 源码结论 |
| [BK-24](06_Web备份恢复与导入/BK-24.md) | 多库DDL半成功不能用一次事务整体回滚 | 历史功能验证 |
| [BK-25](06_Web备份恢复与导入/BK-25.md) | Velero迁移Kubernetes资源不自动备份所有NFS文件 | 源码结论 |
| [BK-26](06_Web备份恢复与导入/BK-26.md) | 备份目录和NFS上传成功后的本地清理 | 历史功能验证 |
| [BK-27](06_Web备份恢复与导入/BK-27.md) | schema-sync文件名带连字符被错误截为库名 | 历史功能验证 |
| [BK-28](06_Web备份恢复与导入/BK-28.md) | prepare漏过滤版本注释DROP导致误删原业务库 | 历史功能验证 |
| [BK-29](06_Web备份恢复与导入/BK-29.md) | DROP保护正则误将datapolicyschema表名识为SCHEMA | 历史功能验证 |
| [BK-30](06_Web备份恢复与导入/BK-30.md) | lastpid跨时区按PID名字排序返回旧任务 | 待验证 |
| [BK-31](06_Web备份恢复与导入/BK-31.md) | 备份配置接口接受只有目录没有cluster config的伪集群 | 代码已验证 |
| [BK-32](06_Web备份恢复与导入/BK-32.md) | Images备份仍用Docker CLI而推送接口已改Go | 代码已验证 |

## 07_OBS网关与文件传输（19）

| 案例 | 问题 | 状态 |
|---|---|---|
| [OBS-01](07_OBS网关与文件传输/OBS-01.md) | 大文件本地分片不等于OBS multipart | 历史功能验证 |
| [OBS-02](07_OBS网关与文件传输/OBS-02.md) | 408 RequestTimeout在OBS而非浏览器HTTP超时 | 待验证 |
| [OBS-03](07_OBS网关与文件传输/OBS-03.md) | NoSuchUpload可能表示multipart已完成 | 历史功能验证 |
| [OBS-04](07_OBS网关与文件传输/OBS-04.md) | 旧docker_push依赖Docker CLI导致command not found | 代码已验证 |
| [OBS-05](07_OBS网关与文件传输/OBS-05.md) | registry上传ECONNRESET因同步长任务跨HTTP窗口 | 代码已验证 |
| [OBS-06](07_OBS网关与文件传输/OBS-06.md) | 大文件下载200 pending及WriteTimeout限制 | 代码已验证 |
| [OBS-07](07_OBS网关与文件传输/OBS-07.md) | 外层镜像包嵌套tar不能直接docker load | 历史功能验证 |
| [OBS-08](07_OBS网关与文件传输/OBS-08.md) | tar文件名包含完整钉钉URL及写归档无进度 | 待验证 |
| [OBS-09](07_OBS网关与文件传输/OBS-09.md) | 并发打包任务同名临时文件和目标key冲突 | 待验证 |
| [OBS-10](07_OBS网关与文件传输/OBS-10.md) | OBS403 AccessDenied只能确认当前身份拒绝 | 待验证 |
| [OBS-11](07_OBS网关与文件传输/OBS-11.md) | V3元数据30秒超时误用于大文件传输 | 代码已验证 |
| [OBS-12](07_OBS网关与文件传输/OBS-12.md) | V3上传10分钟context canceled实际是Axios600000ms | 待验证 |
| [OBS-13](07_OBS网关与文件传输/OBS-13.md) | V3文件下载转发链路慢但未复现持续0B | 历史功能验证 |
| [OBS-14](07_OBS网关与文件传输/OBS-14.md) | V3双签名URL的有效期读取与配置 | 历史功能验证 |
| [OBS-15](07_OBS网关与文件传输/OBS-15.md) | OBS网关目录重命名不是文件系统mv | 历史功能验证 |
| [OBS-16](07_OBS网关与文件传输/OBS-16.md) | V3内容类型校验和错误日志缺上游正文 | 代码已验证 |
| [OBS-17](07_OBS网关与文件传输/OBS-17.md) | V3镜像归档registry重命名只改目标RepoTags | 代码已验证 |
| [OBS-18](07_OBS网关与文件传输/OBS-18.md) | V3上传取消日志归属及网关与接口超时边界 | 待验证 |
| [OBS-19](07_OBS网关与文件传输/OBS-19.md) | 本地未提交改动范围包含OBS落盘离线安装与镜像归档重命名 | 源码结论 |

## 08_NFS与持久化存储（14）

| 案例 | 问题 | 状态 |
|---|---|---|
| [NFS-01](08_NFS与持久化存储/NFS-01.md) | 多个roleGroups nfs节点不等于HA | 代码已验证 |
| [NFS-02](08_NFS与持久化存储/NFS-02.md) | PV PVC与NFS目录及卸载后旧数据复用 | 源码结论 |
| [NFS-03](08_NFS与持久化存储/NFS-03.md) | Web NFSv4客户端不能自动兼容v3 | 历史功能验证 |
| [NFS-04](08_NFS与持久化存储/NFS-04.md) | NFS大文件10065因单次WRITE请求过大 | 历史功能验证 |
| [NFS-05](08_NFS与持久化存储/NFS-05.md) | NAS导出权限和服务配置问题不应盲目降级协议 | 源码结论 |
| [NFS-06](08_NFS与持久化存储/NFS-06.md) | Web部署位置不能用硬编码data-nfs代替网络存储 | 源码结论 |
| [NFS-07](08_NFS与持久化存储/NFS-07.md) | NFS下载缓存保留与保留策略目标一致性 | 源码结论 |
| [NFS-08](08_NFS与持久化存储/NFS-08.md) | NFS4ERR_PERM因高位源端口需要exports匹配 | 历史功能验证 |
| [NFS-09](08_NFS与持久化存储/NFS-09.md) | NFS端口填2049但实际测试服务20549 | 待验证 |
| [NFS-10](08_NFS与持久化存储/NFS-10.md) | NFS删除持全局锁导致所有集群配置查询阻塞 | 历史功能验证 |
| [NFS-11](08_NFS与持久化存储/NFS-11.md) | 自动retention删除NFS失败的记录与clean_fail | 历史功能验证 |
| [NFS-12](08_NFS与持久化存储/NFS-12.md) | immutable手动删除限制历史被明确移除 | 历史功能验证 |
| [NFS-13](08_NFS与持久化存储/NFS-13.md) | NFS备份脚本和上传两阶段超时不能只给一次60分钟 | 代码已验证 |
| [NFS-14](08_NFS与持久化存储/NFS-14.md) | 缩短retention测试策略误删真实历史备份 | 历史状态验证 |

## 09_构建制品与发布（10）

| 案例 | 问题 | 状态 |
|---|---|---|
| [REL-01](09_构建制品与发布/REL-01.md) | 编辑解压Chart未重新打包实际嵌入tgz | 代码已验证 |
| [REL-02](09_构建制品与发布/REL-02.md) | Web重启不会更新固定g-web-installer-kk | 源码结论 |
| [REL-03](09_构建制品与发布/REL-03.md) | 改manifest后旧artifact和镜像缓存不会自动变化 | 代码已验证 |
| [REL-04](09_构建制品与发布/REL-04.md) | Go默认构建因gpgme btrfs原生依赖失败 | 代码已验证 |
| [REL-05](09_构建制品与发布/REL-05.md) | make kk的GIT_MAJOR警告与真实编译失败区别 | 代码已验证 |
| [REL-06](09_构建制品与发布/REL-06.md) | 错误发布仓库路径或构建旧分支 | 历史状态验证 |
| [REL-07](09_构建制品与发布/REL-07.md) | SSH节点重装后指纹与免密认证变化 | 源码结论 |
| [REL-08](09_构建制品与发布/REL-08.md) | 121磁盘不足时保留活动镜像pull | 历史功能验证 |
| [REL-09](09_构建制品与发布/REL-09.md) | Chart应用版本与镜像tag升级不能仅看包名 | 源码结论 |
| [REL-10](09_构建制品与发布/REL-10.md) | Web脚本容器部署与121宿主机部署及containerd配置来源 | 源码结论 |

[历史扫描覆盖说明](coverage.md)记录来源和无法闭环的限制。
