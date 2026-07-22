# Andrew 新电脑环境搭建（Windows + WSL2 + VS Code）

> 目标：从一台空白 Windows 电脑开始，先跑通 `3_rag_from_scratch` 的离线 Part 1，再按需启用在线 `ep-qwen2.5-72b` 和 Codex 插件。
>
> 本文基于 2026-07-16 已验证环境整理：Ubuntu 24.04、Python 3.12、FastEmbed 0.8、本地多语言 MiniLM。

## 最终环境

| 项目 | 建议配置 |
| --- | --- |
| Windows | Windows 11 + WSL2 |
| Linux | Ubuntu 24.04 LTS |
| Python | 3.12 + 仓库内 `.venv` |
| 项目目录 | WSL 文件系统中的 `~/code/andrew` |
| 本地 Embedding | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| 推理方式 | FastEmbed + ONNX Runtime，CPU 即可，384 维 |
| 在线生成 | 可选的 `ep-qwen2.5-72b` |

建议至少预留 1.5 GB：当前 `.venv` 约 716 MB，本地模型约 122 MB，另需给代码和缓存留空间。本地 Embedding 不需要显卡，也不需要 `embedding-3` 权限。

## 1. 安装 WSL2 和 Ubuntu

在 Windows 的“管理员 PowerShell”中运行：

```powershell
wsl --list --online
wsl --install -d Ubuntu-24.04
wsl --update
wsl -l -v
```

如果在线列表中的发行版名称略有不同，以 `wsl --list --online` 的实际名称为准。按系统提示重启 Windows，首次打开 Ubuntu 时创建 Linux 用户名和密码。

进入 Ubuntu 后验证：

```bash
cat /etc/os-release
uname -r
python3 --version
```

目标是 Ubuntu 24.04、WSL 版本为 2、Python 为 3.12 左右。

## 2. 安装 Linux 基础工具

在 Ubuntu 终端运行：

```bash
sudo apt update
sudo apt install -y git curl build-essential python3 python3-venv python3-pip
```

配置 Git 提交身份，值替换成自己的：

```bash
git config --global user.name "你的 GitHub 用户名"
git config --global user.email "你的 GitHub 邮箱"
```

仓库是公开的，克隆不需要登录。以后要从家里电脑推送代码，推荐另外安装 GitHub CLI 并完成一次登录：

```bash
sudo apt install -y gh
gh auth login
gh auth setup-git
gh auth status
```

`gh auth login` 按提示选择 `GitHub.com`、`HTTPS` 和浏览器登录。正常情况下，验证成功后日常 `git push` 不会每次都要求重新登录。

## 3. 安装 VS Code 并进入 WSL

先在 Windows 安装 VS Code，再安装以下扩展：

| 扩展 | ID | 是否必需 |
| --- | --- | --- |
| WSL | `ms-vscode-remote.remote-wsl` | 必需 |
| Python | `ms-python.python` | 必需 |
| Pylance | `ms-python.vscode-pylance` | 推荐 |
| Codex | `openai.chatgpt` | 学习时推荐 |

项目和 Python 环境都放在 WSL 的 Linux 文件系统中，不放在 `/mnt/c`。后续克隆完成后，在 Ubuntu 终端运行：

```bash
code ~/code/andrew
```

确认 VS Code 左下角显示 `WSL: Ubuntu`。仓库已经跟踪 `.vscode/settings.json`，创建 `.venv` 后会自动指向 `${workspaceFolder}/.venv/bin/python`；如果没有生效，执行 `Python: Select Interpreter` 手动选择它。

## 4. 克隆仓库

```bash
mkdir -p ~/code
git clone https://github.com/sanderfei/ANDREW.git ~/code/andrew
cd ~/code/andrew
git status --short --branch
```

以后继续学习前只需更新：

```bash
cd ~/code/andrew
git pull --ff-only
```

## 5. 创建 Python 虚拟环境

