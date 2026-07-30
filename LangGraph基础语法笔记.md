# LangGraph 基础语法笔记

这份笔记整理 `andrew` 项目中 [5_langgraph_agentic_rag](5_langgraph_agentic_rag) 逐步学习到的 LangGraph 语法和运行机制。

本文按实际学习进度持续补充，不提前展开尚未学习的章节。当前学习到：

```text
Part 1：State、Node、Edge、Conditional Edge、compile、invoke
```

当前项目使用 `langgraph 1.2.8`。Part 1 示例见
[part1_graph_basics.py](5_langgraph_agentic_rag/part1_graph_basics.py)。

## 1. 常用术语

| 英文 | 发音近似 | 在 LangGraph 中的含义 |
| --- | --- | --- |
| Agentic | 诶-坚-提克 | 具备自主判断和选择下一步能力的 |
| Graph | 格拉夫 | 由节点和边组成的执行图 |
| State | 斯得特 | 节点之间共享的数据 |
| Node | 诺德 | 读取 State、执行逻辑并返回状态更新 |
| Edge | 诶句 | 从一个节点连接到另一个节点 |
| Router | 路由器 | 读取 State 并选择下一条分支 |

Part 1 的流程是：

```text
START
  ↓
classify_question
  ↓
choose_route
  ├─ smalltalk → answer_smalltalk → END
  └─ knowledge → explain_knowledge_route → END
```

## 2. State：整张图共享的数据

```python
from typing import Literal, TypedDict


class LearningState(TypedDict, total=False):
    question: str
    route: Literal["knowledge", "smalltalk"]
    answer: str
    steps: list[str]
```

`LearningState` 描述整张图可以使用的状态字段。运行时的 State 仍然是普通
Python 字典：

```python
{
    "question": "你好",
    "route": "smalltalk",
    "answer": "你好，下一步可以把问题交给知识库检索。",
    "steps": ["classify_question", "answer_smalltalk"],
}
```

`total=False` 允许初始状态只提供部分字段：

```python
{"question": "你好", "steps": []}
```

后续节点再逐步生成 `route` 和 `answer`。

## 3. Node：返回部分状态更新

节点是接收 State 的 Python 函数：

```python
def classify_question(state: LearningState) -> LearningState:
    question = state["question"].strip().lower()
    smalltalk = question in {"你好", "您好", "hello", "hi"}
    return {
        "route": "smalltalk" if smalltalk else "knowledge",
        "steps": [*state.get("steps", []), "classify_question"],
    }
```

节点不需要复制并返回整个 State，只返回需要更新的字段即可。

```text
执行前 State
{
    "question": "你好",
    "steps": [],
}

节点返回
{
    "route": "smalltalk",
    "steps": ["classify_question"],
}

LangGraph 合并后
{
    "question": "你好",
    "route": "smalltalk",
    "steps": ["classify_question"],
}
```

本章还没有使用 Reducer。同名字段默认采用新的节点返回值，因此代码通过
`[*旧步骤, 新步骤]` 创建新列表并保留已有步骤。

## 4. `StateGraph`：创建图的定义

```python
from langgraph.graph import END, START, StateGraph

workflow = StateGraph(LearningState)
```

这行只是在创建图的设计稿，并指定图使用 `LearningState`。此时没有执行任何节点。

## 5. `add_node()`：注册节点

```python
workflow.add_node("classify_question", classify_question)
workflow.add_node("answer_smalltalk", answer_smalltalk)
workflow.add_node(
    "explain_knowledge_route",
    explain_knowledge_route,
)
```

两个参数的含义不同：

```python
workflow.add_node(
    "answer_smalltalk",  # LangGraph 中的节点名称：str
    answer_smalltalk,    # 真正执行的 Python 函数：callable
)
```

节点名称不必和函数名相同：

```python
workflow.add_node("smalltalk_node", answer_smalltalk)
```

如果注册成 `"smalltalk_node"`，后面的边也必须使用这个节点名称。

## 6. `add_edge()`：添加固定边

```python
workflow.add_edge(START, "classify_question")
```

含义是图从 `START` 出发后，固定进入 `classify_question`：

```text
START → classify_question
```

结束边：

```python
workflow.add_edge("answer_smalltalk", END)
workflow.add_edge("explain_knowledge_route", END)
```

表示这两个回答节点执行完成后结束整张图。

`START` 和 `END` 是 LangGraph 提供的特殊标记，不需要通过 `add_node()` 注册。

## 7. `add_conditional_edges()`：添加条件边

路由函数只读取 State 并返回分支标识：

```python
def choose_route(
    state: LearningState,
) -> Literal["knowledge", "smalltalk"]:
    return state["route"]
```

条件边：

```python
workflow.add_conditional_edges(
    "classify_question",
    choose_route,
    {
        "smalltalk": "answer_smalltalk",
        "knowledge": "explain_knowledge_route",
    },
)
```

三个参数依次表示：

```text
"classify_question"  条件判断发生在哪个节点之后
choose_route          使用哪个函数决定分支
dict                  路由返回值与目标节点名称的映射
```

一次完整查找过程：

```text
choose_route(state)
  ↓ 返回
"smalltalk"
  ↓ 查询映射字典
"answer_smalltalk"
  ↓ 查找已注册节点
answer_smalltalk(state)
```

