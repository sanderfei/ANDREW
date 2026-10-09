# 本地 Langfuse：WSL Ubuntu + Docker Compose

适用：Ubuntu 24.04 / WSL2，单人学习。已验证 Langfuse 4.54.0、Docker 29.8.2、Compose 5.6.0；本机 15 GiB 内存、16 个逻辑 CPU，六个容器实测约占 2.8 GiB 内存。

## 1. 安装 Docker Engine 和 Compose

安装下载工具并添加 Docker 官方软件源：

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<'EOF'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

安装引擎、客户端、容器运行时和 Compose；启动 Docker：

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl start docker
sudo docker version
sudo docker compose version
```

已有 Docker 则跳过安装。Compose 需至少 2.24.4；本方案无需 Docker Desktop。

## 2. 生成部署配置和课件 Key

下载固定版本的官方 Compose 配置，生成本机凭据和初始化账号，自动更新课件 `.env` 的三项 Langfuse 配置：

```bash
cd ~/code/andrew
.venv/bin/python 6_langfuse_observability/setup_local_langfuse.py
```

脚本保留其他模型配置；再次运行复用部署凭据。六个服务：Web、Worker、PostgreSQL、ClickHouse、Redis、MinIO。仅绑定本机 3000、9090 端口，学习容器不会随 Docker 重启自动启动。

## 3. 启动 Langfuse

校验配置、下载镜像并启动，等待 Web 健康后启动 Worker，避免首次数据库迁移冲突：

```bash
cd ~/code/langfuse-learning
sudo docker compose -p langfuse-learning config --quiet
sudo docker compose -p langfuse-learning up -d --wait --wait-timeout 180
sudo docker compose -p langfuse-learning ps
```

访问 **http://localhost:3000**；账号 **learning@example.local**。密码在部署 `.env` 的 `LANGFUSE_INIT_USER_PASSWORD` 中，使用编辑器查看：

```bash
code ~/code/langfuse-learning/.env
```

项目 `andrew-tutorial` 和 API Keys 自动创建，课件可以直接使用。

## 4. 验证课件上报

清除可能覆盖 `.env` 的旧 Shell 配置，运行 Part 1：

```bash
cd ~/code/andrew
unset LANGFUSE_BASE_URL LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY
.venv/bin/python 6_langfuse_observability/part1_trace_basics.py --mode langfuse
```

在网页项目中查询输出的 `trace_id`，应看到 `part1-text-workflow`、`normalize`、`format-report`。仅输出 ID 不算入库验证。

验证错误 Span（退出码 1 为预期结果）：

```bash
.venv/bin/python 6_langfuse_observability/part1_trace_basics.py --mode langfuse --text ""
```

## 5. 停止和再次启动

停止服务，保留数据：

```bash
cd ~/code/langfuse-learning
sudo docker compose -p langfuse-learning stop
```

再次启动：

```bash
sudo docker compose -p langfuse-learning up -d --wait --wait-timeout 180
```

## 6. 排错命令

查看退出状态、日志和内存用量：

```bash
cd ~/code/langfuse-learning
sudo docker compose -p langfuse-learning ps -a
sudo docker compose -p langfuse-learning logs --tail=80 langfuse-web langfuse-worker clickhouse
sudo docker stats --no-stream
```

- OOM：先释放其他任务占用的内存，再启动；不要删除数据卷。
- 下载中断：重新执行 `up -d`，已下载的镜像层会复用。
- 端口冲突：检查 `ss -ltn`；修改覆盖文件端口，并同步部署 `NEXTAUTH_URL` 和课件 `LANGFUSE_BASE_URL`。
- 不要在保留数据卷时重新生成部署密码、SALT 或 ENCRYPTION_KEY。

参考：[Docker 安装](https://docs.docker.com/engine/install/ubuntu/)、[Langfuse Compose](https://langfuse.com/self-hosting/deployment/docker-compose)、[自动初始化](https://langfuse.com/self-hosting/administration/headless-initialization)。