```bash
cd ~/code/andrew
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r 3_rag_from_scratch/requirements.txt
.venv/bin/python -m pip check
```

先用完全不下载模型的教学哈希模式验证 Python 和 LangChain：

```bash
.venv/bin/python 3_rag_from_scratch/part1_overview.py --embedding hash
```

看到 `indexed_chunk_count` 为 `4` 且正常输出答案，说明 Python、依赖和代码层已经就绪。

当前 `requirements.txt` 使用兼容版本范围，不是严格锁定文件。工作机已验证的核心版本是：

```text
Python 3.12.3
langchain-core 1.4.8
langchain-openai 1.2.2
langchain-text-splitters 1.1.2
langchain-community 0.4.2
fastembed 0.8.0
onnxruntime 1.27.0
```

如果未来安装了更新版本后出现不兼容，可先按这组版本定位依赖漂移。

## 6. 安装本地 Embedding 模型

### 推荐：从 ModelScope 下载已验证的量化模型

当前工作机使用的是 AVX2 量化 ONNX。先确认家里电脑的 CPU 支持 AVX2：

```bash
grep -qw avx2 /proc/cpuinfo && echo "AVX2 OK" || echo "没有 AVX2，请使用后面的自动下载方式"
```

输出 `AVX2 OK` 后运行：

```bash
.venv/bin/python -m pip install "modelscope==1.38.1"

MODEL_DIR="$HOME/.cache/fastembed/paraphrase-multilingual-MiniLM-L12-v2-modelscope"
mkdir -p "$MODEL_DIR"

.venv/bin/modelscope download \
  sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
  config.json \
  tokenizer.json \
  tokenizer_config.json \
  special_tokens_map.json \
  onnx/model_quint8_avx2.onnx \
  --revision 5f5b1cee6aeb8bd07d715a425dbe588f6c29d7df \
  --local-dir "$MODEL_DIR"

ln -sfn onnx/model_quint8_avx2.onnx "$MODEL_DIR/model_optimized.onnx"
```

验证模型：

```bash
test -f "$MODEL_DIR/model_optimized.onnx" && echo "模型文件就绪"
du -sh "$MODEL_DIR"
sha256sum "$MODEL_DIR/model_optimized.onnx"
```

本次固定版本的预期结果约为 `122M`，ONNX SHA256 为：

```text
98a01d88b7de996cdea58c32ca71208c09968d143798814b2ea09d3439dc334f
```

`model_optimized.onnx` 软链接不能省略：仓库代码用它判断是否存在可直接加载的本地模型目录。

### 备选：让 FastEmbed 自动下载

如果 CPU 不支持 AVX2，或者不想安装 ModelScope，可直接运行：

```bash
.venv/bin/python 3_rag_from_scratch/part1_overview.py
```

当上面的固定本地目录不存在时，FastEmbed 会从其默认模型源下载兼容模型到 `~/.cache/fastembed`。首次运行需要联网并下载约 120–220 MB，后续会复用缓存。如果下载一直卡住，先回到 `--embedding hash` 验证其余环境，再使用 ModelScope 方案排除 Hugging Face 网络问题。

## 7. 验证本地 RAG

使用 ModelScope 方案安装后，可强制关闭 Hugging Face 网络访问来验证确实在使用本地文件：

```bash
HF_HUB_OFFLINE=1 .venv/bin/python 3_rag_from_scratch/part1_overview.py
```

预期关键结果：

- `embedding.mode` 为 `local FastEmbed / ONNX Runtime`；
- `embedding.installed` 为 `true`；
- `indexed_chunk_count` 为 `4`；
- 检索返回 `2` 个 `Document`；
- 回答标记为“离线抽取式回答”。

到这里，即使没有 API Key，Part 1 也已经能正常学习。

## 8. 配置在线模型

只有 `--live` 在线生成才需要 API Key。复制模板：

