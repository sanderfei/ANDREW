# Python 基础语法笔记

这份笔记汇总在 `andrew` 项目当前会话和其他历史会话中问过的 Python 基础语法问题。重复问题已经合并，示例优先使用项目里的真实代码。

涉及 LangChain 专有 API 的内容放在根目录的 `LangChain基础语法笔记.md`；本文件重点解释这些代码背后的 Python 语法、类型和执行规则。

## 阅读导航

| 想复习的问题 | 对应章节 |
| --- | --- |
| `Iterable`、`Sequence`、`tuple`、`object`、`Literal` | 第 1、3 节 |
| `zip()`、`enumerate()`、变量拆包 | 第 2、8 节 |
| 列表、字典、元组、集合、嵌套列表、索引、切片 | 第 4、5 节 |
| `dict.get()`、`setdefault()`、`pop()`、`items()`、`sorted()` | 第 4 节 |
| 列表推导式、生成器表达式、`extend()`、双层 `flatten` | 第 6 节 |
| 默认参数、`*`、`*args`、`**kwargs`、`**config` | 第 7 节 |
| `argparse`、`action="store_true"`、`choices`、`default` | 第 7 节 |
| 三元条件表达式、`isinstance`、`hasattr`、`getattr` | 第 9 节 |
| `__init__`、`self`、`_embed`、`@dataclass`、`@classmethod`、`default_factory` | 第 10 节 |
| `import`、包层级、`deps["Document"]` | 第 11 节 |
| `Path`、`__file__`、路径 `/` 拼接 | 第 12 节 |
| `splitlines()`、`casefold()`、`re.sub()` | 第 5 节 |
| `async`、`await`、`gather`、`yield`、`async for`、同步/异步方法边界 | 第 13 节 |
| `with`、`@contextmanager`、回调注册、属性赋值 | 第 14 节 |
| 终端与 Python REPL 为什么不能混用 | 第 15 节 |
| Python 字典与 JSON 的区别 | 第 16 节 |

## 1. `Iterable[Document]` 是什么

项目代码位置：`3_rag_from_scratch/_common.py`。

```python
def split_documents(
    documents: Iterable[Document],
    *,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
) -> list[Document]:
    return splitter.split_documents(list(documents))
```

### 1.1 怎么读

```python
documents: Iterable[Document]
```

读作：

> 参数 `documents` 接受一个可迭代对象，遍历它时，每次应该得到一个 `Document` 对象。

这里各部分的含义是：

| 代码 | 含义 |
| --- | --- |
| `documents` | 参数名 |
| `:` | 后面是类型标注 |
| `Iterable` | 可迭代对象类型 |
| `[Document]` | 迭代时产生的元素应该是 `Document` |

`Iterable` 不是 Python 关键字，也不是元组，更不是某一种固定的数据结构。它是一个用于类型标注的可迭代类型，表示“这个对象能够被遍历”。本项目从 `typing` 导入：

```python
from typing import Iterable
```

在其他代码中也经常会看到 `from collections.abc import Iterable`。

### 1.2 哪些对象属于 `Iterable[Document]`

只要对象能够被 `for` 遍历，并且其中的元素是 `Document`，就可以传给这个参数，例如：

```python
# 列表
documents = [doc1, doc2]

# 元组
documents = (doc1, doc2)

# 生成器
documents = (doc for doc in source_documents)
```

它们都可以这样遍历：

```python
for document in documents:
    print(document)
```

关系可以简单理解为：

```text
Iterable[Document]（能逐个遍历出 Document）
├── list[Document]
├── tuple[Document, ...]
├── generator
└── 其他实现了可迭代协议的对象
```

### 1.3 `Iterable`、`Sequence` 和 `tuple` 的区别

| 类型 | 保证能遍历 | 保证有顺序 | 保证支持索引 | 是否是具体容器 |
| --- | --- | --- | --- | --- |
| `Iterable[Document]` | 是 | 否 | 否 | 否，是一种能力约束 |
| `Sequence[Document]` | 是 | 是 | 是 | 否，是一种更严格的能力约束 |
| `tuple[Document, ...]` | 是 | 是 | 是 | 是，明确要求元组 |

常见关系：

```text
list、tuple     同时属于 Sequence 和 Iterable
generator       通常只保证 Iterable，不保证索引和长度
set             属于 Iterable，但不是 Sequence，因为不按位置索引
```

因此，参数标注为 `Iterable[Document]` 时，函数内部不能直接假定下面的操作一定可用：

```python
documents[0]  # 不一定支持索引
len(documents)  # 不一定支持获取长度
```

项目中先执行了：

```python
list(documents)
```

这一步会把列表、元组或生成器等可迭代对象统一转换成列表，再交给文本切分器处理。

### 1.4 返回值 `-> list[Document]`

函数定义中的：

```python
) -> list[Document]:
```

表示该函数的返回值是一个列表，列表中的每一项都是 `Document`。

类型标注主要用于帮助阅读代码、编辑器提示和静态类型检查。Python 通常不会仅仅因为写了类型标注，就在运行时自动检查传入对象的类型。

## 2. `zip()` 是什么

项目代码位置：`3_rag_from_scratch/part5_multi_query.py`。

```python
"per_query_retrieval": [
    {
        "query": query,
        "documents": compact_documents(retrieved),
    }
    for query, retrieved in zip(queries, per_query_documents)
],
```

### 2.1 `zip()` 的作用

`zip()` 会同时遍历多个可迭代对象，把相同位置的元素配对在一起。

假设数据是：

```python
queries = ["问题1", "问题2"]

per_query_documents = [
    [doc1, doc2],
    [doc3],
]
```

执行：

```python
zip(queries, per_query_documents)
```

遍历时会依次产生两个二元组：

```python
("问题1", [doc1, doc2])
("问题2", [doc3])
```

注意，`zip()` 返回的是一个可迭代的 `zip` 对象。为了直接查看全部内容，可以先转成列表：

```python
pairs = list(zip(queries, per_query_documents))
```

结果为：

```python
[
    ("问题1", [doc1, doc2]),
    ("问题2", [doc3]),
]
```

### 2.2 `for query, retrieved` 是元组拆包

下面这段代码：

```python
for query, retrieved in zip(queries, per_query_documents)
```

每次先从 `zip()` 得到一个二元组，然后自动拆给两个变量。

第一次循环相当于：

```python
query, retrieved = ("问题1", [doc1, doc2])

# 拆包之后：
query = "问题1"
retrieved = [doc1, doc2]
```

这里的 `retrieved` 不是一个 `Document`，而是当前查询检索到的一组 `Document`。

### 2.3 完整列表推导式怎么执行

原代码是一个列表推导式：

```python
result = [
    {
        "query": query,
        "documents": compact_documents(retrieved),
    }
    for query, retrieved in zip(queries, per_query_documents)
]
```

它等价于普通的 `for` 循环：

```python
result = []

for query, retrieved in zip(queries, per_query_documents):
    item = {
        "query": query,
        "documents": compact_documents(retrieved),
    }
    result.append(item)
```

最终得到的是一个 Python 字典列表：

```python
[
    {
        "query": "问题1",
        "documents": [...],
    },
    {
        "query": "问题2",
        "documents": [...],
    },
]
```

所以这段代码的目的确实是：

1. 将每个查询和它对应的检索结果一一配对。
2. 把每一对数据整理成一个字典。
3. 把所有字典收集到列表中，方便作为接口结果的一部分返回。

不过，此时得到的仍然是 Python 的 `dict` 和 `list`，还不是 JSON 字符串。后续经过 Web 框架的响应序列化，或者调用 `json.dumps()`，才会变成 JSON。

### 2.4 两边长度不同时会怎样

普通 `zip()` 不要求两边长度相同，它会在较短的一边结束时停止：

```python
queries = ["问题1", "问题2"]
per_query_documents = [[doc1]]

result = list(zip(queries, per_query_documents))
print(result)
```

结果只有一组：

```python
[("问题1", [doc1])]
```

`"问题2"` 会被静默忽略。

如果业务逻辑要求两个列表必须严格一一对应，可以写成：

```python
zip(queries, per_query_documents, strict=True)
```

长度不一致时，Python 会抛出 `ValueError`，这样更容易发现数据对应关系出了问题。

## 3. 类型标注：`list`、`dict`、`tuple`、`object`、`None`、`Literal`

### 3.1 `变量: 类型 = 值` 要分成三部分看

项目代码：

```python
experiments: list[dict[str, object]] = []
```

拆开后是：

```text
experiments                 变量名
: list[dict[str, object]]   类型标注
= []                        真正执行的赋值
```

它不是“初始化空对象”，而是初始化一个空列表。类型标注说明这个列表以后计划存放字典：

```python
experiments.append(
    {
        "chunk_size": 80,
        "score": 0.71,
    }
)
```

其中：

```python
dict[str, object]
```

表示：

- 字典的 key 是字符串。
- 字典的 value 可以是各种类型的 Python 对象。

`object` 是 Python 几乎所有类型的共同基类。这里使用它，是因为同一个字典中可能同时放 `int`、`float`、`str`、`list` 等不同类型。

### 3.2 `Any` 和 `object` 都能接收任意值，但约束不同

