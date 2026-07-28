# 评测指南

`evaluate.py` 默认在临时目录复制 `data/source`，因此不会污染你的本地 Chroma 数据。它先完整索引，再跑 20 条黄金样本，最后修改和删除一份文档验证增量更新。

默认组合是 `--embedding local --mode live`：索引和问题向量使用本机 MiniLM，通过 answerability gate 的问题再调用在线聊天模型回答，因此需要根目录 `.env` 中已有可用的 `ZHIPU_API_KEY`。无答案问题仍应在 gate 处返回拒答，不调用聊天模型。

CI 使用 `--embedding hash --mode offline`，保证无需下载模型、无需 API Key，也不发起外部聊天请求。local 与 hash 两种报告不能直接比较绝对 vector score；live 生成也可能出现措辞波动。

## 当前指标

| 检查 | 失败意味着什么 |
| --- | --- |
| `answerable` | 拒答阈值不合适，或无答案问题被错误放行 |
| expected source | 检索没有把正确资料排进 citation |
| citation 为空 | 已知答案没有可复查来源 |
| 关键术语 | offline 要求答案逐字包含；live 要求 citation 证据包含，生成答案未逐字复述时记录 warning |
| 更新回归 | manifest / chunk ID / Chroma 删除逻辑有残留 |

报告保存为 JSON：

```bash
.venv/bin/python 4_rag_knowledge_base_service/evaluate.py \
  --embedding local \
  --mode live \
  --output /tmp/rag-evaluation.json

# CI 的确定性离线回归
.venv/bin/python 4_rag_knowledge_base_service/evaluate.py \
  --embedding hash \
  --mode offline
```

定位顺序应是：先看 `retrieval.matches` 是否召回正确 chunk；再看 `accepted` 与阈值；最后才看 live 模型的生成文本。这样可以区分检索失败、错误引用、拒答错误和生成不忠实。

后续第 10 周可以在这套本地回归稳定后，开启 `LANGSMITH_TRACING=true`，把同一黄金集做 trace 与实验对比。CI 仍使用 `hash + offline`，不放入任何 API key。