```bash
cp .env.example .env
code .env
```

保留模板中的默认地址和模型，只在本机填写自己的 Key：

```dotenv
ZHIPU_API_KEY=填写自己的Key
ZHIPU_BASE_URL=https://ai-hub.digiwincloud.com.cn/v1
ZHIPU_CHAT_MODEL=ep-qwen2.5-72b
ZHIPU_EMBEDDING_MODEL=embedding-3
```

`.env` 已被 Git 忽略，绝不能把真实 Key 写入 Python、Markdown、聊天记录或 Git 提交。可以这样确认忽略规则有效：

```bash
git check-ignore -v .env
git status --short
```

然后验证在线回答：

```bash
.venv/bin/python 3_rag_from_scratch/part1_overview.py --live
```

目录 3 会自动读取仓库根目录 `.env`，不需要手动 `source .env`。`--live` 仍使用本地 MiniLM 检索，只把最终回答交给 `ep-qwen2.5-72b`。不要添加 `--embedding glm`，否则才会请求当前 Key 没有权限的远程 `embedding-3`。

## 9. 配置 Codex 和插件

Codex 登录、插件和外部服务授权不会随 Git 仓库同步，需要在家里电脑单独配置。

1. 在 VS Code 中安装并登录 Codex 扩展。
2. 打开 `Settings > Plugins`；使用 CLI 时也可以在 Codex 会话中输入 `/plugins`。
3. 安装 `Superpowers` 和 `Hugging Face`。
4. 安装后新建一个 Codex 任务或 CLI 会话，再用 `@` 自动补全检查是否已加载。

Superpowers 主要提供 Skills，通常不需要外部账号。Hugging Face 插件包含外部 App，首次使用时可能要求登录；它和本地 MiniLM 的 Python 下载是两套独立功能，跑 RAG demo 不依赖该插件，也不要把 Hugging Face Token 写入项目 `.env`。

新建 Codex 会话后，使用 [学习交接](learning-handoff.md) 中的启动提示，从文档记录的当前阶段继续。

## 10. 常见问题

### `ensurepip is not available`

说明 Ubuntu 缺少 venv 包：

```bash
sudo apt install -y python3-venv python3.12-venv
python3 -m venv --clear .venv
```

`--clear` 只重建创建失败的 `.venv`，不要删除源码目录。

### Part 1 一直卡在第一次运行

先运行：

```bash
.venv/bin/python 3_rag_from_scratch/part1_overview.py --embedding hash
```

如果 hash 秒回，Python 环境没问题，卡点就是默认模型下载；改用第 6 节的 ModelScope 固定下载。

### `embedding-3` 返回 403

默认本地模式不需要 `embedding-3`。检查命令中不要出现：

```text
--embedding glm
```

### `--live` 返回 503、断连或超时

这是在线聊天接入点链路，不是本地 Embedding 故障。先重新运行不带 `--live` 的命令确认本地流程，再重试在线请求或检查平台接入点状态。

### VS Code 找不到依赖

确认窗口左下角是 `WSL: Ubuntu`，并选择：

```text
~/code/andrew/.venv/bin/python
```

### Codex 中没有新安装的插件

安装后必须新建任务或 CLI 会话。若仍没有，检查当前 VS Code 是否连接到正确的 WSL 环境，并从 `Settings > Plugins` 查看安装状态。

## 官方参考

- [Microsoft：安装 WSL](https://learn.microsoft.com/windows/wsl/install)
- [VS Code：Remote development in WSL](https://code.visualstudio.com/docs/remote/wsl-tutorial)
- [ModelScope：模型下载](https://modelscope.cn/docs/models/download)
- [ModelScope：本地模型仓库](https://www.modelscope.cn/models/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
- [GitHub CLI：快速开始](https://docs.github.com/github-cli/github-cli/quickstart)
- [OpenAI：Codex Plugins](https://learn.chatgpt.com/docs/plugins)