```python
from typing import Any

anything: Any = "hello"
unknown: object = "hello"
```

这两个变量在运行时都只是保存原来的字符串对象，区别主要发生在编辑器和静态类型检查器中：

| 类型 | 能否接收任意类型的值 | 读取后能做什么 |
| --- | --- | --- |
| `object` | 可以 | 只能直接使用所有对象共有的基本能力；使用字符串等专属方法前要先缩小类型 |
| `Any` | 可以 | 类型检查器基本放弃检查，允许访问任意属性、调用任意方法、赋给其他类型 |

例如：

```python
def handle_unknown(value: object) -> None:
    # value.upper()  # 类型检查器会报错：object 不保证有 upper()
    if isinstance(value, str):
        print(value.upper())  # 已确认是 str，可以调用


def handle_any(value: Any) -> None:
    value.upper()             # 类型检查器通常放行
    value.method_not_exist()  # 即使方法不存在，类型检查器也通常放行
```

所以 `Any` 不是“所有类型的共同父类”，而是 `typing` 提供的“跳过类型检查”标记；`object` 才是实际存在的内置基类：

```python
isinstance("hello", object)  # True
# isinstance("hello", Any)  # 错误：Any 不能这样用于运行时类型判断
```

选择原则：确实不知道类型、但仍希望类型检查器保护后续操作时使用 `object`；只有在接入动态库、无类型数据或暂时无法准确标注时才使用 `Any`。

### 3.3 `tuple[str, bytes]` 不是字典

项目代码：

```python
def pandas_skill_file() -> tuple[str, bytes]:
    ...
```

读作：函数返回一个二元组：

1. 第一个元素是 `str`。
2. 第二个元素是 `bytes`。

例如：

```python
result = ("SKILL.md", b"file content")
```

元组可以包含不同类型的元素。下面的检索结果标注也是同一个道理：

```python
list[tuple[Document, float]]
```

它表示外层是列表，列表中的每一项都是：

```python
(document对象, 分数)
```

两种常见元组标注：

```python
tuple[str, bytes]       # 固定两个位置，并分别指定类型
tuple[Document, ...]    # 任意多个 Document
```

### 3.4 `Embeddings | None = None` 要分成两段

项目代码：

```python
embeddings: Embeddings | None = None
```

第一段是类型：

```python
Embeddings | None
```

表示参数既可以是 `Embeddings` 对象，也可以是 `None`。`|` 在类型标注中表示联合类型。

第二段是默认值：

```python
= None
```

表示调用函数时可以省略这个参数，省略后它的值就是 `None`：

```python
build_vector_store(documents)                  # 使用默认值 None
build_vector_store(documents, embeddings=None) # 显式传 None
build_vector_store(documents, embeddings=model)
```

下面的写法同理：

```python
text: str | None = None
```

表示 `text` 可以是字符串，也可以为空值 `None`，并且默认是 `None`。

### 3.5 `Literal[...]` 是固定值类型

项目中见过：

```python
response_format: Literal["content", "content_and_artifact"]
```

读作：`response_format` 只能从这两个字符串字面值中选择：

```python
"content"
"content_and_artifact"
```

`Literal` 不是一个枚举类，它是类型标注：

```python
from typing import Literal
```

编辑器和类型检查器可以据此发现拼写错误，但 Python 通常不会因为标注了 `Literal` 就自动做运行时校验。

### 3.6 类型标注不会自动创建对象

```python
documents: list[Document]
```

这一行只声明类型，并没有创建列表。真正创建空列表需要：

```python
documents: list[Document] = []
```

同样，函数的入参类型和返回类型只是约定：

```python
def build_model(model_class: type) -> object:
    ...
```

它们用于阅读、编辑器提示和静态检查，不代表 Python 会自动初始化或转换对象。

## 4. 列表、字典、元组、集合、索引和属性

### 4.1 Python 的 `dict` 相当于其他语言里的 Map

历史代码中见过：

```python
return {
    "ContactInfo": ContactInfo,
    "ProductReview": ProductReview,
    "SupportTicket": SupportTicket,
}
```

返回值是 Python 字典 `dict`，可以把它理解为 Java 等语言中的 Map：

```text
key                 value
"ContactInfo"  ->  ContactInfo 类对象
"ProductReview" -> ProductReview 类对象
```

读取字典：

```python
ContactInfo = deps["ContactInfo"]
```

这里不是创建类，而是从字典中取出之前保存的类对象，再赋给变量。

字典可以继续嵌套字典：

```python
config = {
    "configurable": {
        "thread_id": "l6-agent-memory-demo",
    }
}
```

读取内层值：

```python
thread_id = config["configurable"]["thread_id"]
```

`parameters`、`type`、`properties` 等字典 key 对 Python 本身没有特殊含义：

```python
schema = {
    "type": "object",
    "properties": {},
}
```

它们是否必须出现，由 JSON Schema、接口协议或业务代码规定，而不是由 Python 的字典语法规定。

### 4.2 中括号可能表示列表，也可能表示取值

创建列表：

```python
middleware = [FilesystemMiddleware(backend=backend)]
```

即使只有一个元素，也需要中括号才能表示“这是一个列表”：

```python
one_object = FilesystemMiddleware(backend=backend)
one_item_list = [FilesystemMiddleware(backend=backend)]
```

在已有对象后使用中括号，则通常表示索引、切片或按 key 取值：

```python
docs[0]              # 列表的第一个元素
messages[-1]         # 列表的最后一个元素
deps["Document"]     # 字典中 key 为 Document 的值
text[:10000]         # 字符串切片
```

### 4.3 `docs[0].page_content` 分两步执行

```python
return docs[0].page_content
```

执行顺序：

```python
first_document = docs[0]
content = first_document.page_content
return content
```

- `[0]` 取列表第一个 `Document`。
- `.page_content` 读取这个对象的属性。
- 返回的是第一个 `Document` 的全部正文字符串。

### 4.4 `[-1]` 表示最后一个元素

```python
result["messages"][-1]
```

先从字典中取出 `messages` 列表，再取列表最后一项：

```text
-1  最后一项
-2  倒数第二项
-3  倒数第三项
```

### 4.5 圆括号不一定代表元组

下面只是为了多行排版和自动拼接字符串，并不是元组：

```python
body = (
    "Agent 是模型和工具的循环。"
    "模型拿到工具结果后可以继续决策。"
)
```

结果是一个字符串：

```python
"Agent 是模型和工具的循环。模型拿到工具结果后可以继续决策。"
```

创建单元素元组必须有逗号：

```python
not_a_tuple = ("hello")
one_item_tuple = ("hello",)
```

### 4.6 `scores.items()` 返回什么

假设字典是：

```python
scores = {
    "doc_b": 0.91,
    "doc_a": 0.72,
}
```

调用：

```python
scores.items()
```

返回的是一个字典视图 `dict_items`，不是普通列表：

```python
dict_items([
    ("doc_b", 0.91),
    ("doc_a", 0.72),
])
```

遍历这个视图时，每次得到一个 `(key, value)` 二元组：

```python
for item in scores.items():
    print(item)

# ("doc_b", 0.91)
# ("doc_a", 0.72)
```

也可以直接进行元组拆包：

```python
for key, score in scores.items():
    print(key)
    print(score)
```

等价于：

```python
for item in scores.items():
    key = item[0]
    score = item[1]
```

如果确实需要普通列表，可以显式转换：

```python
score_pairs = list(scores.items())
```

`dict_items` 是动态视图，它引用原字典。创建视图后再修改字典，之后查看视图时会反映新数据：

```python
view = scores.items()
scores["doc_c"] = 0.85

print(list(view))
# [("doc_b", 0.91), ("doc_a", 0.72), ("doc_c", 0.85)]
```

不要在遍历字典视图的同时增删字典元素，否则可能抛出：

```text
RuntimeError: dictionary changed size during iteration
```

### 4.7 `dict` 有顺序，但不是自动排序

Python 的 `dict` 按照插入顺序迭代。这个行为从 Python 3.7 开始是语言正式保证。

```python
scores = {}
scores["doc_b"] = 0.91  # 第一个插入
scores["doc_a"] = 0.72  # 第二个插入
scores["doc_c"] = 0.85  # 第三个插入
```

因此：

```python
list(scores.items())
```

稳定得到：

```python
[
    ("doc_b", 0.91),
    ("doc_a", 0.72),
    ("doc_c", 0.85),
]
```

这里的“有序”只表示保留插入先后，不表示自动按照 key 或 value 排序。

只要同一个字典没有变化，多次调用的遍历顺序就不会随机改变：

```python
list(scores.items())
list(scores.items())
```

更新已有 key 的 value 通常不改变位置：

```python
scores["doc_a"] = 0.99
```

删除后重新插入，则会移动到最后：

```python
del scores["doc_a"]
scores["doc_a"] = 0.99
```

有一种情况需要区分：如果每次都重新构造字典，并且数据来自 `set` 等不保证迭代顺序的来源，那么新字典的插入顺序可能随来源变化。不是同一个字典的 `items()` 在随机改变，而是每次创建字典时的插入顺序不同。

字典相等性只比较 KV，不比较插入顺序：

