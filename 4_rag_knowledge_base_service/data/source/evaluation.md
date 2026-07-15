# RAG 评估与可观测性

黄金问题集（`golden_cases`）至少覆盖：已命中问题、无答案问题、相近或歧义问法、错误引用防护，以及文档更新后的回归。不要只看回答是否流畅。

离线回归首先检查 retrieval hit rate、citation validity、refusal correctness 和 faithfulness。它无需真实模型或 API key，因此应进入 CI；每次修改切块、embedding 或拒答阈值后都要重跑。

LangSmith tracing 是可选的线上可观测性能力。先用本地评测发现回归，再在提供环境变量时接入 trace 与实验对比；CI 和默认离线模式都不读取 LangSmith 密钥。
