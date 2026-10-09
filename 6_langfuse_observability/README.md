# 目录 6：Langfuse 可观测性与评测

接在目录 5 Part 14 之后学习，用可免费自部署的 Langfuse 承接原路线中的 LangSmith
追踪与实验专题。目录 1～5 保持独立运行，本目录 Part 2 复用已有 Part 13 的构图函数。

## Langfuse 是什么

Langfuse 是用于观察和改进 AI 应用的平台。接入后，可以按一次请求查看各步骤的输入输出、
模型调用、检索与工具调用、耗时和费用；实际记录的细节取决于应用提供的数据。
常见用途包括：

- **追踪与排错**：用 Trace 和嵌套 Span 还原请求执行过程，定位失败或耗时步骤。
- **质量评测**：给结果打 Score，用 Dataset 保存样本，通过 Experiment 比较提示词、模型或代码策略。
- **提示词管理**：集中保存和管理提示词版本，关联追踪与评测结果。

参见 [Langfuse 官方概览](https://langfuse.com/docs)、
[追踪文档](https://langfuse.com/docs/observability/overview)和
[评测文档](https://langfuse.com/docs/evaluation/overview)。

## 与 LangGraph 的分工

| | LangGraph | Langfuse |
| --- | --- | --- |
| 主要职责 | 执行流程：安排步骤、分支、暂停和恢复 | 观察与评测：记录执行过程、分析质量和性能 |
| 典型对象 | 节点、边、State、`thread_id`、checkpoint | Trace、Span、Score、Dataset、Experiment |
| 保存数据的用途 | checkpoint 供工作流继续执行 | Trace 供排错、统计和评测，不充当 LangGraph 的恢复检查点 |

例如一次 RAG 请求中，LangGraph 可以安排“检索资料 → 生成回答 → 等待人工审批”；
Langfuse 可以记录各步骤的输入输出与耗时，再对回答评分。两者可以一起使用：
本目录 Part 2 通过 `CallbackHandler` 观察 LangGraph 执行。Langfuse 的 Session 聚合追踪，
LangGraph 的 `thread_id` 标识检查点线程，两者用途不同。
参见 [LangGraph 官方概览](https://docs.langchain.com/oss/python/langgraph/overview)和
[Langfuse 集成文档](https://langfuse.com/integrations/frameworks/langchain)。

## 课程与知识点

| 课件 | 知识点 | 平台中观察什么 |
| --- | --- | --- |
| [Part 1](part1_trace_basics.py) | Trace、嵌套 Span、input/output、异常、flush | 一条 Trace 内的父子 Span、输入输出和错误 |
| [Part 2](part2_langgraph_tracing.py) | LangChain CallbackHandler、LangGraph、Session、流式消息 | 图节点和模拟模型调用；同一 Session 下的多条 Trace |
| [Part 3](part3_datasets_scores.py) | Dataset、参考答案、规则评测、Trace Score | 四条数据集样本、每条 Trace 的三项评分 |
| [Part 4](part4_experiment_comparison.py) | Dataset Run、同数据集实验对比、回归 | `always_answer` 与 `evidence_only` 两个实验 |

本目录使用 Python 普通函数、`FakeListChatModel` 和合成证据，无真实模型请求。
四条评测数据只用于理解评测接口，不代表真实 RAG 准确率，也不衡量完整语义忠实度。
人工评测、真实模型和 LLM-as-a-judge 放在后续质量专题；平台免费不包含外部模型调用费用。

## 安装和离线运行

在仓库根目录执行：

```bash
.venv/bin/python -m pip install -r 6_langfuse_observability/requirements.txt

.venv/bin/python 6_langfuse_observability/part1_trace_basics.py
.venv/bin/python 6_langfuse_observability/part2_langgraph_tracing.py
.venv/bin/python 6_langfuse_observability/part3_datasets_scores.py
.venv/bin/python 6_langfuse_observability/part4_experiment_comparison.py
```

默认 `--mode offline` 不创建 Langfuse 客户端，不连接平台，不需要任何 Key。
输出的 `trace_id` / `dataset_run_url` 为 `null`，表示没有平台记录。
教程进程会关闭旧课件可能配置的 LangSmith 自动追踪，不修改根 `.env`。

依赖按 Langfuse Python SDK `4.15.4` 验证，不使用旧版 `langfuse.callback` 导入路径。
OpenTelemetry 使用与本仓库已有 gRPC exporter 一致的 `1.43.0` 系列。

## 本地 Langfuse 平台

按 [Docker Compose 本地启动操作文档](docker-compose-local.md) 安装 Docker，再从仓库根目录生成配置并启动：

```bash
.venv/bin/python 6_langfuse_observability/setup_local_langfuse.py
cd ~/code/langfuse-learning
sudo docker compose -p langfuse-learning up -d --wait --wait-timeout 180
```

平台配置放在仓库外的 `~/code/langfuse-learning`。账号、组织、项目和 API Keys 自动初始化，
课件根目录 `.env` 的三项 Langfuse 配置自动更新，原有模型配置保留。
网页地址 `http://localhost:3000`，登录方式见操作文档。

若使用已有平台而不运行初始化脚本，手动修改 **andrew 仓库根目录已有的 `.env`**：

```dotenv
LANGFUSE_BASE_URL=http://localhost:3000
LANGFUSE_PUBLIC_KEY=你的本地项目PublicKey
LANGFUSE_SECRET_KEY=你的本地项目SecretKey
```

模板也位于根目录 [.env.example](../.env.example)。若应用运行在容器里，`localhost`
指的是该应用容器，应改成应用能访问的平台地址。云端也可用同一套接口，但本课默认指向本地。

## 接入平台

回到 andrew 仓库根目录：

```bash
.venv/bin/python 6_langfuse_observability/part1_trace_basics.py --mode langfuse
.venv/bin/python 6_langfuse_observability/part2_langgraph_tracing.py --mode langfuse --session-id learning-session
.venv/bin/python 6_langfuse_observability/part3_datasets_scores.py --mode langfuse
.venv/bin/python 6_langfuse_observability/part4_experiment_comparison.py --mode langfuse
```

`--mode langfuse` 会发送本课的合成输入、输出、Trace 和 Score。启动时先校验连接与项目 Key，
脚本退出前 `flush()` / `shutdown()` 等待 SDK 后台发送并释放资源。输出 Trace ID 只是关联标识，
完整上报结果以平台中可见的记录为准，不能仅凭函数返回就断言服务端已经保存。

## 重要边界与预期结果

- Part 1 使用 `--text ""` 会产生演示异常并以非零状态退出；平台模式可观察错误 Span。
- Part 2 的 CallbackHandler 观察图执行，不修改 State。`writer()` 的 custom 事件仍由
  `astream()` 消费，不能把它理解成写入 Langfuse 的同一个通道。
- Langfuse Session 用于聚合追踪，Graph `thread_id` 用于 checkpoint。示例使用相同字符串
  便于关联，但新建进程中的 `InMemorySaver` 不会恢复上一次进程的业务 State。
- 模拟模型会产生消息片段，但没有真实模型账单；不要根据片段数伪造 token 数和费用。
- Part 3/4 的平台模式会创建/更新专用数据集 `andrew-langfuse-contracts-v1`。
  固定 item ID 避免重复上传产生重复样本；不要把手工维护的业务数据集名传给本课。
- Part 3 的 Score 关联 Trace；Part 4 通过 `dataset.run_experiment()` 自动关联 Dataset Run、
  item、Trace 和评测结果。同名数据集下每次实验都有独立 run name。
- SDK 保留 `dataset_run_url` 等兼容字段；平台 v4 使用 Experiment 视图。URL 可能为空，
  可用输出的 `experiment_id` / `run_name` 查找实验，不把“没有旧版 URL”当成评分失败。
- `citation_validity` 只验证引用 ID 属于本次提供的证据，不保证答案的每句话都被证据支持。
  `reference_match` 是术语/固定拒答规则，不能当作完整语义质量评分。

```bash
# 观察坏基线，也可追加 --mode langfuse
.venv/bin/python 6_langfuse_observability/part3_datasets_scores.py --policy always_answer
```

固定四条数据上，`always_answer` 三项平均分均为 `0.5`，`evidence_only` 均为 `1.0`。
这是代码刻意构造的对照结果；以后换真实应用时应扩充样本、保留验证集，并人工校准评分。

## 与已有课件的关系

目录 4/5 的合同评测继续保留，Langfuse 负责新的追踪与实验管理。
`2_langchain/L8_Deep_Agent_From_Scratch.py` 中可选的 LangSmith Sandbox 是远程代码执行环境，
与追踪平台用途不同，本次没有把它错误替换成 Langfuse。LangChain 本身的 `langsmith` 依赖
也不意味着必须启用付费平台。

后续课程顺序：真实模型质量评测 → 混合检索/模型重排 → 上下文与工具工程 → 持久化服务及交付。

## 官方参考

- [LangChain / LangGraph 集成](https://langfuse.com/integrations/frameworks/langchain)
- [数据集](https://langfuse.com/docs/evaluation/experiments/datasets)
- [SDK 实验与评测器](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk)
- [免费自部署范围](https://langfuse.com/pricing-self-host)