```python
{"a": 1, "b": 2} == {"b": 2, "a": 1}
# True
```

### 4.8 `dict` 是 Map，Map 和“是否有序”不冲突

“映射”和“顺序”是两个独立特性：

| 特性 | 回答的问题 |
| --- | --- |
| Mapping / Map | 能否通过 key 找到 value？ |
| 迭代顺序 | 遍历 KV 时按照什么顺序返回？ |

Python 的 `dict` 可以理解成：

```text
哈希映射
+ key 唯一
+ 平均 O(1) 的按 key 查找
+ 保持插入顺序
- 不会自动按 key 或 value 排序
```

Python 标准库没有另外提供一个常用的 `HashMap` 或 `unordered_map` 容器。即使业务完全不关心顺序，仍然直接使用 `dict`，只是不依赖它的遍历顺序。

不同语言可以粗略对照为：

| 语言 | 常用 KV 映射 |
| --- | --- |
| Python | `dict` |
| Java | `HashMap`、`LinkedHashMap` |
| C++ | `unordered_map`、`map` |
| Go | `map` |

如果只需要不重复的元素、不需要 value，使用 `set`：

```python
document_keys = {"doc_a", "doc_b"}
```

三者不要混淆：

```text
dict     保存 key -> value
set      只保存不重复的元素
map()    对可迭代对象逐项转换的函数，不是 Map 容器
```

例如 Python 的 `map()`：

```python
doubled = map(lambda number: number * 2, [1, 2, 3])
print(list(doubled))
# [2, 4, 6]
```

### 4.9 `sorted(scores.items(), key=..., reverse=True)` 完整语法

本次代码：

```python
return [
    (documents_by_key[key], score)
    for key, score in sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )
]
```

执行过程分为五步。

第一步，`scores.items()` 产生 `(key, score)`：

```python
[
    ("doc_a", 0.72),
    ("doc_b", 0.91),
]
```

第二步，`lambda item: item[1]` 取每个二元组的第二项作为排序依据：

```python
def get_score(item):
    return item[1]
```

第三步，`sorted(..., reverse=True)` 创建一个从高分到低分的新列表：

```python
[
    ("doc_b", 0.91),
    ("doc_a", 0.72),
]
```

`sorted()` 不会修改原来的 `scores` 字典。

第四步，列表推导式把二元组拆成两个变量：

```python
for key, score in sorted_pairs:
    ...
```

第五步，使用 key 找到原始文档，再组成新的二元组：

```python
(documents_by_key[key], score)
```

最终类型近似为：

```python
list[tuple[Document, float]]
```

完整普通循环写法：

```python
sorted_pairs = sorted(
    scores.items(),
    key=lambda item: item[1],
    reverse=True,
)

result = []

for key, score in sorted_pairs:
    document = documents_by_key[key]
    result.append((document, score))

return result
```

这里有三个不同的 `key` 用法：

| 代码 | 含义 |
| --- | --- |
| `for key, score` | 名为 `key` 的循环变量 |
| `sorted(..., key=lambda ...)` | `sorted()` 的排序依据参数 |
| `documents_by_key[key]` | 使用循环变量从字典取值 |

Python 的排序是稳定排序。如果两个 score 相同，它们会保持进入 `sorted()` 之前的相对顺序；这里也就是字典中的插入顺序。

如果 `scores` 中存在某个 key，但 `documents_by_key` 中没有该 key：

```python
documents_by_key[key]
```

会抛出 `KeyError`。

### 4.10 `dict.get()`、`setdefault()` 和 `pop()`

这三个方法都可以处理“key 可能不存在”的情况，但是否修改字典不同。

Part 15 的累计分数代码：

```python
scores[key] = scores.get(key, 0.0) + 1.0 / (rank + k)
```

`scores.get(key, 0.0)` 表示：

- key 已存在：返回对应 value。
- key 不存在：返回默认值 `0.0`。
- 不会因为读取默认值而向字典新增 key。

它等价于：

```python
if key in scores:
    old_score = scores[key]
else:
    old_score = 0.0

scores[key] = old_score + 1.0 / (rank + k)
```

同一文件还使用了：

```python
documents_by_key.setdefault(key, document)
```

`setdefault(key, default)` 表示：

- key 已存在：返回旧值，不覆盖它。
- key 不存在：写入 `default`，然后返回这个默认值。

这里没有接收返回值，只利用了“第一次出现时保存 Document”的副作用。

`2_langchain/L3_Function_Calling_In_Langchain.py` 中还有：

```python
description = schema.pop("description", None)
```

`pop(key, default)` 会取出并删除 key：

- key 已存在：删除并返回原 value。
- key 不存在：返回 `default`。
- 如果没有提供默认值且 key 不存在，则抛出 `KeyError`。

对比：

| 写法 | key 不存在时 | 是否修改字典 |
| --- | --- | --- |
| `mapping[key]` | 抛出 `KeyError` | 否 |
| `mapping.get(key, default)` | 返回 `default` | 否 |
| `mapping.setdefault(key, default)` | 写入并返回 `default` | 是 |
| `mapping.pop(key, default)` | 返回 `default` | key 存在时会删除 |

### 4.11 `set`、成员判断和保序去重

Part 5 使用集合记录已经见过的查询：

```python
unique: list[str] = []
seen: set[str] = set()

for query in candidates:
    normalized = query.casefold().strip()
    if normalized in seen:
        continue
    seen.add(normalized)
    unique.append(query.strip())
```

这里：

- `set()` 创建空集合；空的 `{}` 创建的是字典，不是集合。
- `value in seen` 判断集合中是否已有该值。
- `seen.add(value)` 把值加入集合。
- 集合中的元素不会重复，成员查找通常也比在长列表中逐项查找更合适。

代码同时保留 `seen` 和 `unique`，是因为它们职责不同：

```text
seen    负责快速判断是否重复
unique  负责保存原始对象和首次出现顺序
```

不能只把结果放进 `set` 后再期待它提供业务上的首次命中顺序。

### 4.12 `list[list[Document]]` 与两层索引

Part 5 和 Part 15 的批量检索结果标注为：

```python
ranked_lists: list[list[Document]]
```

它表示：

- 外层列表：每一项对应一条 query。
- 内层列表：当前 query 按相关度排列的多个 `Document`。

例如：

```python
ranked_lists = [
    [query1_top1, query1_top2],
    [query2_top1, query2_top2],
]
```

两层索引的含义：

```python
ranked_lists[0]     # query1 的整组结果
ranked_lists[0][0]  # query1 的 Top-1 Document
ranked_lists[1][1]  # query2 的 Top-2 Document
```

`list[list[Document]]` 只是数据形状的类型标注，不会自动执行排序；内层为什么已经按相关度排序，是 Retriever 的行为。

### 4.13 `[:4]`、`[:6]` 对列表同样是切片

Part 15：

```python
queries = build_query_variants(question, use_live=options.use_live)[:4]
```

Part 5：

```python
return unique[:6]
```

对列表使用 `[:N]` 会创建一个新列表，最多取得前 N 项：

```python
values = ["a", "b", "c", "d", "e"]

values[:3]  # ["a", "b", "c"]
values[:9]  # 不会报错，返回全部五项
```

它不会修改原列表。切片语法相同，但具体切的是字符、字节还是列表元素，取决于被切片对象的类型。

## 5. 字符串：文档字符串、切片、换行、拆分、规范化和正则清理

### 5.1 单独出现的三引号字符串可能是文档字符串

历史问题中的代码：

```python
def get_current_weather(location):
    """Get the current weather in a given location."""
    ...
```

函数体第一条语句是字符串时，它会成为函数的文档字符串 `docstring`：

```python
print(get_current_weather.__doc__)
```

它没有赋给普通变量，但 Python 会把它保存在函数的 `__doc__` 属性里，供编辑器提示、`help()` 和文档工具读取。

如果一个普通字符串既不位于模块、类或函数的第一条语句，也没有赋值或参与运算，它通常只是一个无实际效果的字符串表达式。

### 5.2 `[:10000]` 是字符切片，不是字节切片

```python
page_content = load_article()[:10000]
```

等价于：

```python
all_content = load_article()
page_content = all_content[0:10000]
```

`page_content` 是 `str`，所以这里取的是前 10000 个字符。只有对象是 `bytes` 时，相同切片才是在切字节。

切片规则：

```python
value[start:stop:step]
```

其中 `stop` 位置本身不包含在结果中。

项目里还见过：

```python
delta = content[len(seen):]
```

它表示从已经看过的字符数量开始，取后面新增的内容。

### 5.3 `"\n"` 是换行符

```python
soup.get_text("\n")
```

`"\n"` 是包含一个换行字符的字符串。这里把换行符作为不同 HTML 文本节点之间的分隔符。

常见转义字符：

```text
\n   换行
\t   制表符
\\   一个反斜杠
\"   双引号
```

### 5.4 f-string 可以把表达式放进字符串

```python
f"python{sys.version_info.major}.{sys.version_info.minor}"
```

假设当前 Python 是 3.12，结果就是：

```python
"python3.12"
```

花括号中的表达式会先执行，再转换为字符串。

### 5.5 `split()`、`strip()` 和 `join()`

项目代码：

