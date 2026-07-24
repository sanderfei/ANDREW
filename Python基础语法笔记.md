# Python 基础语法笔记

这份笔记汇总在 `andrew` 项目当前会话和其他历史会话中问过的 Python 基础语法问题。重复问题已经合并，示例优先使用项目里的真实代码。

涉及 LangChain 专有 API 的内容放在根目录的 `LangChain基础语法笔记.md`；本文件重点解释这些代码背后的 Python 语法、类型和执行规则。

## 阅读导航

| 想复习的问题 | 对应章节 |
| --- | --- |
| `Iterable`、`Sequence`、`tuple`、`object`、`Literal`、函数参数类型标注 | 第 1、3 节 |
| `zip()`、`enumerate()`、变量拆包 | 第 2、8 节 |
| 列表、字典、元组、`set`、`frozenset`、嵌套列表、索引、切片、`range()` 分批 | 第 4、5 节 |
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
Iterable（只承诺能够逐项遍历）
└── Sequence（进一步承诺按位置有序、可取长度、可按下标访问）
    ├── list
    ├── tuple
    ├── str
    └── range

generator       通常只保证 Iterable，不保证索引和长度
set             属于 Iterable，但不是 Sequence，因为不按位置索引
dict            虽然保留插入顺序，但按 key 而不是按位置索引，所以不是 Sequence
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

可以用操作能力快速记忆：

```python
# Iterable 只承诺这种操作
for item in values:
    ...

# Sequence 还承诺这些操作
len(values)
values[0]
values[1:3]
```

`Sequence` 也不代表一定可以修改。例如 `tuple` 和 `str` 都是 Sequence，但不能执行
按位置赋值；`list` 则是可修改的 `MutableSequence`：

```python
text = "abc"
text[0]          # "a"，可以读取
# text[0] = "A"  # 报错，str 不可修改

items = ["a", "b"]
items[0] = "A"   # 可以，list 可修改
```

当前索引代码形成了一个直接对照：

```python
def _delete_ids(self, store, ids: Iterable[str]) -> int:
    ids_list = list(ids)
```

`_delete_ids()` 对传入的 `ids` 只要求能够遍历，所以列表、元组、生成器都可以；进入
函数后再统一转换为列表。

```python
def _batched(values: list[str] | list[Document], size: int = 100):
    for start in range(0, len(values), size):
        yield values[start : start + size]
```

`_batched()` 需要 `len(values)` 和列表切片，因此不能只根据 `Iterable` 的最低能力来
编写。概念上，它要求的是“有长度并且支持按位置切片”的 Sequence 能力；当前代码把
参数进一步限制成了具体的 `list`。

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

### 3.7 多个函数参数要分别读取各自的类型标注

`4_rag_knowledge_base_service/indexer.py`：

```python
def _delete_ids(self, store, ids: Iterable[str]) -> int:
    ids_list = list(ids)
    for batch in self._batched(ids_list):
        store.delete(ids=batch)
    return len(ids_list)
```

函数参数之间使用逗号分隔，每个参数的类型标注只属于它自己：

```text
self                 第 1 个参数，没有显式类型标注
store                第 2 个参数，没有显式类型标注
ids: Iterable[str]   第 3 个参数，标注为 Iterable[str]
-> int               函数返回值标注为 int
```

所以 `store` 和 `ids` 不是同一种类型，`ids` 后面的 `: Iterable[str]` 不会向左作用到
`store`。下面这个简单例子也是同样的规则：

```python
def example(left, right: str) -> int:
    ...
```

它只表示 `right` 应该是 `str`；`left` 没有类型标注。

沿着项目真实调用位置看：

```python
store = self._store()
deleted_chunks = self._delete_ids(store, delete_ids)
```

两者的实际形态是：

| 参数 | 当前项目传入的对象 |
| --- | --- |
| `store` | `_store()` 创建或连接的 `langchain_chroma.Chroma` 对象 |
| `ids` | `delete_ids`，当前是 `list[str]` |

`Iterable[str]` 是能力约束，不是一种与 `Chroma` 相同的实际容器。它表示遍历 `ids`
时，每次应当得到一个字符串：

```python
for chunk_id in ids:
    print(chunk_id)  # chunk_id 应当是 str
```

因此列表、元组和生成器都可以满足这个参数约定：

```python
["id-1", "id-2"]                 # list[str]
("id-1", "id-2")                 # tuple[str, str]
(value for value in ["id-1"])    # 产生 str 的生成器
```

函数内部先统一转换：

```python
ids_list = list(ids)
```

得到 `list[str]`，随后 `_batched()` 每次产生一小批 ID，最终调用的是 Chroma 对象的：

```python
store.delete(ids=batch)
```

这里还要区分两个完全不同的 `ids`：

```text
_delete_ids(..., ids=某个可迭代对象)
                   ↑ 函数参数名

store.delete(ids=batch)
             ↑ Chroma.delete() 的关键字参数名
```

它们名字相同是因为都表达“文档 ID”，但处在两个不同函数调用层级。

### 3.8 参数可以不标注类型，但对象的运行时类型并没有隐藏

纯 Python 函数允许省略所有参数和返回值的类型标注：

```python
def process(left, right):
    return left + right
```

也允许只标注一部分：

```python
def process(left, right: str):
    return str(left) + right
```

还可以全部标注：

```python
def process(left: str, right: str) -> str:
    return left + right
```

这三种写法都是合法 Python。位置参数、关键字参数、`*args` 和 `**kwargs` 在语法层面
也都可以不写类型标注。

不过，“没有类型标注”不等于“对象没有类型”或“类型被隐藏”。Python 的变量名保存
的是对象引用，真正传入的每个对象始终有自己的运行时类型：

```python
def show(value):
    print(type(value))

show(10)       # <class 'int'>
show("hello")  # <class 'str'>
show([])       # <class 'list'>
```

同一个参数名可以在不同调用中指向不同类型的对象：

```text
第一次调用：value -> int 对象
第二次调用：value -> str 对象
第三次调用：value -> list 对象
```

所以更准确的表述是：

> 参数没有声明固定类型，但传入对象仍然具有具体运行时类型。

#### Python 根据实际操作判断对象能不能用

项目方法：

```python
def _delete_ids(self, store, ids: Iterable[str]) -> int:
    ...
    store.delete(ids=batch)
```

虽然 `store` 没有标注为 `Chroma`，但代码要求它在运行时至少提供可调用的
`.delete(ids=...)` 方法。只要对象提供所需能力，这行代码就能继续执行，这种风格通常
称为“鸭子类型”：

```text
不先检查它名义上属于哪个类
    ↓
直接使用当前逻辑需要的方法
    ↓
方法存在且调用兼容，就可以工作
```

如果错误地传入整数：

```python
self._delete_ids(123, ["id-1"])
```

函数调用时不会因为缺少类型标注而立即拦截，但运行到：

```python
store.delete(ids=batch)
```

就会抛出 `AttributeError`，因为 `int` 没有 `.delete()` 方法。

如果 `ids` 传入不可迭代的整数：

```python
self._delete_ids(store, 123)
```

即使源代码标注了 `ids: Iterable[str]`，普通 Python 默认也不会在进入函数时自动校验；
运行到 `list(ids)` 时才会因为整数不可迭代而抛出 `TypeError`。

