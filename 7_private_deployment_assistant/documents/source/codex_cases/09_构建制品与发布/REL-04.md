# REL-04：Go默认构建因gpgme btrfs原生依赖失败

项目：g_kube_installer / g_web_installer。记录状态：代码已验证。来源会话起始日期：2026-08-12, 2026-08-20（含之后续问，不是本次现场检查日期）。

适用标签：Kubernetes any；系统 any；安装模式 any。any 表示历史证据未限定，需按实际版本再次核对；不是承诺所有环境兼容。

## REL-04 问题与表现

btrfs/version.h不存在、pkg-config/gpgme/gcc缺失，误认为新代码语法失败。

## REL-04 最终根因或已确认边界

containers/image等默认CGO分支拉入宿主原生依赖，项目已有可用排除标签。

## REL-04 处理方案

按仓库支持的CGO_ENABLED=0及exclude_graphdriver_devicemapper/exclude_graphdriver_btrfs/containers_image_openpgp标签运行针对目标包的测试/构建。既有vet失败需单独说明，不能把-vet=off编译通过当全量逻辑测试通过。

### REL-04 命令示例

在对应执行环境替换占位符，先核对版本/路径；本文件没有执行这些命令。

```bash
CGO_ENABLED=0 go build -tags "exclude_graphdriver_devicemapper exclude_graphdriver_btrfs containers_image_openpgp" ./cmd/server
```

## REL-04 验证证据与限制

多轮历史指定标签测试/构建通过；本轮纯文档未构建源码。

以上为历史归档结论，本次仅整理文档，未重新连接客户环境、部署或触发业务操作。

## REL-04 来源定位

- Codex 会话 `019ff4a4-8c23-7a63-aecb-9f31290a1918`；始于 2026-08-12。可按本条标题及关键错误定位相关提问与后续结论。
- Codex 会话 `01a01e56-f1c8-7c73-926c-5f4838ffbeb9`；始于 2026-08-20。可按本条标题及关键错误定位相关提问与后续结论。

[返回案例索引](../README.md)
