"""本地向量数据库状态、文档录入和片段检索。"""

import argparse
import json

from services.vector_service import VectorService


# 启动命令：.venv/bin/python 7_private_deployment_assistant/vector_cli.py status
# 参数枚举：--backend qdrant/pgvector（不填则读取 config.toml）；
# status 查看状态；ingest "本地文件路径" 录入单个文档；search "问题" 检索；
# search 可用 --top-k 1～20、--k8s 1.23.10/1.32.8、--os Ubuntu/CentOS、--mode online/offline。
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("qdrant", "pgvector"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    ingest = commands.add_parser("ingest")
    ingest.add_argument("file_path", help="服务器本地路径，需位于 config.toml 的允许目录中。")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--k8s", choices=("1.23.10", "1.32.8"))
    search.add_argument("--os", choices=("Ubuntu", "CentOS"))
    search.add_argument("--mode", choices=("online", "offline"))
    args = parser.parse_args()
    service = None
    try:
        service = VectorService(args.backend)
        if args.command == "status":
            result = service.status()
        elif args.command == "ingest":
            result = service.ingest(args.file_path)
        else:
            result = service.search(args.query, args.top_k, {
                "kubernetes_versions": args.k8s, "operating_systems": args.os, "install_modes": args.mode,
            })
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("connected", True) else 1
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    except Exception:
        print(json.dumps({"error": "数据库或本地向量模型操作失败，请检查服务和配置。"}, ensure_ascii=False))
        return 1
    finally:
        if service is not None:
            service.close()


if __name__ == "__main__":
    raise SystemExit(main())