#### 无标注、`Any` 和明确标注的区别

```python
def first(store):            # 没写明预期类型
    ...

def second(store: Any):      # 明确告诉类型检查器跳过严格检查
    ...

def third(store: Chroma):    # 明确说明预期是 Chroma
    ...
```

| 写法 | 代码表达的意思 | Python 是否自动运行时校验 |
| --- | --- | --- |
| `store` | 没有提供类型信息 | 否 |
| `store: Any` | 明确放弃该值的大部分静态检查 | 否 |
| `store: Chroma` | 预期传入 `Chroma`，便于阅读和静态检查 | 默认仍然不校验 |

因此，类型标注主要改善编辑器补全、静态检查和代码可读性，而不是让 Python 参数
获得一个强制的固定类型。

#### 语法允许省略，不代表所有框架场景都适合省略

普通内部辅助函数可以不写标注，但有些框架会主动读取标注，例如 FastAPI、Pydantic
可能使用它们进行请求解析、数据校验或接口文档生成。在这类位置省略标注，可能改变
框架行为。

当前 `_delete_ids()` 是普通内部辅助方法，`store` 的实际对象来源又可以沿着：

```python
store = self._store()
```

推断为 Chroma，所以省略标注不会阻止代码运行，只是让编辑器和读代码的人少了一条
直接的类型信息。

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

### 4.14 `range(start, stop, step)`、列表分片与分批生成器

`4_rag_knowledge_base_service/indexer.py`：

```python
@staticmethod
def _batched(values: list[str] | list[Document], size: int = 100):
    for start in range(0, len(values), size):
        yield values[start : start + size]
```

它的用途是把一个大列表按 `size` 个元素一批，逐批交给调用方。

#### `range(...)` 返回什么类型

```python
numbers = range(0, 10, 2)

print(type(numbers))
# <class 'range'>
```

`range` 不是 Python 遍历关键字。下面这行代码应当拆成三部分：

```python
for start in range(0, 10, 2):
    ...
```

```text
for、in              Python 关键字，负责循环语法
start                每轮接收元素的变量名
range(0, 10, 2)      普通调用表达式，返回一个 range 对象
```

`for` 并不依赖 `range`，它可以遍历任何 Iterable：

```python
for value in ["a", "b"]:       # 遍历 list
    ...

for value in ("a", "b"):       # 遍历 tuple
    ...

for value in range(0, 10, 2):  # 遍历 range
    ...
```

`range` 是内置类型名，因此技术上甚至可以被重新赋值覆盖；`for`、`in` 是关键字，
不能被当成普通变量名。实际代码不要覆盖 `range`：

```python
range = "错误示例"
# range(3)  # 此时会报错，因为 range 名称已经指向字符串
```

所以 `range(...)` 返回的是 Python 内置的 `range` 对象，不是 `list`，也不是生成器。
它是一个不可修改的 Sequence，支持：

```python
len(numbers)   # 5
numbers[0]     # 0
numbers[2]     # 4
numbers[1:4]   # range(2, 8, 2)，切片结果仍然是 range
```

它保存自己的生成规则：

```python
numbers.start  # 0
numbers.stop   # 10
numbers.step   # 2
```

并不会先创建：

```python
[0, 2, 4, 6, 8]
```

需要具体列表时才显式转换：

```python
list(numbers)
# [0, 2, 4, 6, 8]
```

因此，即使范围非常大，`range` 对象本身也只需要记录起点、终点和步长，而不是保存
全部整数：

```python
large_range = range(0, 1_000_000_000)
```

`for` 遍历时会从 `range` 对象取得迭代器，再逐个计算下一项：

```python
iterator = iter(numbers)

print(type(iterator))
# <class 'range_iterator'>
```

所以要区分：

| 表达式 | 类型 |
| --- | --- |
| `range(0, 10, 2)` | `range`，不可修改的 Sequence |
| `iter(range(0, 10, 2))` | `range_iterator`，迭代器 |
| `list(range(0, 10, 2))` | `list[int]` |

#### `range(0, len(values), size)` 的三个参数

```python
range(start, stop, step)
```

| 参数 | 当前值 | 含义 |
| --- | --- | --- |
| `start` | `0` | 第一个循环值，从 0 开始 |
| `stop` | `len(values)` | 到这里停止，但不包含这个值 |
| `step` | `size` | 每次给循环变量增加多少 |

所以：

```python
for start in range(0, len(values), size):
```

确实可以近似理解为其他语言中的：

```text
for (start = 0; start < len(values); start += size)
```

例如列表有 250 项、`size=100`：

```python
list(range(0, 250, 100))
# [0, 100, 200]
```

`start` 不会取到 300，因为它已经超过停止值 250；也不会取到 250，因为 `range()` 的
`stop` 不包含在结果中。

#### `values[start : start + size]` 是列表切片

列表切片的完整形式是：

```python
values[开始索引 : 结束索引]
```

开始索引包含，结束索引不包含。假设：

```python
values = list(range(250))
size = 100
```

每轮结果是：

| `start` | 切片 | 实际索引 | 本批数量 |
| ---: | --- | --- | ---: |
| `0` | `values[0:100]` | 0～99 | 100 |
| `100` | `values[100:200]` | 100～199 | 100 |
| `200` | `values[200:300]` | 200～249 | 50 |

最后一次的 `start + size` 是 300，超过列表长度 250，但列表切片不会报错，只会取得
剩余元素。

#### `yield` 每次产出一批并暂停

```python
yield values[start : start + size]
```

执行过程是：

```text
切出当前小列表
    ↓
yield 把小列表交给调用方
    ↓
_batched() 暂停
    ↓
调用方请求下一批
    ↓
恢复 for 循环，start 增加 size
```

用普通控制流程近似展开：

```python
start = 0

while start < len(values):
    batch = values[start : start + size]
    yield batch
    start += size
```

因为函数中出现了 `yield`，调用 `_batched()` 时得到的是生成器，不会立刻把所有批次
都创建出来：

```python
batches = IncrementalIndexer._batched(["a", "b", "c", "d", "e"], size=2)

print(type(batches))
# <class 'generator'>
```

逐项遍历时，每一项才是一个一维列表：

```python
for batch in batches:
    print(batch)

# ["a", "b"]
# ["c", "d"]
# ["e"]
```

如果显式收集为列表：

```python
all_batches = list(
    IncrementalIndexer._batched(["a", "b", "c", "d", "e"], size=2)
)

# [["a", "b"], ["c", "d"], ["e"]]
```

这时 `all_batches` 才是二维列表：

```text
外层 list：所有批次
内层 list：每一个批次中的元素
```

因此要区分：

| 表达式 | 数据形态 |
| --- | --- |
| `_batched(values)` | 生成器对象 |
| 每次 `yield` 的值 | 一个一维小列表 |
| `list(_batched(values))` | 由多个小列表组成的二维列表 |

项目没有先收集成二维列表，而是直接逐批消费：

```python
for batch in self._batched(ids_list):
    store.delete(ids=batch)
```

添加 Chroma 文档时，则分别切分 `documents` 和 `chunk_ids`，再用 `zip()` 对齐同一批：

```python
for documents, ids in zip(
    self._batched(source.documents),
    self._batched(source.chunk_ids),
):
    store.add_documents(documents=documents, ids=ids)
```