```python
parts = [
    part.strip()
    for part in table_names.split(",")
    if part.strip()
]
```

分步看：

```python
table_names.split(",")  # 按逗号拆成字符串列表
part.strip()             # 删除字符串首尾空白
if part.strip()          # 只保留清理后非空的字符串
```

例如：

```python
" users, orders,  ".split(",")
# [" users", " orders", "  "]

[part.strip() for part in [" users", " orders", "  "] if part.strip()]
# ["users", "orders"]
```

`join()` 做相反方向的工作，把多个字符串拼成一个字符串：

```python
", ".join(["users", "orders"])
# "users, orders"
```

记忆方式：

```python
分隔符.join(字符串序列)
```

### 5.6 `partition()` 按第一次出现的位置固定切成三部分

```python
text.partition(separator)
```

它从左向右寻找分隔符第一次出现的位置，并且始终返回一个包含三个字符串的元组：

```python
(分隔符前面的内容, 分隔符本身, 分隔符后面的内容)
```

例如：

```python
"name=wangfei=admin".partition("=")
# ("name", "=", "wangfei=admin")
```

如果没有找到分隔符，返回：

```python
"name".partition("=")
# ("name", "", "")
```

RAG 课件使用它提取标签中间的 context：

```python
context = message_text.partition("<context>")[2].partition("</context>")[0].strip()
```

分步写法：

```python
after_opening = message_text.partition("<context>")[2]
before_closing = after_opening.partition("</context>")[0]
context = before_closing.strip()
```

- 第一个 `[2]` 取得 `<context>` 后面的内容。
- 第二个 `[0]` 取得 `</context>` 前面的内容。
- `strip()` 删除最终结果首尾的空白。

与 `split(separator, 1)` 相比，`partition()` 会保留分隔符，并且无论是否找到都固定返回三个元素；`split()` 不保留分隔符，返回列表且长度可能不同。`rpartition()` 的规则相同，但从右侧最后一次出现的位置切分。分隔符不能为空字符串，否则会抛出 `ValueError`。

### 5.7 `splitlines()`、`casefold()` 和 `re.sub()` 清理模型输出

Part 5 会把模型生成的多行查询清理并去重：

```python
candidates.extend(_clean_query(line) for line in text.splitlines())
normalized = query.casefold().strip()
```

`splitlines()` 按换行边界拆分字符串：

```python
"问题一\n问题二\n问题三".splitlines()
# ["问题一", "问题二", "问题三"]
```

它和 `split("\n")` 类似，但还能统一处理 `\r\n` 等不同系统的换行形式。

`casefold()` 返回适合做不区分大小写比较的新字符串：

```python
"RAG".casefold() == "rag".casefold()  # True
```

它不会修改原字符串。和 `lower()` 相比，`casefold()` 对部分非英语字符的大小写归一化更彻底，因此更适合作为去重 key。

清理查询编号的函数使用了正则替换：

```python
def _clean_query(line: str) -> str:
    return re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
```

`re.sub(pattern, replacement, text)` 表示把匹配到的内容替换掉。这里 replacement 是空字符串，所以是在删除行首编号：

```python
_clean_query("1. 什么是 RAG？")  # "什么是 RAG？"
_clean_query("- 如何切块？")     # "如何切块？"
```

模式中的主要部分：

| 正则片段 | 含义 |
| --- | --- |
| `r"..."` | 原始字符串，反斜杠不先被 Python 转义 |
| `^` | 只从字符串开头匹配 |
| `\s*` | 零个或多个空白字符 |
| `[-*]` | `-` 或 `*` 项目符号 |
| `\d+[.)]` | 一个或多个数字，后跟 `.` 或 `)` |
| `A\|B` | 匹配 A 或 B |

最后再调用 `.strip()`，删除清理编号后遗留的首尾空白。

## 6. 列表推导式与生成器表达式

### 6.1 最基础的列表推导式

```python
[item for item in items]
```

读作：

> 遍历 `items`，每次把当前元素放进新列表。

它等价于：

```python
result = []
for item in items:
    result.append(item)
```

列表推导式最前面的 `item` 是“新列表中要放入的表达式”，后面的 `for item in items` 才是循环。

### 6.2 对每个元素做转换

```python
[result.papers for result in results]
```

如果每个 `result.papers` 本身也是列表，最终就会得到嵌套列表：

```python
[
    [paper1, paper2],
    [paper3],
    [paper4, paper5],
]
```

另一个历史示例：

```python
return [dict(row) for row in cursor.fetchall()]
```

表示遍历查询到的每一行，把每个 `row` 转换为字典，再组成字典列表。

### 6.3 带过滤条件的列表推导式

```python
[part.strip() for part in values if part.strip()]
```

等价于：

```python
result = []
for part in values:
    if part.strip():
        result.append(part.strip())
```

末尾的 `if` 决定当前元素是否进入新列表。

### 6.4 双层列表推导式 `flatten`

项目历史代码：

```python
def flatten(list_of_lists):
    return [item for sublist in list_of_lists for item in sublist]
```

它应当按照普通循环从左向右读：

```python
result = []

for sublist in list_of_lists:  # 外层循环
    for item in sublist:       # 内层循环
        result.append(item)    # 放进新列表的元素
```

输入：

```python
[["a", "b"], ["c"], ["d", "e"]]
```

输出：

```python
["a", "b", "c", "d", "e"]
```

### 6.5 推导式默认保留遍历顺序

列表推导式会按照源数据的遍历顺序追加元素。只要输入结果本身是按请求顺序返回的，推导后的列表也会保持这个顺序。

### 6.6 生成器表达式与 `list.extend()`

Part 5：

```python
candidates.extend(
    _clean_query(line)
    for line in text.splitlines()
)
```

下面这一段：

```python
(_clean_query(line) for line in text.splitlines())
```

是生成器表达式。它和列表推导式外形相似，但不会先创建完整列表，而是在遍历时逐项产生结果。

当生成器表达式是函数调用的唯一参数时，可以省略它自己的圆括号，所以项目代码写成：

```python
candidates.extend(_clean_query(line) for line in text.splitlines())
```

`extend()` 会遍历收到的可迭代对象，把其中每一项追加到原列表：

```python
candidates = ["原始问题"]
candidates.extend(["改写一", "改写二"])

# ["原始问题", "改写一", "改写二"]
```

它与 `append()` 不同：

```python
values = [1]
values.append([2, 3])  # [1, [2, 3]]，把整个列表作为一项

values = [1]
values.extend([2, 3])  # [1, 2, 3]，逐项追加
```

`extend()` 会原地修改列表，通常返回 `None`。

## 7. 函数参数：逗号、默认值、`*`、`*args`、`**kwargs`、`**config`

### 7.1 函数参数之间的逗号只是分隔符

项目代码：

```python
def split_documents(
    documents: Iterable[Document],
    *,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
) -> list[Document]:
    ...
```

每个逗号把一个参数与下一个参数分开。多行写法和下面的单行写法语义相同：

```python
def split_documents(documents, *, chunk_size=300, chunk_overlap=50):
    ...
```

最后一个参数后的逗号称为尾随逗号，便于以后新增参数和保持格式整齐。

### 7.2 单独的 `*`：后面必须使用参数名传值

签名中的：

```python
*,
chunk_size: int = 300,
chunk_overlap: int = 50,
```

表示 `*` 后面的参数是“仅限关键字参数”：

```python
split_documents(documents, chunk_size=500, chunk_overlap=100)  # 正确
split_documents(documents, 500, 100)                           # TypeError
```

历史代码中的写法同理：

```python
def database_connection(
    database_path: Path,
    *,
    read_only: bool = False,
):
    ...
```

### 7.3 有默认值的参数可以不传

```python
def build_retriever(
    vector_store,
    k=3,
    search_type="similarity",
    fetch_k=None,
    lambda_mult=0.5,
):
    ...
```

因此可以只传前两个：

```python
build_retriever(vector_store, k=3)
```

没有显式传入的参数会使用默认值。也可以覆盖其中一部分：

```python
build_retriever(
    vector_store,
    k=3,
    search_type="mmr",
    fetch_k=6,
    lambda_mult=0.5,
)
```

Python 根据参数名匹配，不需要“自动识别多个 `int`”。

下面也是关键字参数，参数值恰好是一个列表：

```python
load_skills(sources=["/skills/"])
```

这里 `sources` 是参数名，`["/skills/"]` 是传入的列表值。

### 7.4 `*args` 收集多余的位置参数

```python
def demo(*args):
    print(args)

demo(1, 2, 3)
# args == (1, 2, 3)
```

`args` 是元组。名字可以更换，但大家通常使用 `args`。

### 7.5 `**kwargs` 收集多余的关键字参数

```python
def build_model(**kwargs):
    print(kwargs)

build_model(timeout=60, temperature=0.2)
# kwargs == {"timeout": 60, "temperature": 0.2}
```

`kwargs` 是字典，名称来自 keyword arguments。

历史代码：

```python
def load_dotenv(*_args, **_kwargs):
    return False
```

这里的函数接受任意位置参数和任意关键字参数，但不使用它们。变量名前的 `_` 表示“故意不用”的命名习惯。

### 7.6 调用函数时的 `**config` 是拆字典

