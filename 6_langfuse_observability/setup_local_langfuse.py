"""准备本地 Langfuse 配置，自动生成账号和项目 Key，并配置课件 .env。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import tempfile
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_URL = (
    "https://raw.githubusercontent.com/langfuse/langfuse/"
    "3d680c019ddaec28770db53082b58c1ec3dbeff5/docker-compose.yml"
)
OVERRIDE = """services:
  langfuse-web:
    restart: "no"
    ports: !override
      - "127.0.0.1:3000:3000"
    healthcheck:
      test: ["CMD", "node", "-e", "require('http').get('http://langfuse-web:3000/api/public/health',r=>{r.resume();process.exit(r.statusCode===200?0:1)}).on('error',e=>{console.error(e.message);process.exit(1)})"]
      interval: 5s
      timeout: 10s
      start_period: 60s
      retries: 24
  langfuse-worker:
    restart: "no"
    ports: !reset []
    depends_on:
      langfuse-web:
        condition: service_healthy
  clickhouse:
    restart: "no"
    ports: !reset []
  postgres:
    restart: "no"
    ports: !reset []
  redis:
    restart: "no"
    ports: !reset []
  minio:
    restart: "no"
    ports: !override
      - "127.0.0.1:9090:9000"
"""


def write_private(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_settings(path: Path) -> dict[str, str]:
    settings = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.removeprefix("export ").split("=", 1)
            settings[name.strip()] = value.strip().strip("\"'")
    return settings


def prepare(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    service_env = directory / ".env"
    if service_env.exists():
        settings = read_settings(service_env)
        required = ("NEXTAUTH_URL", "LANGFUSE_INIT_PROJECT_PUBLIC_KEY", "LANGFUSE_INIT_PROJECT_SECRET_KEY")
        if any(not settings.get(name) for name in required):
            raise ValueError("已有部署 .env 缺少初始化配置，请保留原凭据并手工补齐。")
    else:
        postgres_password = secrets.token_hex(16)
        minio_password = secrets.token_hex(16)
        settings = {
            "NEXTAUTH_URL": "http://localhost:3000",
            "NEXTAUTH_SECRET": secrets.token_hex(32),
            "SALT": secrets.token_hex(32),
            "ENCRYPTION_KEY": secrets.token_hex(32),
            "POSTGRES_PASSWORD": postgres_password,
            "DATABASE_URL": f"postgresql://postgres:{postgres_password}@postgres:5432/postgres",
            "CLICKHOUSE_PASSWORD": secrets.token_hex(16),
            "REDIS_AUTH": secrets.token_hex(16),
            "MINIO_ROOT_PASSWORD": minio_password,
            "LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY": minio_password,
            "LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY": minio_password,
            "LANGFUSE_S3_BATCH_EXPORT_SECRET_ACCESS_KEY": minio_password,
            "TELEMETRY_ENABLED": "false",
            "LANGFUSE_INIT_ORG_ID": "andrew-learning",
            "LANGFUSE_INIT_ORG_NAME": "Andrew Learning",
            "LANGFUSE_INIT_PROJECT_ID": "andrew-tutorial",
            "LANGFUSE_INIT_PROJECT_NAME": "andrew-tutorial",
            "LANGFUSE_INIT_PROJECT_PUBLIC_KEY": "pk-lf-" + secrets.token_hex(16),
            "LANGFUSE_INIT_PROJECT_SECRET_KEY": "sk-lf-" + secrets.token_hex(32),
            "LANGFUSE_INIT_USER_EMAIL": "learning@example.local",
            "LANGFUSE_INIT_USER_NAME": "Learning",
            "LANGFUSE_INIT_USER_PASSWORD": secrets.token_hex(16),
        }
        write_private(service_env, "\n".join(f"{key}={value}" for key, value in settings.items()) + "\n")

    compose = directory / "compose.yaml"
    if not compose.exists():
        with urlopen(COMPOSE_URL, timeout=30) as response:
            compose.write_bytes(response.read())
    override = directory / "compose.override.yaml"
    if not override.exists():
        override.write_text(OVERRIDE, encoding="utf-8")

    tutorial_settings = {
        "LANGFUSE_BASE_URL": settings["NEXTAUTH_URL"],
        "LANGFUSE_PUBLIC_KEY": settings["LANGFUSE_INIT_PROJECT_PUBLIC_KEY"],
        "LANGFUSE_SECRET_KEY": settings["LANGFUSE_INIT_PROJECT_SECRET_KEY"],
    }
    tutorial_env = PROJECT_ROOT / ".env"
    original = tutorial_env.read_text(encoding="utf-8") if tutorial_env.exists() else ""
    remaining = tutorial_settings.copy()
    lines = []
    for line in original.splitlines():
        name = line.strip().removeprefix("export ").split("=", 1)[0].strip()
        if name in tutorial_settings:
            lines.append(f"{name}={tutorial_settings[name]}")
            remaining.pop(name, None)
        else:
            lines.append(line)
    lines.extend(f"{name}={value}" for name, value in remaining.items())
    write_private(tutorial_env, "\n".join(lines) + "\n")
    print(f"部署配置：{directory}")
    print("课件 .env 已配置，其他模型配置保留；凭据未输出。")


# 启动命令：.venv/bin/python 6_langfuse_observability/setup_local_langfuse.py
# 参数枚举：--directory 部署目录（默认 ~/code/langfuse-learning）。
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path.home() / "code/langfuse-learning")
    args = parser.parse_args()
    prepare(args.directory.expanduser().resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