默认 `size=100`，所以每次最多向 Chroma 提交 100 个文档及其对应的 100 个 ID；最后
一批可以少于 100 个。

`@staticmethod` 表示这个辅助方法不使用实例状态，因此参数中没有 `self`。当前代码
始终使用正整数 100；如果把 `size` 设置成 0，`range()` 会抛出 `ValueError`。

### 4.15 `set.difference()` 与不可修改的 `frozenset`

当前项目中：

```python
ANSWERABILITY_STOP_TOKENS = frozenset(
    {
        "知识",
        "识库",
        "文档",
        "问题",
        "什么",
    }
)

return lexical_tokens(text).difference(ANSWERABILITY_STOP_TOKENS)
```

#### `set.difference()` 计算集合差集

```python
left.difference(right)
```

读作：

> 返回只在 `left` 中、但不在 `right` 中的元素。

例如：

```python
tokens = {"知识", "识库", "使用", "向量"}
stop_tokens = frozenset({"知识", "识库"})

result = tokens.difference(stop_tokens)

print(result)
# {"使用", "向量"}
```

它不会修改原集合：

```python
print(tokens)
# {"知识", "识库", "使用", "向量"}
```

下面两种写法在这里等价：

```python
tokens.difference(stop_tokens)
tokens - stop_tokens
```

如果需要直接修改普通 `set`，对应方法是 `difference_update()`；但当前项目需要保留
原集合，因此使用返回新集合的 `difference()`。

#### `frozenset` 是不可修改的集合

是的，`frozenset` 可以理解为“冻结的 `set`”：

```python
normal_set = {"知识", "文档"}
frozen_set = frozenset({"知识", "文档"})
```

两者都支持：

```python
"知识" in frozen_set
len(frozen_set)
frozen_set.difference({"知识"})
frozen_set.intersection({"知识"})
```

但是只有普通 `set` 支持原地修改：

```python
normal_set.add("问题")       # 可以
normal_set.remove("知识")    # 可以

frozen_set.add("问题")       # 报错：frozenset 没有 add()
frozen_set.remove("知识")    # 报错：frozenset 没有 remove()
```

当前项目把停用词定义成 `frozenset`，表示这组模块级配置只供查询，不应该在业务运行
过程中被意外增加或删除。

返回值类型取决于调用 `difference()` 的左侧对象：

```python
set({"a", "b"}).difference(frozenset({"a"}))
# {"b"}，类型是 set

frozenset({"a", "b"}).difference({"a"})
# frozenset({"b"})，类型是 frozenset
```

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

### 5.8 `re.compile()`、正则 Pattern 对象与全大写常量名

项目代码：

```python
ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9_./-]+")
CJK_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
```

这两行既和正则表达式有关，也使用了常量风格的变量名，二者并不冲突：

```text
正则字符串
    ↓ re.compile(...)
re.Pattern 对象
    ↓ 赋值给模块级全大写变量
可复用的正则模式常量
```

`re.compile(...)` 现在只是创建正则模式对象，还没有拿具体文本执行匹配：

```python
pattern = re.compile(r"[a-z]+")

print(type(pattern))
# <class 're.Pattern'>
```

真正处理文本发生在调用模式对象的方法时：

```python
matches = pattern.findall("rag 2026 python")
# ["rag", "python"]
```

因此项目代码的执行阶段是：

```python
# 模块被导入时执行一次：创建 Pattern 对象
ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9_./-]+")
CJK_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")

# lexical_tokens() 每次被调用时：使用 Pattern 对象处理具体文本
tokens = set(ASCII_TOKEN_PATTERN.findall(normalized))
chinese_runs = CJK_RUN_PATTERN.findall(normalized)
```

两种写法的效果可以理解为相同：

```python
# 直接把正则字符串传给 re.findall()
matches = re.findall(r"[a-z]+", text)

# 先编译并保存，再调用 Pattern.findall()
WORD_PATTERN = re.compile(r"[a-z]+")
matches = WORD_PATTERN.findall(text)
```

当同一个模式会被多次使用时，第二种写法能集中定义规则，也能直接通过变量名说明
规则的用途。

#### `ASCII_TOKEN_PATTERN` 的规则

```python
r"[a-z0-9_./-]+"
```

| 正则片段 | 含义 |
| --- | --- |
| `r"..."` | Python 原始字符串，便于书写正则中的反斜杠 |
| `[...]` | 字符集合，其中任意一个字符都可以匹配 |
| `a-z` | 一个小写英文字母 |
| `0-9` | 一个数字 |
| `_` | 下划线 |
| `.` | 点；在字符集合内部表示普通点字符 |
| `/` | 斜杠 |
| `-` | 连字符；放在字符集合末尾时表示普通连字符 |
| `+` | 前面的字符集合连续出现一次或多次 |

项目会先执行：

```python
normalized = text.lower()
```

所以输入中的大写英文会先变成小写，再由该模式匹配。

#### `CJK_RUN_PATTERN` 的规则

```python
r"[\u4e00-\u9fff]+"
```

| 正则片段 | 含义 |
| --- | --- |
| `\u4e00-\u9fff` | 常用 CJK 汉字的 Unicode 范围 |
| `[...]` | 匹配范围中的一个汉字 |
| `+` | 匹配一个或多个连续汉字 |

例如：

```python
text = "RAG_service/v1 用中文检索-2026！"
normalized = text.lower()

ASCII_TOKEN_PATTERN.findall(normalized)
# ["rag_service/v1", "-2026"]

CJK_RUN_PATTERN.findall(normalized)
# ["用中文检索"]
```

这两个模式分别提取英文/数字类词项和连续中文片段。项目随后还会把连续中文片段
切成二字词：

```python
"用中文检索"
→ "用中", "中文", "文检", "检索"
```

变量名写成全大写：

```python
ASCII_TOKEN_PATTERN
CJK_RUN_PATTERN
```

表示开发者约定“这个模块级变量定义后按常量使用，不要在业务过程中重新赋值”。
但 Python 没有真正的常量关键字，下面的代码在语法上仍然允许：

```python
ASCII_TOKEN_PATTERN = "changed"
```

因此“常量”描述的是变量的使用约定；`re.Pattern` 描述的是变量当前保存的对象
类型。

### 5.9 `lexical_tokens()`：英文整段提取，中文相邻双字切分

项目中的函数：

```python
def lexical_tokens(text: str) -> set[str]:
    normalized = text.lower()
    tokens = set(ASCII_TOKEN_PATTERN.findall(normalized))
    for run in CJK_RUN_PATTERN.findall(normalized):
        tokens.update(run[index : index + 2] for index in range(len(run) - 1))
    return tokens
```

可以读作：

> 接收一个字符串 `text`，先统一转成小写；提取英文、数字和路径类词项；
> 再把每段连续中文按相邻两个字切分；用集合去重后返回。

以这段文本为例：

```python
text = "RAG_service/v1 使用知识库知识"
```

每一步的值和类型是：

```python
normalized = text.lower()
# "rag_service/v1 使用知识库知识"
# 类型：str

ASCII_TOKEN_PATTERN.findall(normalized)
# ["rag_service/v1"]
# 类型：list[str]

tokens = set(ASCII_TOKEN_PATTERN.findall(normalized))
# {"rag_service/v1"}
# 类型：set[str]

CJK_RUN_PATTERN.findall(normalized)
# ["使用知识库知识"]
# 类型：list[str]
```