项目代码：

```python
config = {
    "chunk_size": 140,
    "chunk_overlap": 30,
}

split_documents_token_aware(documents, **config)
```

等价于：

```python
split_documents_token_aware(
    documents,
    chunk_size=140,
    chunk_overlap=30,
)
```

要求字典 key 与函数参数名一致。`**` 不会根据多个 `int` 自动猜参数。

定义和调用时的区别：

| 位置 | 写法 | 含义 |
| --- | --- | --- |
| 函数定义 | `def f(**kwargs)` | 收集关键字参数为字典 |
| 函数调用 | `f(**config)` | 把字典拆成关键字参数 |

### 7.7 类和函数本身也可以作为参数或返回值

历史代码中见过：

```python
ChatOpenAI = deps["ChatOpenAI"]
model = build_zhipu_chat_model(ChatOpenAI)
```

`deps["ChatOpenAI"]` 取出的是类对象。Python 中类和函数都是可以保存、传参和返回的对象：

```python
def build_zhipu_chat_model(model_class):
    return model_class(model="glm")
```

流程是：

```text
传入 ChatOpenAI 类
    ↓
model_class 指向该类
    ↓
model_class(...) 调用类
    ↓
创建并返回实例
```

入参是“类对象”，返回值是“这个类创建的实例”，不是同一个对象。

### 7.8 `lambda` 是匿名函数

项目代码：

```python
lambda value: build_query_variants(
    str(value),
    use_live=options.use_live,
)
```

它等价于：

```python
def generate(value):
    return build_query_variants(
        str(value),
        use_live=options.use_live,
    )
```

当外部框架调用这个函数并传入 `question` 时：

```text
question -> value -> build_query_variants(str(value), ...)
```

另一个项目写法：

```python
lambda _: queries
```

`_` 仍然会接收一个参数，但下划线表示“这个参数不使用”。无论传入什么，它都返回外层已有的 `queries`。

`lambda` 可以读取外层作用域中的 `queries`、`options` 等变量，这称为闭包捕获。

### 7.9 `return` 只能写在函数体中

```python
def get_path():
    return database_path
```

如果直接在 Python 交互环境顶层输入：

```python
return database_path
```

会得到：

```text
SyntaxError: 'return' outside function
```

### 7.10 `argparse` 的 `action`、`choices` 和 `default`

项目代码：

```python
parser.add_argument(
    "--web-source",
    action="store_true",
)

parser.add_argument(
    "--embedding",
    choices=("local", "hash", "glm"),
    default="local",
)
```

`add_argument()` 默认使用 `action="store"`：命令行出现选项后，读取它后面的一个值并保存。因此即使不写 `choices`，`--embedding local` 也可以接收字符串；`choices` 只负责限制允许的值：

```bash
python demo.py --embedding glm       # args.embedding == "glm"
python demo.py --embedding unknown   # argparse 报错
python demo.py                       # args.embedding == "local"
```

`default="local"` 表示没有传 `--embedding` 时使用 `local`。

`action="store_true"` 是 `argparse` 规定的固定 action 名称。它把选项变成不带值的布尔开关：

```bash
python demo.py                # args.web_source is False
python demo.py --web-source   # args.web_source is True
```

不能写成 `--web-source true`，因为 `store_true` 本身不读取后续值。长选项名中的连字符默认会转换成属性名中的下划线，所以 `--web-source` 通过 `args.web_source` 读取。

三者的职责不要混在一起：

| 配置 | 作用 |
| --- | --- |
| 默认的 `action="store"` | 读取并保存选项后面的值 |
| `action="store_true"` | 选项出现即保存 `True`，未出现为 `False` |
| `choices=(...)` | 校验传入值是否属于允许范围 |
| `default=...` | 选项未出现时提供默认值 |

## 8. `for`、`enumerate()` 和变量拆包

### 8.1 `for` 后面的冒号表示循环代码块开始

```python
for chunk in chunks:
    print(chunk)
```

冒号后缩进的语句属于循环体。Python 使用缩进划分代码块，而不是使用 `{}`。

### 8.2 `enumerate()` 同时提供序号和元素

项目代码：

```python
for rank, (document, score) in enumerate(matches, start=1):
    ...
```

假设：

```python
matches = [
    (doc1, 0.91),
    (doc2, 0.83),
]
```

`enumerate(matches, start=1)` 依次产生：

```python
(1, (doc1, 0.91))
(2, (doc2, 0.83))
```

循环变量进行了两层拆包：

```text
rank                     <- 1
(document, score)        <- (doc1, 0.91)
```

### 8.3 一个赋值语句也可以拆包

```python
file_descriptor, raw_path = tempfile.mkstemp(...)
```

`mkstemp()` 返回二元组，等价于：

```python
result = tempfile.mkstemp(...)
file_descriptor = result[0]
raw_path = result[1]
```

异步并发的返回值也可以这样拆包：

```python
invoke_result, batch_result = await asyncio.gather(
    invoke_task,
    batch_task,
)
```

### 8.4 `zip()` 与拆包组合

```python
for question, documents in zip(questions, batch_documents):
    ...
```

每次从 `zip()` 取得一个二元组，再拆成 `question` 和 `documents`。详细规则见第 2 节。

## 9. 条件判断：三元表达式、类型检查、属性检查和真假值

### 9.1 Python 的条件表达式

历史代码：

```python
arguments = (
    json.loads(raw_arguments)
    if isinstance(raw_arguments, str)
    else raw_arguments
)
```

读法是：

```text
条件为真时的值 if 条件 else 条件为假时的值
```

等价于：

```python
if isinstance(raw_arguments, str):
    arguments = json.loads(raw_arguments)
else:
    arguments = raw_arguments
```

另一个历史例子：

```python
schema = (
    args_schema.model_json_schema()
    if hasattr(args_schema, "model_json_schema")
    else args_schema.schema()
)
```

你的理解是正确的：如果条件为真，就执行 `model_json_schema()`，并把它的返回值赋给 `schema`；否则执行 `schema()`。

还有：

```python
checkpointer = deps["InMemorySaver"]() if use_memory else None
```

表示启用内存时创建对象，否则使用 `None`。

RAG 课件中的多行写法：

```python
active_embeddings = (
    embeddings
    if embeddings is not None
    else build_embeddings(mode=embedding_mode)
)
```

仍然是同一个条件表达式，可以从中间的条件开始读：

```text
如果 embeddings 不是 None
    就把已有的 embeddings 赋给 active_embeddings
否则
    调用 build_embeddings(...)，把它返回的 Embeddings 对象赋给 active_embeddings
```

它等价于：

```python
if embeddings is not None:
    active_embeddings = embeddings
else:
    active_embeddings = build_embeddings(mode=embedding_mode)
```

这里的圆括号只用于把一个长表达式分成多行，不是函数调用，也不是元组。Python 创建元组的关键是逗号，例如 `(embeddings,)`；这里只有括号而没有逗号，所以整个表达式只产生一个值。它也不是匿名函数：匿名函数必须出现 `lambda`，例如 `lambda value: value`。

更一般地，只要一个表达式还位于 `()`、`[]` 或 `{}` 内，Python 就允许在合适的位置直接换行，这叫隐式续行，不需要在行尾添加 `\`：

```python
queries_documents = (
    RunnableLambda(
        lambda _: queries
    ) | retriever.map()
).invoke(question)
```

这里的换行和缩进只影响可读性，不改变表达式的执行结果。它等价于：

```python
queries_documents = (
    RunnableLambda(lambda _: queries) | retriever.map()
).invoke(question)
```

最外层的 `(...)` 包住完整的 `RunnableLambda(...) | retriever.map()` 表达式，所以最后的 `.invoke(question)` 调用的是整条组合后的 Chain。

`RunnableLambda(...)` 这次只有一个位置参数 `lambda _: queries`，所以不需要用逗号分隔参数。多行函数调用可以选择添加尾逗号：

```python
RunnableLambda(
    lambda _: queries,
)
```

在函数调用中，这个尾逗号不会把参数变成元组，仍然只传入一个 `lambda` 对象；而脱离函数调用后，`(value,)` 才表示单元素元组。

条件表达式只执行被选中的分支：已有 `embeddings` 时不会调用 `build_embeddings(...)`。两条分支最终都应得到一个实现了 LangChain `Embeddings` 接口的对象，例如 `LocalMiniLMEmbeddings` 或 `StableHashEmbeddings`。

### 9.2 `isinstance()` 判断对象的运行时类型

```python
isinstance(raw_arguments, str)
```

如果 `raw_arguments` 是字符串或 `str` 的子类实例，返回 `True`，否则返回 `False`。

```python
isinstance("hello", str)  # True
isinstance(123, str)      # False
```

也可以一次检查多个类型：

```python
isinstance(value, (str, bytes))
```

### 9.3 `hasattr()` 判断属性或方法是否存在

```python
hasattr(args_schema, "model_json_schema")
```

表示检查 `args_schema` 是否有名为 `model_json_schema` 的属性或方法，返回布尔值。

### 9.4 `getattr()` 安全读取属性

```python
content = getattr(message, "content", "")
```

等价思路：

```python
if hasattr(message, "content"):
    content = message.content
