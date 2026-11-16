# Codex 换电脑迁移

本文记录如何在新电脑恢复 Codex 的本地记忆、聊天历史和配置。新电脑的 Windows、WSL、VS Code 及仓库准备见 [setup-new-machine.md](setup-new-machine.md)。

如果主要目的是让 Codex 协助梳理项目经历和写简历，优先使用精简的 [项目简历素材](codex-resume-context.md)：新电脑拉取仓库后，在对话中让 Codex 阅读该文件即可。按本人确认的经历持续更新素材，不需要恢复全部聊天记录；这也不会自动恢复原始会话或本地记忆。以下步骤适用于确实需要迁移本地数据的情况。

## 先区分数据

Codex IDE 扩展使用它连接的主机上的本地数据：如果 VS Code 通过 WSL 或 SSH 工作，需要在相应的 WSL 或远程主机操作。默认目录是 `~/.codex`；设置了 `CODEX_HOME` 时，以该变量指向的目录为准。ChatGPT 网页记忆与 Codex 本地记忆分开。登录相同账号不等于本地数据自动同步。[官方说明](https://learn.chatgpt.com/docs/customization/memories)

| 数据 | 作用 |
| --- | --- |
| `memories/`、可能存在的 `memories_v2/` | 历史工作的记忆摘要，不等于完整对话 |
| `sessions/`、`archived_sessions/` | 本地会话记录 |
| `session_index.jsonl`、`*.sqlite` 及其关联文件 | 本地会话和记忆等索引、状态 |
| `attachments/` | 本地附件 |
| `config.toml`、`AGENTS.md`、`skills/`、`rules/`、`hooks/`、`references/` | 配置、工作约定和扩展能力 |
| `plugins/` | 插件及缓存；新机器可能需要重新安装和授权 |

2026-11-16 检查时，旧机器的会话及归档约 2.5 GiB；仅 `thread_history_1.sqlite` 就约 220 MB。它们会持续增长，不能假定适合普通 Git 文件管理。

**本仓库是公开仓库，拉取代码不会自动带来这些本地数据。** 聊天、附件、记忆和配置可能包含私有信息；不要将未经本人审阅的数据提交到公开仓库。不要复制登录凭据、API Key、Token 或密码，在新电脑重新登录并重新配置。项目级 `AGENTS.md` 和仓库文档随对应项目迁移。

## 1. 在旧电脑准备快照

1. 结束正在进行的任务，关闭所有使用该 Codex 目录的 VS Code、Codex CLI 和后台进程。确认进程完全退出，再复制 SQLite 数据库和关联文件；不要在数据库仍被写入时只复制 `.sqlite` 主文件。
2. 根据上表选择要迁移的内容。本人审阅所选内容并排除不适合传输的敏感数据；完整会话可能包含工具输出和附件，仅排除登录文件不足以保证无敏感内容。
3. 把审阅后的数据通过可信的私密渠道传输到新电脑。保存备份时注意文件权限；不要把原始数据或凭据提交到公开仓库。

如果旧电脑目录为默认位置、且已经审阅并决定传输以下数据，可以在旧电脑终端制作快照。命令只包含当前机器已存在的路径；如有 `memories_v2/` 或其他需要的数据，审阅后另行加入。生成的压缩包本身也必须按私有数据保管。

```bash
cd ~/.codex
```

```bash
tar -czf ~/codex-migration.tar.gz \
  memories sessions archived_sessions session_index.jsonl attachments \
  config.toml AGENTS.md skills plugins references rules hooks \
  ./*.sqlite*
```

这是一次快照，不会自动包含之后产生的新会话或记忆。不同版本可能增删文件；制作快照前检查实际目录。不要将运行中的两台机器指向同一份同步中的 SQLite 数据库。

## 2. 在新电脑恢复

1. 按新机搭建文档安装 VS Code、Codex 扩展和 WSL；让 Codex 在目标环境启动一次并登录，然后退出所有相关进程。
2. 将快照传入目标环境，先解压到独立目录查看：

   ```bash
   mkdir -p ~/codex-migration-check
   tar -xzf ~/codex-migration.tar.gz -C ~/codex-migration-check
   ```

3. 对照上表，将需要的文件和目录复制到目标环境的 `~/.codex/`，或实际的 `CODEX_HOME`。如果目标位置已有同名数据，先保留原文件，再决定如何处理；不要直接覆盖新机器的数据库或已有会话，也不要尝试直接合并两个 SQLite 文件。
4. 检查 `config.toml`、`AGENTS.md` 和脚本中旧机器的绝对路径，按新环境调整。项目仓库也需要单独克隆，旧会话中的项目路径不会自动迁移。
5. 按需重新安装插件、MCP 服务和依赖，并在新电脑重新登录、授权。插件缓存或旧路径存在，不代表外部服务可用。

若本地记忆未启用，在 `config.toml` 已有的 `[features]` 段中添加 `memories = true`；不要创建重复的 `[features]` 段。也可通过 `/memories` 查看当前会话的记忆选项。具体选项见[官方记忆文档](https://learn.chatgpt.com/docs/customization/memories)。

## 3. 验证

在新电脑的目标工作区打开 Codex：

1. 查看历史列表，打开几条旧会话并检查能否继续；必要时确认其项目目录和模型提供方。
2. 新开一个会话，询问一项旧记忆中的工作偏好，检查是否能使用记忆。
3. 按需验证自定义技能、MCP、插件和相关项目工具。

复制本地状态不是官方承诺的完整跨机恢复方式：版本、工作区路径和外部服务可能影响恢复，必须以新电脑实际验证结果为准。关键、必须长期遵守的工作约定应保存在相关项目的 `AGENTS.md` 或文档中。