这里的 `run` 是 `for` 循环变量，不是 Python 关键字：

```python
for run in CJK_RUN_PATTERN.findall(normalized):
    ...
```

可以读作：

> 遍历找到的每一段连续中文，每次把当前中文字符串暂时赋值给变量 `run`。

例如：

```python
normalized = "中文 RAG 知识库"
CJK_RUN_PATTERN.findall(normalized)
# ["中文", "知识库"]

for run in CJK_RUN_PATTERN.findall(normalized):
    print(run, type(run))

# 第一轮：run == "中文"，类型是 str
# 第二轮：run == "知识库"，类型是 str
```

变量名 `run` 在这里表示“一段连续出现的字符”（a run of characters）。它只是开发者
选择的普通变量名，也可以改写成更直观的 `chinese_text`：

```python
for chinese_text in CJK_RUN_PATTERN.findall(normalized):
    tokens.update(
        chinese_text[index : index + 2]
        for index in range(len(chinese_text) - 1)
    )
```

对于连续中文 `"使用知识库知识"`：

```python
len(run)
# 7

range(len(run) - 1)
# 相当于依次产生 0、1、2、3、4、5

run[0:2]  # "使用"
run[1:3]  # "用知"
run[2:4]  # "知识"
run[3:5]  # "识库"
run[4:6]  # "库知"
run[5:7]  # "知识"
```

这里是一个“宽度为 2、每次向右移动 1 个字符”的滑动窗口。生成器表达式：

```python
run[index : index + 2] for index in range(len(run) - 1)
```

展开成普通 Python 循环就是：

```python
two_character_tokens = []
for index in range(len(run) - 1):
    token = run[index : index + 2]
    two_character_tokens.append(token)

tokens.update(two_character_tokens)
```

`set.update(...)` 会把多个元素加入原集合并自动去重。因此上例最终得到的集合等价于：

```python
{
    "rag_service/v1",
    "使用",
    "用知",
    "知识",
    "识库",
    "库知",
}
```

#### 它在当前项目中的作用

`lexical_tokens()` 不是为了得到自然语言学意义上的准确分词，而是把文本转换成一组
可以直接比较、去重和稳定哈希的简单特征。

例如问题和知识库文档分别是：

```python
question = "知识库使用什么向量数据库？"
document = "当前知识库使用 Chroma 向量数据库。"
```

去掉项目定义的高频停用词后，实际得到的部分词项是：

```python
query_tokens
# {"使用", "向量", "库使", "量数", "据库", ...}

document_tokens
# {"chroma", "使用", "向量", "库使", "量数", "据库", ...}

query_tokens.intersection(document_tokens)
# {"使用", "向量", "库使", "量数", "据库"}
```

项目用交集计算问题词项被文档覆盖的比例：

```python
lexical_overlap = len(query_tokens.intersection(document_tokens)) / max(
    1, len(query_tokens)
)
# 这组输入实际得到约 0.7143
```

因此它有两个下游用途：

1. `StableHashEmbeddings._embed()` 把每个唯一词项稳定哈希到一个向量槽位，构造
   无需模型和 API Key 的离线教学向量。
2. `KBService.ask()` 比较问题和候选文档的词项交集，辅助过滤“向量看起来相似，
   但文档实际不能回答问题”的结果。

注意：

- `set` 不保证展示顺序，所以实际打印顺序可能不同。
- 重复出现的 `"知识"` 最终只保留一份。
- 一段中文只有一个字时，`len(run) - 1` 等于 `0`，不会产生双字词项。
- 这是项目为了离线检索写的简单词项规则，不是大模型或 embedding 模型自带的 tokenizer。

### 5.10 `technical_tokens()`：筛选 API 名、字段名和英文词项

当前项目中的函数：

```python
def technical_tokens(text: str) -> set[str]:
    return {
        token
        for token in ASCII_TOKEN_PATTERN.findall(text.lower())
        if len(token) >= 3 and any(character.isalnum() for character in token)
    }
```

它可以读作：

> 把文本转成小写并提取 ASCII 词项；只保留长度至少为 3，而且至少包含一个
> 字母或数字的词项；最后用集合去重并返回。

例如：

```python
text = "字段 tenant_id 使用 API /api/v1/ask，--- 和 id"

ASCII_TOKEN_PATTERN.findall(text.lower())
# ["tenant_id", "api", "/api/v1/ask", "---", "id"]

technical_tokens(text)
# {"tenant_id", "api", "/api/v1/ask"}
```

过滤过程如下：

| 候选词项 | `len(token) >= 3` | 至少有一个字母或数字 | 是否保留 |
| --- | --- | --- | --- |
| `"tenant_id"` | 是 | 是 | 保留 |
| `"api"` | 是 | 是 | 保留 |
| `"/api/v1/ask"` | 是 | 是 | 保留 |
| `"---"` | 是 | 否 | 丢弃 |
| `"id"` | 否 | 是 | 丢弃 |

#### `any(...)` 的作用

```python
any(character.isalnum() for character in token)
```

读作：

> 逐个检查 `token` 中的字符，只要至少一个字符是字母或数字，就返回 `True`。

例如：

```python
any(character.isalnum() for character in "---")
# False

any(character.isalnum() for character in "/api/")
# True，因为其中的 a、p、i 是字母
```

整个集合推导式展开成普通 Python 循环是：

```python
result: set[str] = set()

for token in ASCII_TOKEN_PATTERN.findall(text.lower()):
    long_enough = len(token) >= 3
    contains_letter_or_number = any(
        character.isalnum()
        for character in token
    )

    if long_enough and contains_letter_or_number:
        result.add(token)

return result
```

#### 它在知识库问答中的作用

例如问题是：

```python
question = "tenant_id 字段在哪里？"
```

问题的技术词项是：

```python
query_technical_tokens = {"tenant_id"}
```

两个候选文档：

```python
document_a = "请求必须包含 tenant_id"
document_b = "请求必须包含 area_id"
```

比较结果：

```python
{"tenant_id"}.intersection({"tenant_id"})
# {"tenant_id"}，转换成 bool 后是 True

{"tenant_id"}.intersection({"area_id"})
# set()，转换成 bool 后是 False
```

因此，当问题中存在技术词项时，当前项目要求候选文档至少精确命中其中一个技术词项。
这能避免把 `tenant_id` 的问题错误匹配到只介绍 `area_id` 的文档。

这里的“技术词项”只是项目定义的启发式规则：所有符合条件的英文词项都有可能被
保留，它并不真正理解某个英文词是不是技术术语。

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

### 9.4 `getattr()` 根据名字读取属性

`getattr()` 是 Python 的内置函数，不是某个对象专有的方法。它的常用形式是：

```python
getattr(对象, "属性名", 默认值)
```

读作：

> 从这个对象上，取出名字为指定字符串的属性；如果属性不存在，就返回默认值。

```python
content = getattr(message, "content", "")
```

这里三个参数分别是：

| 参数 | 含义 |
| --- | --- |
| `message` | 要查找属性的对象 |
| `"content"` | 要读取的属性名，必须是字符串 |
| `""` | 属性不存在时返回的默认值 |

等价思路：

```python
if hasattr(message, "content"):
    content = message.content
else:
    content = ""
```

如果属性名是固定的，下面两种写法效果相同：