else:
    content = ""
```

第三个参数 `""` 是属性不存在时的默认值。

### 9.5 空容器和空字符串会被当作 False

Python 中常见的假值：

```python
False
None
0
""
[]
{}
()
```

因此：

```python
if not matched:
    ...
```

如果 `matched` 是列表，这通常表示列表为空，而不是列表不为空。

同理：

```python
if part.strip():
    parts.append(part.strip())
```

`strip()` 后还有内容时条件为真；变成空字符串时条件为假。

### 9.6 `or` 可以提供后备值

```python
agent = agent or build_voice_agent(deps)
```

如果传入的 `agent` 是真值，就继续使用它；否则创建一个新 agent。

```python
content = getattr(message, "content", "") or ""
```

如果属性不存在、为 `None` 或为空字符串，最终统一得到空字符串。

### 9.7 `continue` 跳过本次循环剩余代码

```python
if event.type != "stt_output" or not event.transcript:
    continue
```

条件满足时，不再执行当前循环后面的语句，直接进入下一轮循环。

### 9.8 `try / except` 捕获异常

历史代码：

```python
try:
    from dotenv import find_dotenv, load_dotenv
except ImportError:
    find_dotenv = None

    def load_dotenv(*_args, **_kwargs):
        return False
```

含义是：

1. 尝试导入依赖。
2. 如果发生 `ImportError`，执行后备定义。
3. 后续代码仍然可以调用 `load_dotenv(...)`，只是后备函数固定返回 `False`。

下面的写法会保留原异常链：

```python
except ImportError as exc:
    raise RuntimeError("缺少依赖") from exc
```

排错时既能看到新的业务错误，也能看到最初的导入错误。

## 10. 类、对象、方法、默认工厂和装饰器

### 10.1 `__init__` 在创建实例时初始化属性

历史代码：

```python
class KeywordEmbeddings:
    def __init__(self):
        self.keywords = [
            "task",
            "decomposition",
            "rag",
            "retrieval",
        ]
```

使用：

```python
embeddings = KeywordEmbeddings()
```

Python 创建对象时直接调用类，不需要 Java 风格的 `new` 关键字。

执行过程：

1. 创建 `KeywordEmbeddings` 实例。
2. 自动调用 `__init__(self)`。
3. 把关键词列表保存到当前实例的 `self.keywords` 属性。

`self` 代表当前对象本身。

### 10.2 `_embed` 的单下划线是命名约定

```python
def _embed(self, text: str):
    ...
```

单下划线表示“这是类或模块内部使用的实现细节”。它不是强制私有，外部仍然可以调用：

```python
embeddings._embed("rag")
```

但通常建议外部使用公开方法：

```python
embeddings.embed_query("rag")
```

### 10.3 `@dataclass(frozen=True)` 是装饰器

项目代码：

```python
@dataclass(frozen=True)
class EmbeddingRuntime:
    mode: str
    model: str
```

`@dataclass(...)` 会处理紧随其后的类，自动生成常用方法，例如 `__init__`、`__repr__` 和 `__eq__`。

`frozen=True` 表示实例创建后不允许普通字段重新赋值：

```python
runtime = EmbeddingRuntime(mode="local", model="MiniLM")
runtime.mode = "remote"  # FrozenInstanceError
```

装饰器的一般形式：

```python
@decorator
def function():
    ...
```

概念上接近：

```python
function = decorator(function)
```

项目中的 `@tool(...)` 也是 Python 装饰器语法，只是具体增强逻辑由 LangChain 提供。

### 10.4 `对象.属性 = 值` 是属性赋值

```python
conn.row_factory = sqlite3.Row
```

这不是定义局部变量，而是把 `sqlite3.Row` 保存到 `conn` 对象的 `row_factory` 属性中。

### 10.5 `@classmethod` 与 `cls`

`2_langchain/L12_Voice_Agent.py`：

```python
@classmethod
def stt_chunk(cls, text: str):
    return cls(type="stt_chunk", text=text, transcript=text)
```

`@classmethod` 把方法绑定到类，而不是绑定到某个实例。调用时不需要手动传入 `cls`：

```python
event = VoiceAgentEvent.stt_chunk("你好")
```

Python 会自动把 `VoiceAgentEvent` 作为第一个参数 `cls`。如果要写出接近底层函数的概念形式，可以表示为：

```python
VoiceAgentEvent.stt_chunk.__func__(VoiceAgentEvent, "你好")
```

方法内部的：

```python
return cls(type="stt_chunk", ...)
```

表示调用当前类创建实例。与三种常见方法对比：

| 方法 | 第一个自动参数 | 常见调用方式 |
| --- | --- | --- |
| 普通实例方法 | `self`，当前实例 | `event.method()` |
| `@classmethod` | `cls`，当前类 | `VoiceAgentEvent.method()` |
| `@staticmethod` | 没有自动参数 | `VoiceAgentEvent.method()` |

`cls` 和 `self` 都不是 Python 关键字，但属于应当遵守的惯用命名。

### 10.6 `default_factory=list` 为每个实例创建新列表

`2_langchain/L4.py`：

```python
people: list[Person] = Field(
    default_factory=list,
    description="文本中提到的人",
)
```

这里传入的是 `list` 函数对象，没有写 `list()`。Pydantic 会在每次创建模型且没有提供 `people` 时调用它：

```text
创建第一个 Information → 调用 list() → 得到列表 A
创建第二个 Information → 调用 list() → 得到列表 B
```

这样两个实例不会意外共享同一个可变列表。普通 Python 函数也应避免把可变对象直接作为默认值：

```python
def add_item(item, items=[]):  # 不推荐，同一个列表会跨调用复用
    items.append(item)
    return items
```

普通函数通常写成：

```python
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

标准库 `dataclasses` 对应写法是：

```python
from dataclasses import dataclass, field

@dataclass
class Group:
    people: list[str] = field(default_factory=list)
```

核心规则是：需要“每次创建一个新对象”时传工厂函数，不要提前调用并保存同一个可变对象。

### 10.7 一个实例方法可以通过 `self` 调用另一个实例方法

`2_langchain/L9_Semantic_Search_Knowledge_Base.py` 中的教学 Embedding：

```python
def embed_query(self, text: str) -> list[float]:
    return self._embed(text)

def embed_documents(self, texts: list[str]) -> list[list[float]]:
    return [self.embed_query(text) for text in texts]
```

这是合法的普通方法调用。对每段文档文本都会执行：

```text
self.embed_query(text)
    ↓
self._embed(text)
    ↓
list[float]
```

最终列表推导式收集成 `list[list[float]]`。如果 query 和 document 将来需要不同编码规则，也可以让两个公开方法分别调用共同的 `_embed()` 并添加各自处理。

## 11. Python 包、模块、导入和依赖字典

### 11.1 包层级怎么读

```python
from deepagents.backends.langsmith import LangSmithSandbox
```

从左到右：

```text
deepagents               顶层包
└── backends              子包
    └── langsmith         模块或子包
        └── LangSmithSandbox  导入的类
```

这和文件目录结构很像，但最终以 Python 包实际导出的内容为准。

### 11.2 常见导入形式

```python
import json
json.loads(text)
```

导入整个模块，使用时保留模块名。

```python
from pathlib import Path
Path("data.txt")
```

从模块中直接导入对象，使用时不需要写 `pathlib.Path`。

```python
from langchain_openai import ChatOpenAI as ModelClass
```

`as` 可以在当前文件中使用别名。

### 11.3 `from ._common` 与 `from _common` 兼容两种启动方式

RAG Part 1 使用了：

```python
try:
    from ._common import build_rag_chain, build_retriever
except ImportError:  # pragma: no cover
    from _common import build_rag_chain, build_retriever
```

两段导入的对象名称相同，但查找模块的方式不同：

```python
from ._common import ...
```

开头的 `.` 表示“当前包”，也就是从 `3_rag_from_scratch/_common.py` 做相对导入。它适合模块模式：

```bash
.venv/bin/python -m 3_rag_from_scratch.part1_overview
```

这里的 `-m` 是 `module` 的缩写，表示“按照模块名查找，然后把该模块作为主程序执行”。这条命令可以拆成：

```text
.venv/bin/python                         使用项目虚拟环境中的 Python
-m                                       按模块名运行
3_rag_from_scratch                       包名
part1_overview                           包内模块名
3_rag_from_scratch.part1_overview        完整模块名
```

包和模块对应当前文件结构：

```text
3_rag_from_scratch/           包（包含 __init__.py）
├── __init__.py
├── _common.py                3_rag_from_scratch._common 模块
└── part1_overview.py         3_rag_from_scratch.part1_overview 模块
```

使用 `-m` 时写的是点分模块名，不是文件路径，所以没有 `/` 和 `.py`：

```bash
# 模块名
python -m 3_rag_from_scratch.part1_overview

# 文件路径
python 3_rag_from_scratch/part1_overview.py
```

两种方式都会把被执行文件中的 `__name__` 设置为 `"__main__"`，因此都会进入：

```python
if __name__ == "__main__":
    main()
```

关键区别是包上下文：`-m` 运行时 Python 知道当前模块属于 `3_rag_from_scratch`，`__package__` 有包名，所以 `from ._common` 能找到当前包中的 `_common`；直接按文件路径运行时通常没有这个父包上下文。

