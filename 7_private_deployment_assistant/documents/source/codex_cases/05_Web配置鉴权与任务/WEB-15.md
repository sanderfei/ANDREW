# WEB-15：PushAppImages 的 plainHTTP 与 skipTLSVerify 只控制传输

项目：g_web_installer。记录状态：源码结论。来源会话始于 2026-07-22，含之后续问。

适用标签：Kubernetes any；系统 any；安装模式 any。需要匹配目标接口、仓库类型和服务器实际协议。

## WEB-15 问题与表现

自建仓库镜像推送失败，想用 `skipTLSVerify` 修 HTTP/HTTPS 不匹配，或认为新增传输选项就可以去掉 Harbor 项目检查。

## WEB-15 最终根因与处理方案

协议选择、证书校验和仓库业务规则是三个层次。历史 `PushAppImages` 增加传输选项时，`plainHTTP` 决定是否使用 HTTP，`skipTLSVerify` 决定 HTTPS 是否验证证书；后者不会把 HTTP 请求变成 HTTPS，也不解决认证失败。

这两个选项用于最终镜像传输，不意味着绕过原来 Harbor 的状态、项目存在性或创建逻辑。后续对 `type: zot` 专门跳过 Harbor 项目 API 是另一个修改，见 REG-12。也不能把此 Web 接口的选项语义与旧 KK artifact push 中曾被忽略的同名字段混为一谈。

按真实监听协议配置传输选项，核对完整 registry host:port、认证和项目；受管离线仓库 HTTPS 444 的生成规则见 REG-04。优先建立正确证书信任，不将临时诊断设置当作所有环境的默认值。

## WEB-15 验证证据与限制

历史源码解释与选项传递分析；本条没有任意自建仓库的最终推送证明。实际 Harbor 核心推送验证见 REG-19，Zot 适配验证见 REG-12。本次未发起仓库操作。

## WEB-15 来源定位

- Codex 会话 `019f8890-65af-7ad1-accc-c33bdcc287a2`，始于 2026-07-22。

[返回案例索引](../README.md)