```python
message.content
getattr(message, "content")
```

`getattr()` 特别适合属性名保存在变量里的情况：

```python
field_name = "content"
value = getattr(message, field_name, "")
```

如果不写第三个参数，而且属性不存在，Python 会抛出 `AttributeError`：

```python
getattr(message, "missing_field")  # AttributeError
```

它也能取出方法，但只是返回方法对象，不会自动执行：

```python
method = getattr(text, "upper")
result = method()  # 现在才调用方法
```

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

当前项目还有一个利用 `or` 短路的判断：

```python
sources = active_manifest.get("sources", {})

return (
    not sources
    or active_manifest.get("index_fingerprint")
    == self.index_fingerprint
)
```

如果 `sources == {}`：

```python
not sources
# True
```

`or` 左侧已经是 `True`，Python 不再计算右侧，整个表达式直接返回 `True`。只有
`sources` 非空、`not sources` 为 `False` 时，才继续比较两个 fingerprint。

可以展开成普通 `if`：

```python
if not sources:
    return True

return (
    active_manifest.get("index_fingerprint")
    == self.index_fingerprint
)
```

方法前一行：

```python
active_manifest = manifest if manifest is not None else self.read_manifest()
```

是条件表达式，表示显式传入了 `manifest` 就直接使用；参数是 `None` 时才调用
`read_manifest()` 读取本地文件。

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

#### `IndexStats`：用 dataclass 表示一次索引的统计结果

当前项目定义：

```python
@dataclass(frozen=True)
class IndexStats:
    reset: bool
    scanned_files: int
    added_files: int
    updated_files: int
    unchanged_files: int
    removed_files: int
    indexed_chunks: int
    deleted_chunks: int
    total_indexed_chunks: int
    index_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

`IndexStats` 不保存 Chroma 中的文档和向量。它只是一次 `reindex()` 执行结束后返回的
统计结果对象：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `reset` | `bool` | 本次是否按 `reset=True` 重建索引 |
| `scanned_files` | `int` | 本次扫描到的受支持来源文件数 |
| `added_files` | `int` | 新增来源文件数 |
| `updated_files` | `int` | 内容发生变化并重新索引的已有文件数 |
| `unchanged_files` | `int` | 与 manifest 相比没有变化的文件数 |
| `removed_files` | `int` | 已从来源目录删除的文件数 |
| `indexed_chunks` | `int` | 本次实际新增或重新写入 Chroma 的 chunk 数 |
| `deleted_chunks` | `int` | 本次从 Chroma 删除的旧 chunk 数 |
| `total_indexed_chunks` | `int` | 本次执行结束后整个知识库的 chunk 总数 |
| `index_fingerprint` | `str` | chunk 参数、Embedding 身份和 collection 的配置指纹 |

例如：

```python
stats = IndexStats(
    reset=False,
    scanned_files=5,
    added_files=1,
    updated_files=1,
    unchanged_files=3,
    removed_files=0,
    indexed_chunks=2,
    deleted_chunks=1,
    total_indexed_chunks=6,
    index_fingerprint="16fff5586f9f9b4a372b",
)
```

这些字段都没有定义默认值，因此创建对象时少传任何一个字段都会报错：

```python
IndexStats(
    reset=False,
    scanned_files=5,
)
# TypeError：缺少其他必需参数
```

#### `asdict()` 是 dataclasses 模块函数

项目导入的是：

```python
from dataclasses import asdict, dataclass
```

所以：

```python
asdict(self)
```

表示把当前 dataclass 实例转换成一个新的字典。它不是 `IndexStats` 自带的方法，下面
这样调用才是原始形式：

```python
payload = asdict(stats)
```

结果是：

```python
{
    "reset": False,
    "scanned_files": 5,
    "added_files": 1,
    "updated_files": 1,
    "unchanged_files": 3,
    "removed_files": 0,
    "indexed_chunks": 2,
    "deleted_chunks": 1,
    "total_indexed_chunks": 6,
    "index_fingerprint": "16fff5586f9f9b4a372b",
}
```

项目为了让调用方使用更直观，另外包装了一个实例方法：

```python
def to_dict(self) -> dict[str, Any]:
    return asdict(self)
```

因此：

```python
stats.to_dict()
```

内部实际执行的仍然是：

```python
asdict(stats)
```

`asdict()` 还会递归转换嵌套的 dataclass；普通类实例不能直接传给它。

转换成字典后，CLI 可以交给 `json.dumps()` 输出 JSON，FastAPI 也可以通过：

```python
ReindexResponse(request_id=request_id, **stats.to_dict())
```

把字典中的统计字段展开为 `ReindexResponse` 的关键字参数。

#### `ChunkedSource`：保存一个来源文件的全部切块结果

当前项目定义：

```python
@dataclass(frozen=True)
class ChunkedSource:
    source: str
    source_sha256: str
    documents: list[Document]
    chunk_ids: list[str]
```

`ChunkedSource` 是项目自己定义的 dataclass，不是 Chroma 对象，也不是 LangChain
提供的类型。它表示：

> 一个来源文件完成切块和 chunk ID 生成以后得到的中间结果。

名称可以拆成：

```text
Chunked = 已经完成切块的
Source  = 一个来源文件
```

各字段含义：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `source` | `str` | 来源文件相对于知识库目录的路径 |
| `source_sha256` | `str` | 整个来源文件的 SHA-256，用于判断文件内容是否变化 |
| `documents` | `list[Document]` | 切分并补充 metadata 后的 chunk Document 列表 |
| `chunk_ids` | `list[str]` | 与 `documents` 按相同顺序一一对应的稳定 chunk ID |

一个来源文件可能产生多个 chunk：

```text
rag_basics.md
    ↓ Loader
LoadedSource（原始 Document）
    ↓ RecursiveCharacterTextSplitter
ChunkedSource
├── documents[0] ↔ chunk_ids[0]
├── documents[1] ↔ chunk_ids[1]
└── documents[2] ↔ chunk_ids[2]
```

这里最重要的隐含约束是：

```python
len(chunked_source.documents) == len(chunked_source.chunk_ids)

chunked_source.documents[index].metadata["chunk_id"] \
    == chunked_source.chunk_ids[index]