另一个常见例子是：

```bash
.venv/bin/python -m pip install package_name
```

意思是使用当前这个 `.venv/bin/python` 去运行它环境里的 `pip` 模块，可以避免误用系统中另一套 `pip`。

```python
from _common import ...
```

没有开头的点，是按顶层模块名查找。直接运行文件时，脚本所在目录会进入 Python 的模块搜索路径，因此它能找到同目录的 `_common.py`：

```bash
.venv/bin/python 3_rag_from_scratch/part1_overview.py
```

直接运行单文件时，`part1_overview.py` 没有已知的父包，第一段相对导入会出现类似 `attempted relative import with no known parent package` 的 `ImportError`，随后执行 `except` 中的同目录导入。

之所以把名称完整写两遍，是为了保证无论走哪条导入路径，后续代码都获得完全相同的局部名称：

```text
模块模式 ─→ from ._common ─┐
                            ├─→ build_rag_chain、build_retriever ...
脚本模式 ─→ from _common  ─┘
```

这不是把模块成功导入两次：第一段成功后不会进入 `except`；第一段失败时才执行第二段。`# pragma: no cover` 是覆盖率工具的提示，不影响 Python 的执行逻辑。

这种写法是学习脚本为了同时支持两种入口所做的兼容处理。正式包通常统一要求使用 `python -m ...` 或安装后的命令入口，从而只保留包内相对导入；此外，宽泛捕获 `ImportError` 也可能把 `_common.py` 内部依赖缺失误认为入口问题，排错时要查看最初异常。

### 11.4 函数内部导入是延迟导入

```python
def load_dependencies():
    from langchain_openai import ChatOpenAI
    return {"ChatOpenAI": ChatOpenAI}
```

只有调用 `load_dependencies()` 时才执行导入。学习项目里常用它来：

- 把可选依赖集中处理。
- 导入失败时给出更清楚的错误。
- 避免仅仅导入当前文件就立刻加载所有重依赖。

### 11.5 `deps["Document"]` 是从字典取类

```python
Document = deps["Document"]
document = Document(page_content="hello")
```

执行过程：

```text
deps 字典保存 Document 类
       ↓
按 key 取出类并赋给局部变量 Document
       ↓
调用 Document(...) 创建实例
```

变量可以指向普通值，也可以指向函数或类。

## 12. `Path`、`__file__` 和路径拼接

### 12.1 `__file__` 是当前 Python 文件的路径

项目代码：

```python
PROJECT_ROOT = Path(__file__).resolve().parents[1]
```

逐步拆开：

```python
current_file = Path(__file__)       # 当前 .py 文件路径
absolute_file = current_file.resolve()  # 转为规范的绝对路径
project_root = absolute_file.parents[1] # 取上两级目录
```

假设文件是：

```text
/home/wangfei/code/andrew/2_langchain/L7.py
```

那么：

```text
parents[0] = /home/wangfei/code/andrew/2_langchain
parents[1] = /home/wangfei/code/andrew
```

`parents[1]` 是第二个父目录，因为 Python 索引从 `0` 开始。

### 12.2 `Path / "目录"` 是 Path 专用的运算符重载

```python
VENV_SITE_PACKAGES = (
    PROJECT_ROOT
    / ".venv"
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)
```

如果 `PROJECT_ROOT` 是 `Path` 对象，`/` 被 `pathlib` 重载成路径拼接。它不是所有字符串都能使用的通用拼接语法：

```python
Path("/tmp") / "data.txt"  # 正确，得到 Path
"/tmp" / "data.txt"        # TypeError
"/tmp" + "/data.txt"       # 字符串拼接，但不推荐手工处理路径
```

跨系统路径优先使用 `Path`。

### 12.3 `sys.path.insert(0, path)` 调整模块搜索顺序

```python
if VENV_SITE_PACKAGES.exists():
    sys.path.insert(0, str(VENV_SITE_PACKAGES))
```

- `exists()` 检查路径是否存在。
- `str(...)` 把 `Path` 转成字符串。
- `insert(0, ...)` 把路径插到列表最前面。
- Python 导入模块时会优先搜索这个目录。

这是运行环境处理，不是安装依赖本身。

## 13. 异步语法与同步/异步方法边界

### 13.1 `async def` 定义异步函数

```python
async def fetch_result():
    ...
```

调用普通异步函数时，通常先得到协程对象，而不是立即得到最终结果：

```python
coroutine = fetch_result()
result = await coroutine
```

`await` 表示暂停当前协程，等待异步操作完成，同时把事件循环的执行机会交给其他任务。

### 13.2 `asyncio.gather()` 并发等待多个异步任务

历史代码：

```python
(
    invoke_result,
    batch_result,
    stream_result,
    another_result,
) = await asyncio.gather(
    invoke_task,
    batch_task,
    stream_task,
    another_task,
)
```

这里真正负责并发调度和统一等待的是 `asyncio.gather(...)`。它会按照传入 awaitable 的顺序返回结果，而不是按照完成先后顺序排列：

```text
第 1 个任务的结果 -> invoke_result
第 2 个任务的结果 -> batch_result
第 3 个任务的结果 -> stream_result
第 4 个任务的结果 -> another_result
```

单纯写一个字典：

```python
return {
    "a": already_finished_a,
    "b": already_finished_b,
}
```

只是组装结果，不会自动产生并发。

### 13.3 `AsyncIterator[bytes]` 是异步迭代器类型

```python
async def fake_audio_stream(text: str) -> AsyncIterator[bytes]:
    for word in text.split():
        await asyncio.sleep(0)
        yield word.encode() + b" "
```

这段函数包含 `yield`，所以它是异步生成器：

- 输入是字符串。
- 每次产生一个 `bytes` 数据块。
- 不会一次性把所有结果放进列表返回。

### 13.4 `yield` 产出一个值并暂停函数

```python
yield event
```

含义是：

1. 把当前 `event` 交给调用方。
2. 暂停在这里。
3. 调用方下一次继续迭代时，从下一行恢复执行。

这与 `return` 不同：`return` 会结束函数，普通情况下只返回一次。

### 13.5 `async for` 遍历异步数据流

```python
async for audio_chunk in audio_stream:
    text = audio_chunk.decode(errors="ignore")
    yield VoiceAgentEvent.stt_chunk(text)
```

`async for` 每次异步等待下一项，适合网络流、音频流、模型流式输出等不能一次性得到全部数据的场景。

### 13.6 `str` 与 `bytes`

```python
encoded = word.encode()   # str -> bytes
decoded = encoded.decode() # bytes -> str
b" "                     # bytes 字面量
```

文本处理通常使用 `str`，网络、文件或音频等原始二进制数据经常使用 `bytes`。

### 13.7 流式增量代码怎么读

历史代码：

```python
delta = content[len(seen):] if content.startswith(seen) else content
seen = content
```

含义是：

1. 如果新 `content` 以前面已经见过的 `seen` 开头，只取后面新增部分。
2. 否则把完整 `content` 当作本次数据。
3. 最后更新 `seen`。

这里组合了字符串切片、条件表达式和变量赋值。

### 13.8 同步方法不能把异步方法的协程当成结果

是否异步由定义时的 `async def` 决定：

```python
def embed_query(self, text: str) -> list[float]:
    return self._embed(text)           # 同步，直接得到向量

async def aembed_query(self, text: str) -> list[float]:
    ...                                # 异步，调用后先得到协程
```

因此下面的同步实现有问题：

```python
def embed_documents(self, texts: list[str]) -> list[list[float]]:
    return [self.aembed_query(text) for text in texts]
```

列表中装入的是协程对象，不是 `list[float]`。同步版本应调用同步方法：

```python
def embed_documents(self, texts: list[str]) -> list[list[float]]:
    return [self.embed_query(text) for text in texts]
```

异步批量版本才使用 `await`：

```python
async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
    return await asyncio.gather(
        *(self.aembed_query(text) for text in texts)
    )
```

方法名开头的 `a` 只是常见命名约定；真正的判断标准仍然是它是否由 `async def` 定义。

## 14. `with`、`@contextmanager`、资源管理和回调注册

### 14.1 `with` 使用上下文管理器自动收尾

项目历史代码：

```python
with database_connection(database_path) as conn:
    conn.executescript("""
        CREATE TABLE Genre (...);
    """)
    conn.commit()
```

`with` 会在进入代码块时获取资源，并在离开时执行清理。即使代码块中发生异常，也会调用上下文管理器的退出逻辑。

数据库连接、文件和锁都经常使用 `with`：

```python
with open("data.txt", encoding="utf-8") as file:
    content = file.read()
```

### 14.2 `@contextmanager`、`yield` 和 `finally`

`2_langchain/L11_SQL_Agent.py` 使用生成器函数创建上下文管理器：

```python
from contextlib import contextmanager

@contextmanager
def database_connection(database_path, *, read_only=False):
    conn = sqlite3.connect(database_path)
    try:
        yield conn
    finally:
        conn.close()
```

调用：

```python
with database_connection(database_path) as conn:
    conn.execute("SELECT 1")
```

执行顺序是：

