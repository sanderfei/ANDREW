# 3 分钟演示脚本

1. 启动服务并访问 `GET /health`，说明初始索引是否准备好。
2. 调用 `POST /v1/reindex`，展示扫描、写入与 manifest 增量统计。
3. 在 `/health` 中指出 `embedding_mode=local` 和本地 MiniLM 模型，再调用 `POST /v1/ask` 问“citation 必须包含哪些定位字段？”，展示 `answer`、`citations` 和 `retrieval.matches`。
4. 问一个实时天气问题，展示 `answerable=false` 和空 citation，说明拒答不是故障。
5. 修改 `data/source/service_operations.md`，再次 reindex，展示 `updated_files` 与新的 chunk IDs。
6. 最后分别说明本机 MiniLM 在线回答评测与 CI Hash 离线回归的边界，并运行 `evaluate.py --embedding local --mode live` 展示黄金集结果和更新回归。

演示时要明确：离线模式输出的是检索摘录，用来检查数据流；live 模式才是 LLM 生成，但两种模式都把 citation 由服务端控制。