```

当前代码在同一个循环中同时追加 `Document` 和 ID，所以能够保持这个对应关系：

```python
documents.append(Document(page_content=content, metadata=metadata))
chunk_ids.append(chunk_id)
```

它有两个主要下游用途：

1. 写入 Chroma：

   ```python
   store.add_documents(
       documents=source.documents,
       ids=source.chunk_ids,
   )
   ```

2. 写入增量索引 manifest：

   ```python
   {
       "sha256": source.source_sha256,
       "chunk_count": len(source.chunk_ids),
       "chunk_ids": source.chunk_ids,
   }
   ```

因此 `ChunkedSource` 本身不执行切块，也不执行向量计算；真正切块发生在
`_chunk_source()` 中。它只把切块完成后的相关数据打包在一起，方便后续同时写
Chroma 和 manifest。

`frozen=True` 只能阻止给字段重新赋值：

```python
chunked_source.source = "other.md"
# FrozenInstanceError
```

但 `documents` 和 `chunk_ids` 本身仍然是可变列表；语法上依旧能够执行
`append()`。因此这里的“不修改列表内容”仍然依靠项目代码约定。

#### `settings: Settings`：配置类、参数变量和实例属性

当前项目代码：

```python
class IncrementalIndexer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._embeddings = build_embeddings(settings)
```

需要先区分三个名称：

| 名称 | 含义 |
| --- | --- |
| `Settings` | 项目定义的配置类，类名首字母大写且使用复数 |
| `settings` | 调用 `__init__()` 时接收配置对象的参数变量 |
| `self.settings` | 当前 `IncrementalIndexer` 实例保存配置对象的属性 |

```python
settings: Settings
```

读作：

> 参数名是 `settings`，按照类型标注，调用方应该传入一个 `Settings` 实例。

冒号后面的 `Settings` 只是类型标注，不会在这里创建配置，也不会自动把字典转换成
`Settings`。项目真正创建和解析配置的位置是：

```python
settings = Settings.from_env()
indexer = IncrementalIndexer(settings)
```

执行：

```python
self.settings = settings
```

只是把同一个对象引用保存到实例属性中，没有复制对象，也没有重新读取环境变量：

```python
indexer.settings is settings
# True
```

`__init__` 是实例初始化方法。调用：

```python
IncrementalIndexer(settings)
```

时 Python 自动创建实例并调用：

```python
IncrementalIndexer.__init__(new_instance, settings)
```

`__init__()` 负责初始化已有的新实例，正常情况下返回 `None`。

#### `Settings` 是 frozen dataclass

当前项目中的 `Settings` 是普通 Python dataclass，不是 Pydantic `BaseSettings`：

```python
@dataclass(frozen=True)
class Settings:
    mode: Literal["offline", "live"]
    embedding_mode: Literal["local", "hash", "glm"]
    source_dir: Path
    runtime_dir: Path
    ...
```

`@dataclass` 自动生成接收这些字段的 `__init__()`；`frozen=True` 表示对象创建后不应
重新给字段赋值：

```python
settings.mode = "live"
# FrozenInstanceError
```

主要字段可以分为：

| 分类 | 字段 | 作用 |
| --- | --- | --- |
| 运行模式 | `mode` | `offline` 使用本地摘录回答；`live` 调用聊天模型生成 |
| 向量模式 | `embedding_mode` | 选择 `local`、`hash` 或 `glm` Embedding |
| 来源和运行目录 | `source_dir`、`runtime_dir` | 知识来源目录与持久化运行目录 |
| Chroma | `collection_name` | Chroma collection 名称 |
| 切块 | `chunk_size`、`chunk_overlap` | chunk 大小和重叠长度 |
| 检索 | `default_top_k` | 默认召回候选数量 |
| 拒答门槛 | `min_relevance_score`、`min_lexical_overlap` | 候选文档最低相关度要求 |
| 上下文 | `max_context_chars` | 最终交给回答阶段的上下文字符上限 |
| 超时 | `timeout_seconds` | 在线模型请求超时 |
| 在线模型 | `zhipu_api_key`、`zhipu_base_url`、`chat_model` | 在线聊天模型配置 |
| 远程向量模型 | `embedding_model` | `glm` 模式使用的 Embedding 模型名 |
| 本地向量模型 | `local_embedding_model`、`local_embedding_cache`、`local_embedding_path` | 本地模型身份、缓存和文件路径 |
| 追踪 | `langsmith_tracing` | 是否启用 LangSmith tracing |

不要直接把完整 `settings` 对象写入日志或文档。dataclass 自动生成的 `repr` 默认会展示
所有字段，其中包括 `zhipu_api_key`。需要排查配置时，应只打印允许公开的字段，或者把
密钥替换成是否已配置的布尔值。

此外还有三个计算属性，它们不是额外存储的字段：

```python
settings.manifest_path
# settings.runtime_dir / "index_manifest.json"

settings.chroma_dir
# settings.runtime_dir / "chroma"

settings.is_live
# settings.mode == "live"
```

#### `Settings.from_env()` 才负责解析配置

`from_env()` 是类方法，执行顺序是：

```text
读取已有系统环境变量
    ↓
根目录 .env 补充缺失值
    ↓
目录 4 的 .env 再补充仍然缺失的值
    ↓
读取并转换 str / int / float / bool / Path
    ↓
校验模式、API Key 条件和切块参数
    ↓
cls(...) 创建 Settings 实例
```

调用方也可以显式覆盖部分配置：

```python
Settings.from_env(
    mode="offline",
    embedding_mode="hash",
    runtime_dir=temporary_runtime_dir,
)
```

项目会执行的主要校验包括：

- `mode` 只能是 `offline` 或 `live`。
- `embedding_mode` 只能是 `local`、`hash` 或 `glm`。
- `live` 和 `glm` 模式要求配置 API Key。
- 必须满足 `chunk_size > chunk_overlap >= 0`。

因此下面的完整传递过程是：

```text
Settings.from_env()
    ↓ 返回 Settings 实例
settings
    ↓ 传给 KnowledgeBaseService
service.settings
    ↓ 同一个对象继续传给 IncrementalIndexer
indexer.settings
    ↓ build_embeddings(settings) / _store() / reindex() / search()
```

#### `@property`：`index_fingerprint` 是读取时计算的属性

当前项目代码：

```python
@property
def index_fingerprint(self) -> str:
    payload = {
        "chunk_size": self.settings.chunk_size,
        "chunk_overlap": self.settings.chunk_overlap,
        "embedding": embedding_identity(self.settings),
        "collection": self.settings.collection_name,
    }
    return _sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False)
    )[:20]
```

`@property` 会让一个无参数实例方法使用起来像普通属性：

```python
fingerprint = indexer.index_fingerprint
```

上面这行访问属性时，Python 实际调用概念上接近：

```python
fingerprint = type(indexer).index_fingerprint.fget(indexer)
```

调用方不写括号：

```python
indexer.index_fingerprint    # 正确
indexer.index_fingerprint()  # 错误：前一次访问已经得到 str
```

它没有在 `__init__()` 中执行：

```python
self.index_fingerprint = ...
```

也没有缓存计算结果。每次读取 `indexer.index_fingerprint` 都会根据当前索引构建配置
重新计算并返回一个 `str`。

当 `_empty_manifest()` 执行：

```python
{
    "index_fingerprint": self.index_fingerprint,
}
```

时，右侧先触发 property 计算，得到的字符串随后才作为普通 value 放进新字典。

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

当前知识库项目也使用了函数内部导入：

```python
def _store(self):
    from langchain_chroma import Chroma
    ...