映射字典中：

```python
{
    "smalltalk": "answer_smalltalk",
}
```

- 左侧 `"smalltalk"`：路由函数的返回值。
- 右侧 `"answer_smalltalk"`：通过 `add_node()` 注册的节点名称。
- 右侧不是直接调用的 Python 函数。

目标节点必须在 `compile()` 之前注册，否则编译时会出现 unknown target 错误。
目标节点可以在 `add_conditional_edges()` 之后、`compile()` 之前注册，但推荐先注册
所有节点，再添加边，代码更容易阅读。

## 8. 添加边的代码顺序不等于运行顺序

下面两种声明顺序构建出的连接关系相同：

```python
workflow.add_edge(START, "classify_question")
workflow.add_conditional_edges(
    "classify_question",
    choose_route,
    {
        "smalltalk": "answer_smalltalk",
        "knowledge": "explain_knowledge_route",
    },
)
```

```python
workflow.add_conditional_edges(
    "classify_question",
    choose_route,
    {
        "smalltalk": "answer_smalltalk",
        "knowledge": "explain_knowledge_route",
    },
)
workflow.add_edge(START, "classify_question")
```

运行顺序由图中的起点和终点决定，不由 `add_edge()` 的书写行号决定：

```text
START → classify_question → 条件判断 → 对应回答节点 → END
```

推荐按照以下顺序组织代码：

```text
1. 注册所有节点
2. 添加 START 入口边
3. 添加固定边或条件边
4. 添加 END 结束边
5. compile()
```

这个顺序是为了提高可读性，不是 LangGraph 的运行顺序规则。

## 9. `compile()`：把设计稿变成可执行图

```python
graph = workflow.compile()
```

可以把两个对象理解为：

```text
workflow: StateGraph          图的定义或设计稿
graph: CompiledStateGraph     编译后的可运行图
```

`add_node()`、`add_edge()` 和 `add_conditional_edges()` 都是在描述图，没有执行
业务节点。`compile()` 会检查图的连接关系，例如条件边是否指向未知节点。

## 10. `invoke()`：真正执行一次图

```python
result = graph.invoke({
    "question": "你好",
    "steps": [],
})
```

此时才会真正从 `START` 开始执行节点。

`invoke()` 的输入字段应该来自 `LearningState`，但不表示每次都要把所有字段传入。
当前 `LearningState` 使用了 `total=False`，所以可以只传本次执行需要的部分状态。

当前代码中各字段的输入要求是：

| 字段 | 是否需要在本次输入中显式提供 | 原因 |
| --- | --- | --- |
| `question` | 需要 | `classify_question` 使用 `state["question"]` 直接读取 |
| `steps` | 不需要 | 节点使用 `state.get("steps", [])`，缺少时自动从空列表开始 |
| `route` | 不需要 | 由 `classify_question` 节点生成 |
| `answer` | 不需要 | 由后续回答节点生成 |

因此下面的最小输入可以正常运行：

```python
result = graph.invoke({
    "question": "你好",
})
```

状态变化是：

```text
初始 State
{"question": "你好"}

classify_question 中
state.get("steps", []) → []

最终 State
{
    "question": "你好",
    "route": "smalltalk",
    "answer": "你好，下一步可以把问题交给知识库检索。",
    "steps": ["classify_question", "answer_smalltalk"],
}
```

如果连 `question` 也不传：

```python
graph.invoke({})
```

执行到下面这行时：

```python
question = state["question"].strip().lower()
```

会因为字典里不存在 `question` 而产生：

```text
KeyError: 'question'
```

所以需要区分：

```text
State Schema：定义整张图允许和预期使用哪些字段
初始 State：只提供本次执行开始时已经具备的字段
节点逻辑：决定某个字段在运行到该节点前是否必须存在
```

输入输出类型可以先理解为：

```text
初始 State: dict
  ↓ graph.invoke()
节点逐步返回部分更新
  ↓ LangGraph 合并状态
最终 State: dict
```

两个独立的 `invoke()`：

```python
first = graph.invoke({"question": "你好", "steps": []})
second = graph.invoke({
    "question": "本地默认 Embedding 模型是什么？",
    "steps": [],
})
```

当前图没有配置 Checkpointer，因此第二次调用不会继承第一次调用的 State。

## 11. 用普通 Python 理解 Part 1

Part 1 的图大致等价于：

```python
def ordinary_invoke(initial_state):
    state = dict(initial_state)

    update = classify_question(state)
    state.update(update)

    route = choose_route(state)
    if route == "smalltalk":
        update = answer_smalltalk(state)
    else:
        update = explain_knowledge_route(state)

    state.update(update)
    return state
```

LangGraph 的价值是把这里隐藏在 `if/else` 中的状态、节点和分支显式组织成图。
后续才能在此基础上继续加入 Tool、循环、重试、Checkpoint、人工审批和流式事件。

## 12. Part 1 当前边界

Part 1 专门学习图的基本结构，因此当前没有：

- LLM 或 Agent 决策。
- Embedding。
- Chroma 检索。
- Tool 调用。
- Checkpoint 和跨调用状态。

知识分支目前只返回说明文字。Part 2 才会在该位置接入真实的 Chroma
Retriever Tool。
