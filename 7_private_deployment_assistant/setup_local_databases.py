"""准备本地数据库密码；不打印凭据，不覆盖已有配置。"""

from pathlib import Path
import secrets


# 启动命令：.venv/bin/python 7_private_deployment_assistant/setup_local_databases.py
# 参数枚举：无；仅生成当前目录 runtime/local.env，不启动或删除数据库。
def main() -> None:
    directory = Path(__file__).resolve().parent / "runtime"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "local.env"
    try:
        with path.open("x", encoding="utf-8") as stream:
            path.chmod(0o600)
            stream.write(f"PRIVATE_ASSISTANT_PG_PASSWORD={secrets.token_hex(24)}\n")
    except FileExistsError:
        print("已有本地环境文件，保留原密码。")
    else:
        print("本地数据库环境文件已生成，凭据未输出。")


if __name__ == "__main__":
    main()