```

只有调用 `_store()` 时，当前函数才需要获得 `Chroma` 这个名称。每次调用都会执行到
这条 `import` 语句，但 Python 通常会从 `sys.modules` 模块缓存中复用已经导入的模块，
不会每次都重新加载整个 `langchain_chroma` 包。

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

### 12.3 `Path.read_text()` 读取文本时的参数

项目代码：

```python
text = path.read_text(encoding="utf-8", errors="replace").strip()
```

假设 `path` 当前是：

```python
Path("4_rag_knowledge_base_service/data/source/rag_basics.md")
```

这一行读作：

> 让 `path` 这个 `Path` 对象用 UTF-8 编码读取文件；遇到不能按 UTF-8
> 解码的字节时，用替代字符代替；读取完成后，再删除文本首尾的空白字符。

当前项目 Python 环境中的方法签名是：

```python
Path.read_text(self, encoding=None, errors=None)
```

项目代码里的参数对应关系：

| 参数 | 实际值 | 作用 |
| --- | --- | --- |
| `self` | `path` | 要读取的路径对象；写成 `path.read_text(...)` 时由 Python 自动传入 |
| `encoding` | `"utf-8"` | 指定用 UTF-8 把文件字节解码成 `str` |
| `errors` | `"replace"` | 遇到非法 UTF-8 字节时，用 Unicode 替代字符 `�` 代替，而不是抛出 `UnicodeDecodeError` |

`errors` 表示“解码发生错误时采用什么处理策略”。文件在磁盘上保存的是
`bytes`；Python 按 `encoding="utf-8"` 把这些字节转换成 `str`。如果某段字节
不符合 UTF-8 规则，`errors="replace"` 就让 Python 用 `�` 占住出错位置并继续
读取。

例如：

```python
raw = b"hello \xff world"

text = raw.decode("utf-8", errors="replace")
print(text)
```

输出：

```text
hello � world
```

其中 `\xff` 不是合法的 UTF-8 起始字节，所以被替换成了 `�`。常见策略的区别：

| 写法 | 遇到非法字节时的结果 |
| --- | --- |
| `errors="strict"` | 立即抛出 `UnicodeDecodeError` |
| `errors="replace"` | 用 `�` 替换出错部分，然后继续解码 |
| `errors="ignore"` | 直接丢弃出错部分，然后继续解码 |

`replace` 的优点是一个异常字符不会中断整个文件的读取；代价是被替换位置的
原始文字已经丢失。如果整个文件实际使用 GBK 等其他编码，却错误地指定为
UTF-8，结果中可能出现很多 `�`，此时应该改正 `encoding`，而不是把 `replace`
当成编码转换。

所以方法调用也可以从理解语法的角度写成：

```python
text = Path.read_text(
    path,
    encoding="utf-8",
    errors="replace",
).strip()
```

平时应优先使用原来的 `path.read_text(...)` 写法。上面的展开只是为了说明
点号左边的对象会作为 `self` 自动传给实例方法。

`encoding="utf-8"` 和 `errors="replace"` 都使用了“关键字参数”：

```python
参数名=参数值
```

因此阅读代码时可以直接看出每个值的用途，不需要只靠参数位置判断。

`read_text(...)` 大致等价于：

```python
with path.open(
    mode="r",
    encoding="utf-8",
    errors="replace",
) as file:
    original_text = file.read()

text = original_text.strip()
```

执行顺序是：

1. `path.read_text(...)` 打开文件、读取文本并关闭文件。
2. 它返回一个新的 `str` 字符串。
3. 再对返回的字符串调用 `.strip()`。
4. `.strip()` 返回删除了首尾空格、换行符、制表符等空白字符的新字符串。
5. 最终把这个新字符串赋给变量 `text`。

需要特别区分：

- `.strip()` 不是 `read_text()` 的参数，而是对读取结果进行的下一次方法调用。
- `.strip()` 只清理字符串首尾，不会删除正文内部的空格或换行。
- `errors="replace"` 只处理“字节无法按指定编码解码”的问题；文件不存在、
  没有读取权限等问题仍然会抛出相应异常。
- 如果使用默认的 `errors=None`，文本读取通常采用严格解码；遇到非法 UTF-8
  字节会抛出 `UnicodeDecodeError`。

### 12.4 `Path.mkdir(parents=True, exist_ok=True)` 创建目录

当前项目代码：

```python
self.settings.chroma_dir.mkdir(parents=True, exist_ok=True)
```

这里 `self.settings.chroma_dir` 是一个 `Path` 对象。这行可以读作：

> 创建 Chroma 持久化目录；缺少的父目录也一起创建；如果目录已经存在则继续执行。

两个参数分别表示：

| 参数 | 含义 |
| --- | --- |
| `parents=True` | 父目录不存在时递归创建父目录 |
| `exist_ok=True` | 目标目录已经存在时不抛出 `FileExistsError` |

例如：

```python
path = Path("runtime/chroma")
result = path.mkdir(parents=True, exist_ok=True)

print(result)
# None
```

`mkdir()` 负责产生目录创建这一文件系统副作用，正常完成时返回 `None`。它不会清空
已经存在的目录，也不会删除其中的 Chroma 数据。

`exist_ok=True` 只表示“目录已经存在可以接受”。如果目标路径已经是普通文件、父目录
没有写权限或磁盘发生错误，仍然会抛出相应异常。

项目随后执行：

```python
persist_directory = str(self.settings.chroma_dir)
```

这是把 `Path` 对象转换成 Chroma 构造函数接收的路径字符串；它不会再次创建目录。

### 12.5 `Path.rglob("*")` 递归查找目录内容

项目代码：

```python
for path in sorted(source_dir.rglob("*")):
```

其中：

```python
source_dir.rglob("*")
```

读作：

> 从 `source_dir` 目录开始，递归查找它下面所有层级中名称符合 `"*"`
> 的项目。

各部分含义：

| 部分 | 含义 |
| --- | --- |
| `source_dir` | 一个 `Path` 目录对象，也是搜索起点 |
| `rglob(...)` | recursive glob，按照通配模式递归查找 |
| `"*"` | 通配模式，表示任意名称 |

例如有如下目录：

```text
source/
├── a.md
├── image.png
└── notes/
    └── b.md
```

那么：

```python
paths = source_dir.rglob("*")
```

迭代 `paths` 时，可以得到这些 `Path` 对象：

```text
source/a.md
source/image.png
source/notes
source/notes/b.md
```

需要注意：

- 它查找的是 `source_dir` 的后代，不包含 `source_dir` 自己。
- 结果既可能包含文件，也可能包含目录。
- 它返回的是惰性迭代器，在当前项目 Python 环境中实际类型为 `generator`，
  不是已经装好全部结果的 `list`。
- 每次迭代得到的元素都是 `Path` 对象。

可以这样观察惰性迭代：

```python
paths = source_dir.rglob("*")  # 此时得到 generator

for path in paths:
    print(path)                # 迭代时逐个得到 Path
```

`glob()` 与 `rglob()` 的区别：

```python
source_dir.glob("*")       # 只匹配当前目录的直接子项
source_dir.rglob("*")      # 递归匹配所有层级中的子项
source_dir.rglob("*.md")   # 递归匹配所有层级中的 Markdown 文件名
```

在完整项目代码中，数据流是：

```python
found_paths = source_dir.rglob("*")  # generator[Path]
sorted_paths = sorted(found_paths)   # 消耗 generator，得到排序后的 list[Path]

for path in sorted_paths:
    if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
        continue
