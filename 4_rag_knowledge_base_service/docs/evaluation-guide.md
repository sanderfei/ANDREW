# 评测指南

`evaluate.py` 默认在临时目录复制 `data/source`，因此不会污染你的本地 Chroma 数据。它先完整索引，再跑 18 条黄金样本，最后修改和删除一份文档验证增量更新。

## 当前指标

| 检查 | 失败意味着什么 |
| --- | --- |
| `answerable` | 拒答阈值不合适，或无答案问题被错误放行 |
| expected source | 检索没有把正确资料排进 citation |
| citation 为空 | 已知答案没有可复查来源 |
| 关键术语 | 离线摘录没有包含支撑答案的原文 |
| 更新回归 | manifest / chunk ID / Chroma 删除逻辑有残留 |

报告保存为 JSON：

```bash
.venv/bin/python evaluate.py --output /tmp/rag-evaluation.json
```

定位顺序应是：先看 `retrieval.matches` 是否召回正确 chunk；再看 `accepted` 与阈值；最后才看 live 模型的生成文本。这样可以区分检索失败、错误引用、拒答错误和生成不忠实。

后续第 10 周可以在这套本地回归稳定后，开启 `LANGSMITH_TRACING=true`，把同一黄金集做 trace 与实验对比。CI 仍保持离线，不放入任何 API key。
