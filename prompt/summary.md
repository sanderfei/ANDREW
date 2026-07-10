# L1 到 L7 模型调用 Prompt 总结

这份总结对应 `prompt` 目录下的 `L1_guidelines.py` 到 `L7_chatbot.py`。
这些文件的核心不是训练模型，而是学习如何把任务、上下文、约束和输出格式写进 prompt，再通过统一的模型调用函数拿到结果。

## 1. 公共模型调用方式

`L1_guidelines.py` 是后面课程复用的模型调用入口。

单轮调用使用：

```python
response = get_completion(prompt)
```

它内部会把普通字符串 prompt 包装成 chat messages：

```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": prompt},
]
```

真正请求模型的是：

```python
response = requests.post(API_URL, headers=headers, json=payload, timeout=180)
```

payload 的主要字段是：

```python
{
    "model": MODEL,
    "messages": messages,
    "temperature": temperature,
    "max_tokens": max_tokens,
}
```

所以后面 L2 到 L6 大多只关心如何写 `prompt`，不重复关心 HTTP 请求细节。

L7 是多轮对话，所以直接使用：

```python
get_completion_from_messages(context)
```

它传入的是完整消息列表，而不是单个 prompt 字符串。

## 2. L1 Guidelines：清晰指令和结构化输出

L1 主要学习如何写清楚任务。

常见写法包括：

- 用分隔符包住输入文本，例如三个反引号。
- 明确说明任务，例如“总结成一句中文”。
- 指定输出格式，例如 JSON、步骤列表、固定字段。
- 把复杂任务拆成多个步骤。
- 要求模型先自己推理，再判断学生答案是否正确。

典型结构：

```text
你的任务是...
请按以下步骤操作：
1 - ...
2 - ...

请使用以下格式：
...

文本：
<三个反引号包裹的输入内容>
```

学习点是：prompt 不是只写一句问题，而是要把任务目标、输入边界、步骤和输出格式都交代清楚。

## 3. L2 Iterative：迭代优化 Prompt

L2 用产品规格生成商品描述，重点是不断发现输出问题，然后修改 prompt。

迭代过程大致是：

- 第一次只要求写产品描述，结果可能太长、太泛。
- 增加“最多 50 个词”，控制长度。
- 增加“面向家具零售商”，控制受众。
- 增加“重点介绍材料”，控制内容侧重点。
- 增加“包含产品 ID”，控制必要信息。
- 增加“输出 HTML 和尺寸表格”，控制输出格式。

学习点是：模型输出不符合预期时，通常不是模型不能做，而是 prompt 约束不够具体。

## 4. L3 Summarizing：摘要和提取

L3 使用产品评论做摘要。

主要模式有两类：

摘要：

```text
请总结下面的评论，最多 30 个词。
```

面向特定部门的摘要：

```text
请重点关注发货和配送相关内容。
```

提取：

```text
请提取与发货和配送相关的信息。
```

摘要会重新组织原文，提取更强调只拿出相关事实。

学习点是：同一段输入可以因为目标不同，得到完全不同的输出。prompt 里要明确“为谁总结”和“关注什么”。

## 5. L4 Inferring：推断、分类和主题识别

L4 让模型从文本中推断隐含信息。

包括：

- 判断情感倾向。
- 限制只输出“正面”或“负面”。
- 识别情绪列表。
- 判断是否表达愤怒。
- 提取商品和品牌，并输出 JSON。
- 从新闻中识别主题。
- 判断给定主题是否出现在文本中。

典型结构：

```text
请从评论文本中识别以下信息：
- 情感倾向
- 是否表达愤怒
- 商品
- 品牌

请将响应格式化为 JSON 对象。
```

学习点是：模型不仅能改写文本，也能做分类、打标签、字段抽取和主题判断。输出越要给程序继续处理，格式要求就越要严格。

## 6. L5 Transforming：转换、翻译和校对

L5 关注把输入转换成另一种形式。

包括：

- 翻译到一种或多种语言。
- 判断输入语言。
- 区分正式和非正式表达。
- 把口语改写成商务信函。
- 把 JSON/Python 字典转换成 HTML 表格。
- 校对拼写、语法、风格。
- 用 `unified_diff` 对比原文和修正版。

典型结构：

```text
请将下面的文本翻译成法语、西班牙语和英文海盗风格：
<三个反引号包裹的输入内容>
```

或：

```text
请校对并修正下面的英文文本。
如果没有发现错误，只需说“No errors found”。
```

学习点是：转换类任务要说清楚目标格式、目标语气、目标语言和是否保留原意。

## 7. L6 Expanding：扩写和个性化回复

L6 用客户评论和情感倾向生成客服邮件。

prompt 里给了角色：

```text
你是一名客服 AI 助手。
```

给了任务：

```text
给一位重要客户发送邮件回复。
```

给了条件分支：

```text
如果情感倾向是正面或中性，请感谢他们的评论。
如果情感倾向是负面，请表达歉意，并建议他们联系客服。
```

给了风格和署名：

```text
请使用简洁、专业的语气。
邮件署名为 `AI customer agent`。
```

还演示了 `temperature=0.7`：

```python
response = get_completion(prompt, temperature=0.7)
```

学习点是：扩写不是让模型随便发挥，而是用角色、条件、细节、语气和署名控制生成内容。`temperature` 越高，表达越有变化；越低，输出越稳定。

## 8. L7 Chatbot：多轮消息和上下文

L7 不再只传单个 prompt，而是维护一个 `context` 消息列表。

初始上下文是 system prompt：

```python
{
    "role": "system",
    "content": "你是 OrderBot..."
}
```

每次用户输入时追加：

```python
context.append({"role": "user", "content": user_input})
```

模型回复后追加：

```python
context.append({"role": "assistant", "content": response})
```

这样下一次请求会带上之前所有对话，模型就能记住顾客点过什么。

`summary` 命令会在当前上下文后追加一个新的 system 指令：

```text
请为前面的食品订单创建一个 JSON 摘要。
```

学习点是：聊天机器人不是每轮重新开始，而是靠 `messages` 保存上下文。不同角色的消息共同决定模型下一次如何回复。

## 9. L1 到 L7 的通用 Prompt 模式

可以把这些课程里的 prompt 写法总结成一个模板：

```text
角色：你是谁？
任务：你要做什么？
输入：需要处理的文本或数据是什么？
约束：长度、语言、风格、受众、是否只输出某些值。
步骤：复杂任务是否需要分步骤完成？
格式：输出 JSON、HTML、列表、表格，还是自然语言？
上下文：是否需要保留多轮消息？
```

对应到模型调用：

```text
单轮任务：
prompt -> get_completion(prompt)

多轮聊天：
messages/context -> get_completion_from_messages(messages)
```

最重要的结论是：

```text
模型调用本身很简单，真正影响结果的是 prompt 里给出的任务边界、上下文、约束和输出格式。
```