```

因为 `"*"` 也会找到目录和不支持的文件，所以后面的条件继续筛选：

- `path.is_file()`：只保留普通文件，排除目录。
- `path.suffix.lower()`：取得小写扩展名。
- `SUPPORTED_SUFFIXES`：只允许 `.md`、`.markdown` 和 `.pdf`。
- `continue`：当前项目不符合条件时，直接进入下一轮循环。

### 12.6 `relative_to().as_posix()` 生成相对路径字符串

项目代码：

```python
source = path.relative_to(source_dir).as_posix()
```

这里的 `source` 不是 Python 关键字，只是作者定义的变量名。在这个知识库项目中，
它表示“来源文件标识”，也就是当前文档来自知识库中的哪个文件。

`path` 和 `source` 的用途不同：

| 变量 | 示例值 | 类型 | 用途 |
| --- | --- | --- | --- |
| `path` | `Path("/project/data/source/manual/setup.md")` | `Path` | 访问磁盘上的真实文件 |
| `source` | `"manual/setup.md"` | `str` | 保存到 metadata、索引和引用结果中的稳定来源标识 |

这条链式调用分两步执行。假设：

```python
source_dir = Path("/project/data/source")
path = Path("/project/data/source/manual/setup.md")
```

第一步：

```python
relative_path = path.relative_to(source_dir)
```

得到：

```python
Path("manual/setup.md")
```

`relative_to(source_dir)` 的意思是：

> 以 `source_dir` 为起点，计算 `path` 位于它下面的相对路径。

可以从理解效果的角度把它看成删除共同的目录前缀：

```text
完整路径：/project/data/source/manual/setup.md
起点目录：/project/data/source
相对结果：                    manual/setup.md
```

但它不是普通的字符串替换，而是按照路径层级计算。如果 `path` 不在
`source_dir` 里面，`relative_to()` 会抛出 `ValueError`。

第二步：

```python
source = relative_path.as_posix()
```

得到：

```python
"manual/setup.md"
```

`as_posix()` 做两件容易混淆的事：

- 把 `Path` 转成 `str`。
- 使用 POSIX 风格的 `/` 作为路径分隔符。

例如在 Windows 上，普通路径字符串可能是：

```text
manual\setup.md
```

调用 `as_posix()` 后统一为：

```text
manual/setup.md
```

所以原代码可以拆成：

```python
relative_path = path.relative_to(source_dir)  # Path
source = relative_path.as_posix()             # str
```

当前项目中的实际示例：

```python
source_dir = Path("4_rag_knowledge_base_service/data/source")
path = source_dir / "rag_basics.md"

relative_path = path.relative_to(source_dir)
source = relative_path.as_posix()
```

中间值和类型：

```text
relative_path = PosixPath("rag_basics.md")  # Path
source = "rag_basics.md"                    # str
```

项目不直接把机器上的绝对路径作为 `source`，是因为绝对路径会随着电脑、项目
安装位置或容器挂载位置变化；相对于知识库根目录的 `"rag_basics.md"` 更稳定。
这个值随后会进入 `Document.metadata["source"]`，并用于索引 manifest、稳定
chunk ID、检索记录和最终 citation。

### 12.7 `sys.path.insert(0, path)` 调整模块搜索顺序

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

### 14.3 `mkstemp()`、`fdopen()` 与临时文件原子替换

`4_rag_knowledge_base_service/indexer.py`：

```python
def _write_manifest(self, payload: dict[str, Any]) -> None:
    self.settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix=".index_manifest.", suffix=".tmp", dir=self.settings.runtime_dir
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_path, self.settings.manifest_path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
```

这不是普通的“直接打开正式文件并覆盖”，而是：

```text
创建并打开临时文件
    ↓
把 manifest JSON 写入临时文件
    ↓
关闭临时文件
    ↓
用完整临时文件替换正式 manifest
    ↓
发生异常时删除遗留的临时文件
```

#### `fd, temporary_path` 是返回值拆包

```python
fd, temporary_path = tempfile.mkstemp(...)
```

等价于：

```python
result = tempfile.mkstemp(...)
fd = result[0]
temporary_path = result[1]
```

两个值分别是：

| 变量 | 典型类型 | 含义 |
| --- | --- | --- |
| `fd` | `int` | 已经打开的操作系统文件描述符，例如 `3`、`4` |
| `temporary_path` | `str` | 这个临时文件的路径 |

`fd` 不是文件锁，也不是文件内容。它是操作系统用来标识当前已打开文件的整数句柄。
`mkstemp()` 已经同时完成了“安全创建临时文件”和“打开文件”，所以不能再只根据
`temporary_path` 重复打开而忘记关闭 `fd`。

`os.fdopen(fd, ...)` 把这个底层整数描述符包装成 Python 文件对象：

```python
handle = os.fdopen(fd, "w", encoding="utf-8")
```

其中：

- `"w"`：按文本写入模式使用；
- `encoding="utf-8"`：把 Python 字符串编码成 UTF-8 字节；
- `handle`：具有 `.write()`、`.close()` 等方法的文本文件对象。

#### 这里的 `with` 负责关闭文件

```python
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    ...
```

进入 `with` 后，`handle` 指向文件对象；离开代码块时会自动执行关闭逻辑。无论正常
结束，还是 `json.dump()` 抛出异常，文件对象都会被关闭，写入缓冲也会在关闭过程中
刷新。

它可以近似理解为：

```python
handle = os.fdopen(fd, "w", encoding="utf-8")
try:
    ...
finally:
    handle.close()
```

#### `json.dump()` 直接把 JSON 写入文件对象

```python
json.dump(
    payload,
    handle,
    ensure_ascii=False,
    indent=2,
    sort_keys=True,
)
```

参数含义：

| 参数 | 含义 |
| --- | --- |
| `payload` | 要序列化的 Python 对象；这里是 `dict` |
| `handle` | JSON 的写入目标文件对象 |
| `ensure_ascii=False` | 中文直接写成中文，不转换成 `\u4e2d` 形式 |
| `indent=2` | 使用两个空格缩进，便于人阅读 |
| `sort_keys=True` | 按字典键排序，让文件输出顺序稳定 |

`json.dump()` 中的 `dump` 没有 `s`，表示直接写入文件；`json.dumps()` 末尾的 `s`
可以理解为 string，它返回 JSON 字符串：

```python
json.dump(payload, handle)  # 返回 None，JSON 写入 handle
json_text = json.dumps(payload)  # 返回 str
```

`handle.write("\n")` 再给 JSON 文件末尾补一个换行，方便终端查看和版本管理。

#### `replace` 提交结果，`unlink` 清理残留文件

```python
os.replace(temporary_path, self.settings.manifest_path)
```

写入完整并关闭文件后，再用临时文件替换正式 manifest。临时文件和正式文件在同一个
目录中，因此正常情况下替换是原子的：其他读取者通常只会看到旧的完整文件或新的
完整文件，不会看到只写了一半的 JSON。

```python
finally:
    if os.path.exists(temporary_path):
        os.unlink(temporary_path)
```

`finally` 无论前面成功还是抛出异常都会执行。`os.unlink(path)` 表示删除这个文件路径，
近似于：

```python
os.remove(path)
```

它不是关闭文件，也不是解除文件锁。文件描述符由前面的 `with` 关闭；这里负责删除
写入失败后可能遗留的 `.tmp` 文件。替换成功时，临时路径已经被移动成正式路径，
`os.path.exists(temporary_path)` 通常为 `False`，不会误删正式 manifest。

这套写法可以概括成：

> 先完整写临时文件，成功后一次性替换正式文件；失败则清理临时文件。

### 14.4 三引号也可以表示多行普通字符串

```python
sql = """
CREATE TABLE Genre (...);
INSERT INTO Genre VALUES (...);
"""
```

当它被赋值给变量或作为函数参数时，就是普通的多行字符串，不是文档字符串。

### 14.5 注册函数时不要提前调用

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