```text
运行 yield 之前的代码，创建 conn
    ↓
yield conn，把 conn 交给 as conn
    ↓
执行 with 代码块
    ↓
离开 with 后，从 yield 下一行继续
    ↓
执行 finally，关闭连接
```

`yield` 在这里既交出资源，也标记“进入”和“退出”两个阶段的分界。`finally` 保证即使 `with` 代码块抛出异常，也会执行 `conn.close()`。

普通包含 `yield` 的函数是生成器；加上 `@contextmanager` 后，`contextlib` 会把这种“前置处理 → yield → 后置处理”的生成器协议适配成 `with` 所需的上下文管理器协议。

### 14.3 三引号也可以表示多行普通字符串

```python
sql = """
CREATE TABLE Genre (...);
INSERT INTO Genre VALUES (...);
"""
```

当它被赋值给变量或作为函数参数时，就是普通的多行字符串，不是文档字符串。

### 14.4 注册函数时不要提前调用

```python
atexit.register(database_path.unlink, missing_ok=True)
```

这里把方法对象 `database_path.unlink` 交给 `atexit.register`，没有写括号，因此此刻不会删除文件。程序退出时，注册器才会执行近似下面的调用：

```python
database_path.unlink(missing_ok=True)
```

对比：

```python
register(database_path.unlink)   # 传递函数或方法
register(database_path.unlink()) # 先执行，再传递返回值
```

## 15. 终端和 Python REPL 不能混用

### 15.1 看到 `>>>` 时，当前在 Python 交互环境

```text
>>>
```

这里应当输入 Python 代码：

```python
print("hello")
1 + 2
```

下面这些是 shell 命令，不能直接输入 Python REPL：

```bash
source .venv/bin/activate
.venv/bin/python 2_langchain/L7.py
```

否则会出现 `SyntaxError` 或 `IndentationError`，因为 Python 在尝试把 shell 命令解析成 Python 语法。

### 15.2 正确运行脚本

先离开 REPL：

```python
exit()
```

回到类似下面的终端提示符：

```text
wangfei@host:~/code/andrew$
```

再执行：

```bash
.venv/bin/python 2_langchain/L7.py
```

### 15.3 `venv` 是虚拟环境工具，不是 Python 语法

虚拟环境为项目提供独立的 Python 解释器和依赖目录，避免不同项目之间的包版本互相影响。

```bash
python3 -m venv .venv
source .venv/bin/activate
```

项目在新电脑初始化时，应先参考 `docs/setup-new-machine.md`。

## 16. Python `dict/list` 与 JSON 的区别

### 16.1 Python 对象还不是 JSON 字符串

```python
result = {
    "query": "什么是 RAG？",
    "documents": [],
    "answerable": True,
    "error": None,
}
```

这是 Python 字典，其中还包含列表、布尔值和 `None`。

序列化之后才是 JSON：

```python
json_text = json.dumps(result, ensure_ascii=False)
```

JSON 形式类似：

```json
{
  "query": "什么是 RAG？",
  "documents": [],
  "answerable": true,
  "error": null
}
```

差异：

| Python | JSON |
| --- | --- |
| `dict` | object |
| `list` | array |
| `True` / `False` | `true` / `false` |
| `None` | `null` |

Web 框架常常会自动完成序列化，所以业务代码可以直接返回字典或列表。

### 16.2 `json.loads()` 把 JSON 字符串解析成 Python 对象

```python
raw_arguments = '{"location": "Boston"}'
arguments = json.loads(raw_arguments)
```

结果：

```python
{"location": "Boston"}
```

历史代码先用 `isinstance(raw_arguments, str)` 判断是否需要解析，是为了兼容“参数可能已经是字典”的情况。

### 16.3 `dict(row)` 是 Python 数据结构转换

```python
result = dict(row)
```

它尝试把 `row` 转成 Python 字典。是否能转换取决于 `row` 是否提供键值对结构；例如 `sqlite3.Row` 支持这种转换。

## 17. 同一个符号在不同位置可能有不同含义

### 17.1 常见符号对照表

| 符号 | 示例 | 含义 |
| --- | --- | --- |
| `[]` | `[a, b]` | 创建列表 |
| `[]` | `docs[0]` | 索引取值 |
| `[]` | `text[:10]` | 切片 |
| `[]` | `list[str]` | 泛型类型标注 |
| `()` | `function()` | 调用函数 |
| `()` | `(a + b) * c` | 控制运算顺序或多行分组 |
| `()` | `(a, b)` | 创建元组，关键是逗号 |
| `{}` | `{"a": 1}` | 创建字典 |
| `{}` | `{1, 2}` | 创建集合 |
| `:` | `name: str` | 类型标注 |
| `:` | `{"key": value}` | 分隔字典 key 和 value |
| `:` | `values[1:3]` | 切片分隔符 |
| `:` | `if ok:` | 代码块开始 |
| `*` | `def f(*, key)` | 后面是仅限关键字参数 |
| `*` | `def f(*args)` | 收集位置参数 |
| `*` | `f(*values)` | 拆开序列作为位置参数 |
| `**` | `def f(**kwargs)` | 收集关键字参数 |
| `**` | `f(**config)` | 拆开字典作为关键字参数 |
| `|` | `str | None` | 联合类型 |
| `|` | `prompt | model` | 对象重载后的管道运算 |
| `/` | `10 / 2` | 数值除法 |
| `/` | `Path("a") / "b"` | `Path` 重载后的路径拼接 |

### 17.2 `prompt | model | parser` 为什么能工作

`|` 本来是 Python 运算符。LangChain 的对象实现了对应的运算符方法，因此：

```python
chain = prompt | model | parser
```

会被这些对象解释成“把多个步骤组成管道”。这仍然是合法的 Python 运算符语法，但“管道”的业务含义来自 LangChain 的运算符重载。

同一个 `|` 出现在：

```python
str | None
```

时，则由 Python 类型系统解释成联合类型，含义完全不同。

## 18. 历史提问速查

```text
"""说明文字"""
    函数、类或模块第一条字符串语句时，是 docstring

value_if_true if condition else value_if_false
    Python 条件表达式

isinstance(value, str)
    判断运行时类型

hasattr(obj, "method") / getattr(obj, "field", default)
    检查属性 / 带默认值读取属性

list[dict[str, object]] = []
    创建空列表，并标注计划存放“字符串 key、任意对象 value”的字典

tuple[str, bytes]
    固定两个位置、两种类型的元组标注，不是 Map

Embeddings | None = None
    参数类型可为 Embeddings 或 None，默认值是 None

[expression for item in values if condition]
    列表推导式：遍历、转换、可选过滤

[item for sublist in groups for item in sublist]
    双层循环压平嵌套列表

def f(value, *, option=default)
    * 后面的参数必须按名字传递

def f(*args, **kwargs)
    收集额外位置参数和关键字参数

f(**config)
    把字典拆成关键字参数

lambda value: expression
    匿名函数；lambda _: value 表示接收但忽略参数

@dataclass(frozen=True)
    自动生成数据类常用方法，并限制实例字段修改

async def / await / asyncio.gather
    定义异步函数 / 等待 / 并发等待多个任务

yield / async for / AsyncIterator[T]
    逐项产出 / 异步遍历 / 异步迭代器类型

Path(__file__).resolve().parents[1]
    当前文件绝对路径的第二级父目录

for rank, (document, score) in enumerate(..., start=1)
    带序号遍历，并进行两层元组拆包

zip(left, right)
    按位置配对，以较短一侧为准

scores.items()
    返回动态字典视图；遍历时每项是 (key, value) 二元组

sorted(scores.items(), key=lambda item: item[1], reverse=True)
    按 value 从大到小生成新的二元组列表，不修改原字典

mapping.get(key, default)
    key 不存在时返回默认值，不修改字典

mapping.setdefault(key, default)
    key 不存在时写入并返回默认值，存在时保留旧值

mapping.pop(key, default)
    取出并删除 key；不存在时返回默认值

Python dict
    是保持插入顺序的 KV 映射；不关心顺序时仍然使用 dict

set / map()
    set 保存不重复元素；map() 是逐项转换函数，都不是 KV Map

seen: set[str] = set() / value in seen / seen.add(value)
    创建空集合 / 判断成员 / 添加成员，常与列表配合做保序去重

list[list[Document]]
    二维列表；外层通常对应多条查询，内层对应每条查询的一组 Document

values[:4]
    取得序列前四项并返回新对象，不修改原序列

text.splitlines() / text.casefold() / re.sub(...)
    按行拆分 / 大小写规范化 / 正则替换

candidates.extend(expression for item in items)
    逐项消费生成器表达式，并把结果追加到原列表

@classmethod / cls
    定义绑定到类的方法；调用时 Python 自动传入当前类

default_factory=list
    每次创建实例时调用 list()，避免多个实例共享同一个可变默认对象

@contextmanager + yield + finally
    用生成器函数描述获取资源、交出资源和退出清理三个阶段

def embed_query(...) / async def aembed_query(...)
    前者直接返回结果；后者调用后先返回协程，必须 await 才得到结果

Python REPL 的 >>>
    只能输入 Python；source 和脚本启动命令应在 shell 中执行
```
