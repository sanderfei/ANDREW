# Python 基础语法笔记

这份笔记汇总已经学习过的 Python 基础语法问题。重复问题已经合并，示例使用简化的
通用代码。

涉及 LangChain 专有 API 的内容放在根目录的 `LangChain基础语法笔记.md`；本文件只记录
通用 Python 语法、类型和执行规则，不记录某个项目函数的完整业务逻辑。

## 阅读导航

| 想复习的问题 | 对应章节 |
| --- | --- |
| `Iterable`、`Sequence`、`tuple`、`object`、`Literal`、`TypedDict`、函数参数类型标注 | 第 1、3 节 |
| `zip()`、`enumerate()`、变量拆包 | 第 2、8 节 |
| 列表、字典、元组、`set`、`frozenset`、嵌套列表、索引、切片、`range()` 分批 | 第 4、5 节 |
| `dict.get()`、`setdefault()`、`pop()`、`items()`、`sorted()` | 第 4 节 |
| 列表推导式、生成器表达式、`extend()`、双层 `flatten` | 第 6 节 |
| 默认参数、`*`、`*args`、`**kwargs`、`**config` | 第 7 节 |
| `argparse`、`action="store_true"`、`choices`、`default` | 第 7 节 |
| 三元条件表达式、`isinstance`、`hasattr`、`getattr` | 第 9 节 |
| `__init__`、`self`、属性、`@property`、`@dataclass`、`@classmethod`、`default_factory` | 第 10 节 |
| `import`、包层级、类或函数作为字典的值 | 第 11 节 |
| `Path`、`__file__`、路径 `/` 拼接 | 第 12 节 |
| `splitlines()`、`casefold()`、`re.sub()` | 第 5 节 |
| `async`、`await`、`gather`、`yield`、`async for`、同步/异步方法边界 | 第 13 节 |
| `with`、`@contextmanager`、回调注册 | 第 14 节 |
| 终端与 Python REPL 为什么不能混用 | 第 15 节 |
| Python 字典与 JSON 的区别 | 第 16 节 |

## 1. `Iterable[T]` 是什么

```python
def collect(values: Iterable[str]) -> list[str]:
    return list(values)
```

### 1.1 怎么读

```python
values: Iterable[str]
```

读作：

> 参数 `values` 接受一个可迭代对象，遍历它时，每次应该得到一个字符串。

这里各部分的含义是：

| 代码 | 含义 |
| --- | --- |
| `values` | 参数名 |
| `:` | 后面是类型标注 |
| `Iterable` | 可迭代对象类型 |
| `[str]` | 迭代时产生的元素应该是字符串 |

`Iterable` 不是 Python 关键字，也不是某一种固定的数据结构。它是用于类型标注的
可迭代类型，表示“这个对象能够被遍历”：

```python
from typing import Iterable
```

在其他代码中也经常会看到 `from collections.abc import Iterable`。

### 1.2 哪些对象属于 `Iterable[str]`

只要对象能够被 `for` 遍历，并且其中的元素是字符串，就可以传给这个参数：

```python
# 列表
values = ["a", "b"]

# 元组
values = ("a", "b")

# 生成器
values = (value for value in ["a", "b"])
```

它们都可以这样遍历：

```python
for value in values:
    print(value)
```

关系可以简单理解为：

```text
Iterable[str]（能逐个遍历出 str）
├── list[str]
├── tuple[str, ...]
├── generator
└── 其他实现了可迭代协议的对象
```

### 1.3 `Iterable`、`Sequence` 和 `tuple` 的区别

| 类型 | 保证能遍历 | 保证有顺序 | 保证支持索引 | 是否是具体容器 |
| --- | --- | --- | --- | --- |
| `Iterable[str]` | 是 | 否 | 否 | 否，是一种能力约束 |
| `Sequence[str]` | 是 | 是 | 是 | 否，是一种更严格的能力约束 |
| `tuple[str, ...]` | 是 | 是 | 是 | 是，明确要求元组 |

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

因此，参数标注为 `Iterable[str]` 时，函数内部不能直接假定下面的操作一定可用：

```python
values[0]    # 不一定支持索引
len(values)  # 不一定支持获取长度
```

可以先转换成列表：

```python
items = list(values)
```

这会把列表、元组或生成器等可迭代对象统一转换成列表。

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

### 1.4 返回值 `-> list[str]`

函数定义中的：

```python
) -> list[str]:
```

表示该函数的返回值是一个列表，列表中的每一项都是字符串。

类型标注主要用于帮助阅读代码、编辑器提示和静态类型检查。Python 通常不会仅仅因为写了类型标注，就在运行时自动检查传入对象的类型。

## 2. `zip()` 是什么

### 2.1 `zip()` 的作用

`zip()` 会同时遍历多个可迭代对象，把相同位置的元素配对在一起。

假设数据是：

```python
names = ["Alice", "Bob"]
scores = [90, 85]
```

执行：

```python
zip(names, scores)
```

遍历时会依次产生两个二元组：

```python
("Alice", 90)
("Bob", 85)
```

注意，`zip()` 返回的是一个可迭代的 `zip` 对象。为了直接查看全部内容，可以先转成列表：

```python
pairs = list(zip(names, scores))
```

结果为：

```python
[
    ("Alice", 90),
    ("Bob", 85),
]
```

### 2.2 `for name, score` 是元组拆包

下面这段代码：

```python
for name, score in zip(names, scores)
```

每次先从 `zip()` 得到一个二元组，然后自动拆给两个变量。

第一次循环相当于：

```python
name, score = ("Alice", 90)

# 拆包之后：
name = "Alice"
score = 90
```

### 2.3 完整列表推导式怎么执行

下面是一个列表推导式：

```python
result = [
    {
        "name": name,
        "score": score,
    }
    for name, score in zip(names, scores)
]
```

它等价于普通的 `for` 循环：

```python
result = []

for name, score in zip(names, scores):
    item = {
        "name": name,
        "score": score,
    }
    result.append(item)
```

最终得到的是一个 Python 字典列表：

```python
[
    {
        "name": "Alice",
        "score": 90,
    },
    {
        "name": "Bob",
        "score": 85,
    },
]
```

执行顺序是：先按位置配对，再拆包，把每一对值转换成字典，最后收集成列表。

### 2.4 两边长度不同时会怎样

普通 `zip()` 不要求两边长度相同，它会在较短的一边结束时停止：

```python
names = ["Alice", "Bob"]
scores = [90]

result = list(zip(names, scores))
print(result)
```

结果只有一组：

```python
[("Alice", 90)]
```

`"Bob"` 会被静默忽略。

如果要求两个列表长度必须相同，可以写成：

```python
zip(names, scores, strict=True)
```

长度不一致时，Python 会抛出 `ValueError`，这样更容易发现数据对应关系出了问题。

## 3. 类型标注：`list`、`dict`、`tuple`、`object`、`None`、`Literal`

### 3.1 `变量: 类型 = 值` 要分成三部分看

示例：

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
        "width": 80,
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

示例：

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

元组可以包含不同类型的元素。例如：

```python
list[tuple[str, float]]
```

它表示外层是列表，列表中的每一项都是：

```python
(字符串, 浮点数)
```

两种常见元组标注：

```python
tuple[str, bytes]       # 固定两个位置，并分别指定类型
tuple[str, ...]         # 任意多个字符串
```

### 3.4 `Model | None = None` 要分成两段

```python
model: Model | None = None
```

第一段是类型：

```python
Model | None
```

表示参数既可以是 `Model` 对象，也可以是 `None`。`|` 在类型标注中表示联合类型。

第二段是默认值：

```python
= None
```

表示调用函数时可以省略这个参数，省略后它的值就是 `None`：

```python
build_service()            # 使用默认值 None
build_service(model=None)  # 显式传 None
build_service(model=model)
```

下面的写法同理：

```python
text: str | None = None
```

表示 `text` 可以是字符串，也可以为空值 `None`，并且默认是 `None`。

### 3.5 `Literal[...]` 是固定值类型

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

`Literal` 中列出多个字符串，不表示“字符串列表”，而是表示一个变量只能取其中一个
单独的字符串值：

```python
MetricName = Literal[
    "completed_order_count",
    "completed_revenue",
    "average_completed_order_value",
]

metric: MetricName = "completed_revenue"

type(metric)  # str
```

这里需要区分“类型别名”和“变量值”：

```text
MetricName    一个 Literal 类型别名，不是实际业务字符串，也不是 list
metric        使用该类型标注的变量，运行时值是一个 str
```

正确的单值和列表写法分别是：

```python
# 单个值，只能从三个字符串中选择一个
metric: MetricName = "completed_revenue"

# 多个值，列表中的每个元素都必须是允许的字符串之一
metrics: list[MetricName] = [
    "completed_order_count",
    "completed_revenue",
]
```

因此：

```python
metric = ["completed_revenue"]
```

不符合 `MetricName`，因为它是 `list[str]`，不是单个 `str`。在 Part 4 中，Pydantic
又把 `Literal` 转换成运行时 `enum` 校验，所以 Tool 输入非法字符串或列表时会直接
产生 `ValidationError`。

### 3.6 `TypedDict` 联合与判别字段

多个运行时都是普通 `dict` 的事件，可以用不同 `TypedDict` 描述，并用一个固定值字段
区分结构：

```python
from typing import Any, Literal, TypedDict


class ValuesEvent(TypedDict):
    type: Literal["values"]
    data: dict[str, Any]


class CustomEvent(TypedDict):
    type: Literal["custom"]
    data: Any


Event = ValuesEvent | CustomEvent
```

`Event` 是联合类型，`type` 是判别字段：

```python
def consume(event: Event) -> None:
    if event["type"] == "values":
        state = event["data"]
    elif event["type"] == "custom":
        payload = event["data"]
```

类型检查器可以根据 `event["type"]` 的值缩小 `event` 和 `data` 的类型。运行时的
`event` 仍是普通字典，`TypedDict` 不会创建一种新的字典对象，也不会自动执行运行时
校验。这种写法常称为“带判别字段的联合类型”。

### 3.7 类型标注不会自动创建对象

```python
items: list[str]
```

这一行只声明类型，并没有创建列表。真正创建空列表需要：

```python
items: list[str] = []
```

同样，函数的入参类型和返回类型只是约定：

```python
def build_model(model_class: type) -> object:
    ...
```

它们用于阅读、编辑器提示和静态检查，不代表 Python 会自动初始化或转换对象。

返回值类型标注也可以完全省略：

```python
# 有返回值类型标注
def build_business_metric_tool(database_path: Path) -> BaseTool:
    return query_business_metric


# 没有返回值类型标注，运行行为不变
def build_business_metric_tool(database_path: Path):
    return query_business_metric
```

两种写法真正返回什么，都只由 `return` 后面的对象决定。Part 4 中
`query_business_metric` 经过 `@tool` 装饰后，实际是一个 `StructuredTool` 对象；
`StructuredTool` 是 `BaseTool` 的子类，所以写 `-> BaseTool` 是用父类型声明函数对外
承诺的接口。

省略 `-> BaseTool` 不会影响 `@tool`、Pydantic 参数校验或 `tool.invoke()`，但会减少：

```text
阅读代码时的返回类型说明
编辑器对 .invoke()、.name 等属性的补全
静态类型检查器对错误返回值的检查
```

即使标注写错，Python 默认也不会在运行时自动阻止返回：

```python
def example() -> int:
    return "实际仍然返回字符串"
```

这里运行时返回的是 `str`；错误主要由编辑器或 mypy、pyright 等静态检查工具发现。

### 3.7 多个函数参数要分别读取各自的类型标注

```python
def combine(prefix, values: Iterable[str]) -> str:
    return prefix + ",".join(values)
```

参数之间使用逗号分隔，每个类型标注只属于紧靠它左侧的参数：

```text
prefix                  没有显式类型标注
values: Iterable[str]   遍历时应当产生 str
-> str                  返回值应当是 str
```

`values` 后面的标注不会向左作用到 `prefix`。列表、元组和产生字符串的生成器都可以
满足 `Iterable[str]`：

```python
["a", "b"]
("a", "b")
(value for value in ["a", "b"])
```

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

```python
def save(writer, text):
    writer.write(text)
```

虽然 `writer` 没有类型标注，但运行时要求它提供可调用的 `.write(...)` 方法。只要对象
提供所需能力，代码就可以工作，这种风格通常称为“鸭子类型”：

```text
不先检查它名义上属于哪个类
    ↓
直接使用当前逻辑需要的方法
    ↓
方法存在且调用兼容，就可以工作
```

如果错误地传入整数：

```python
save(123, "hello")
```

函数调用时不会因为缺少类型标注而立即拦截，但运行到：

```python
writer.write(text)
```

就会抛出 `AttributeError`，因为 `int` 没有 `.write()` 方法。

#### 无标注、`Any` 和明确标注的区别

```python
def first(value):            # 没写明预期类型
    ...

def second(value: Any):      # 明确告诉类型检查器跳过严格检查
    ...

def third(value: str):       # 明确说明预期是 str
    ...
```

| 写法 | 代码表达的意思 | Python 是否自动运行时校验 |
| --- | --- | --- |
| `value` | 没有提供类型信息 | 否 |
| `value: Any` | 明确放弃该值的大部分静态检查 | 否 |
| `value: str` | 预期传入字符串，便于阅读和静态检查 | 默认仍然不校验 |

因此，类型标注主要改善编辑器补全、静态检查和代码可读性，而不是让 Python 参数
获得一个强制的固定类型。

#### 语法允许省略，不代表所有框架场景都适合省略

普通函数可以不写标注，但有些框架会主动读取标注并用于数据校验或接口文档生成。
因此，语法上允许省略，不代表所有框架场景下省略后的行为都相同。

## 4. 列表、字典、元组、集合、索引和属性

### 4.1 Python 的 `dict` 相当于其他语言里的 Map

```python
return {
    "Parser": Parser,
    "Writer": Writer,
}
```

返回值是 Python 字典 `dict`，可以把它理解为 Java 等语言中的 Map：

```text
key                 value
"Parser"  ->  Parser 类对象
"Writer"  ->  Writer 类对象
```

读取字典：

```python
Parser = dependencies["Parser"]
```

这里不是创建类，而是从字典中取出之前保存的类对象，再赋给变量。

字典可以继续嵌套字典：

```python
config = {
    "configurable": {
        "session_id": "demo-1",
    }
}
```

读取内层值：

```python
session_id = config["configurable"]["session_id"]
```

`parameters`、`type`、`properties` 等字典 key 对 Python 本身没有特殊含义：

```python
schema = {
    "type": "object",
    "properties": {},
}
```

它们是否必须出现，由使用这份字典的代码约定，而不是由 Python 的字典语法规定。

### 4.2 中括号可能表示列表，也可能表示取值

创建列表：

```python
items = [object()]
```

即使只有一个元素，也需要中括号才能表示“这是一个列表”：

```python
one_object = object()
one_item_list = [object()]
```

在已有对象后使用中括号，则通常表示索引、切片或按 key 取值：

```python
items[0]             # 列表的第一个元素
messages[-1]         # 列表的最后一个元素
mapping["name"]      # 按字典 key 取值
text[:10000]         # 字符串切片
```

### 4.3 `objects[0].attribute` 分两步执行

```python
return users[0].name
```

执行顺序：

```python
first_user = users[0]
name = first_user.name
return name
```

- `[0]` 取列表第一个对象。
- `.name` 读取这个对象的属性。
- 最终返回属性值。

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
    "相邻的字符串字面量"
    "会被自动拼接。"
)
```

结果是一个字符串：

```python
"相邻的字符串字面量会被自动拼接。"
```

创建单元素元组必须有逗号：

```python
not_a_tuple = ("hello")
one_item_tuple = ("hello",)
```

### 4.6 `dict.items()` 和 `dict.values()` 返回什么

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

`values()` 只返回所有 value，不携带 key：

```python
score_values = scores.values()
# dict_values([0.91, 0.72])
```

它的类型是字典视图 `dict_values`，同样不是普通列表。遍历时每次直接得到一个 value：

```python
for score in scores.values():
    print(score)

# 0.91
# 0.72
```

需要普通列表时可以显式转换：

```python
score_list = list(scores.values())
# [0.91, 0.72]
```

对比：

| 调用 | 返回类型 | 遍历时每次得到 |
| --- | --- | --- |
| `mapping.items()` | `dict_items` | `(key, value)` 元组 |
| `mapping.values()` | `dict_values` | `value` |

`dict_items` 和 `dict_values` 都是动态视图，它们引用原字典。创建视图后再修改字典，之后查看视图时会反映新数据：

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

Python 标准库没有另外提供一个常用的 `HashMap` 或 `unordered_map` 容器。即使调用方
完全不关心顺序，仍然直接使用 `dict`，只是不依赖它的遍历顺序。

不同语言可以粗略对照为：

| 语言 | 常用 KV 映射 |
| --- | --- |
| Python | `dict` |
| Java | `HashMap`、`LinkedHashMap` |
| C++ | `unordered_map`、`map` |
| Go | `map` |

如果只需要不重复的元素、不需要 value，使用 `set`：

```python
unique_keys = {"a", "b"}
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

示例：

```python
return [
    (items_by_key[key], score)
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

第五步，使用 key 找到原始对象，再组成新的二元组：

```python
(items_by_key[key], score)
```

最终类型近似为：

```python
list[tuple[object, float]]
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
    item = items_by_key[key]
    result.append((item, score))

return result
```

这里有三个不同的 `key` 用法：

| 代码 | 含义 |
| --- | --- |
| `for key, score` | 名为 `key` 的循环变量 |
| `sorted(..., key=lambda ...)` | `sorted()` 的排序依据参数 |
| `items_by_key[key]` | 使用循环变量从字典取值 |

Python 的排序是稳定排序。如果两个 score 相同，它们会保持进入 `sorted()` 之前的相对顺序；这里也就是字典中的插入顺序。

如果 `scores` 中存在某个 key，但 `items_by_key` 中没有该 key：

```python
items_by_key[key]
```

会抛出 `KeyError`。

### 4.10 `dict.get()`、`setdefault()` 和 `pop()`

这三个方法都可以处理“key 可能不存在”的情况，但是否修改字典不同。

示例：

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

`get(key, default)` 的默认值只在 key 不存在时生效，不会校验已存在 value
的类型：

```python
{}.get("accepted", [])                       # []
{"accepted": ["chunk-1"]}.get("accepted", [])  # ["chunk-1"]
{"accepted": None}.get("accepted", [])     # None
{"accepted": "wrong"}.get("accepted", [])  # "wrong"
```

因此读取来自 Tool、JSON 或其他外部边界的数据时，可以再做类型收窄：

```python
accepted = artifact.get("accepted", [])
if not isinstance(accepted, list):
    accepted = []
```

第二步不是重复处理“key 缺失”，而是把 key 存在但值为 `None`、字符串、
字典等非 `list` 情况统一降级为空列表。

另一个例子：

```python
items_by_key.setdefault(key, item)
```

`setdefault(key, default)` 表示：

- key 已存在：返回旧值，不覆盖它。
- key 不存在：写入 `default`，然后返回这个默认值。

这里没有接收返回值，只利用了“key 第一次出现时保存默认值”的副作用。

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

#### `dict.update()` 把其他键值对写入当前字典

```python
update = {"messages": ["AIMessage"]}
update.update(
    {
        "active_query": "本地 Embedding 模型是什么？",
        "route": "retrieve",
    }
)
```

执行后，原来的 `update` 字典被原地修改为：

```python
{
    "messages": ["AIMessage"],
    "active_query": "本地 Embedding 模型是什么？",
    "route": "retrieve",
}
```

如果新键值对与旧字典存在同名 key，新值会覆盖旧值。`dict.update()` 的返回值是
`None`，因此通常先执行修改，再单独 `return update`：

```python
result = update.update({"route": "retrieve"})
result is None  # True
```

### 4.11 `set`、成员判断和保序去重

集合经常与列表配合进行保序去重：

```python
unique: list[str] = []
seen: set[str] = set()

for value in candidates:
    normalized = value.casefold().strip()
    if normalized in seen:
        continue
    seen.add(normalized)
    unique.append(value.strip())
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

不能只把结果放进 `set` 后再期待它保存首次出现顺序。

#### `set(字典)` 会把字典的 key 转成集合

字典直接参与遍历时默认遍历 key：

```python
mapping = {"a": 1, "b": 2}

set(mapping)          # {"a", "b"}
set(mapping.keys())   # {"a", "b"}，与上一行相同
set(mapping.values()) # {1, 2}
```

`set(mapping)` 会创建新集合，不会修改原字典。

#### 集合差集与 `sorted()`

```python
previous = {"a.md", "b.md"}
current = {"b.md", "c.md"}

missing = previous - current
# {"a.md"}，类型是 set[str]

ordered = sorted(missing)
# ["a.md"]，类型是 list[str]
```

集合差集有方向：

```python
previous - current  # {"a.md"}
current - previous  # {"c.md"}
```

`sorted()` 接收任意可迭代对象并返回一个新列表，不会修改原集合。

### 4.12 `list[list[str]]` 与两层索引

```python
groups: list[list[str]]
```

它表示：

- 外层列表：包含多组数据。
- 内层列表：每一组包含多个字符串。

例如：

```python
groups = [
    ["a", "b"],
    ["c", "d"],
]
```

两层索引的含义：

```python
groups[0]     # ["a", "b"]
groups[0][0]  # "a"
groups[1][1]  # "d"
```

`list[list[str]]` 只是描述两层列表的数据形状，不会自动排序或修改数据。

### 4.13 `[:4]`、`[:6]` 对列表同样是切片

```python
first_four = values[:4]
first_six = values[:6]
```

对列表使用 `[:N]` 会创建一个新列表，最多取得前 N 项：

```python
values = ["a", "b", "c", "d", "e"]

values[:3]  # ["a", "b", "c"]
values[:9]  # 不会报错，返回全部五项
```

它不会修改原列表。切片语法相同，但具体切的是字符、字节还是列表元素，取决于被切片对象的类型。

### 4.14 `range(start, stop, step)`、列表分片与分批生成器

```python
def batched(values: list[str], size: int = 100):
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
batched() 暂停
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
batches = batched(["a", "b", "c", "d", "e"], size=2)

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
all_batches = list(batched(["a", "b", "c", "d", "e"], size=2))

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
| `batched(values)` | 生成器对象 |
| 每次 `yield` 的值 | 一个一维小列表 |
| `list(batched(values))` | 由多个小列表组成的二维列表 |

调用方可以不先收集成二维列表，而是直接逐批消费：

```python
for batch in batched(values):
    consume(batch)
```

默认 `size=100`，因此每次最多产生 100 个元素，最后一批可以少于 100 个。
`size` 必须是非零整数；传入 `0` 时 `range()` 会抛出 `ValueError`。

### 4.15 `set.difference()` 与不可修改的 `frozenset`

```python
selected = {"a", "b", "c"}
excluded = frozenset({"a", "c"})
result = selected.difference(excluded)
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

如果需要直接修改普通 `set`，可以使用 `difference_update()`；`difference()` 则返回
新集合并保留原集合。

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

返回值类型取决于调用 `difference()` 的左侧对象：

```python
set({"a", "b"}).difference(frozenset({"a"}))
# {"b"}，类型是 set

frozenset({"a", "b"}).difference({"a"})
# frozenset({"b"})，类型是 frozenset
```

## 5. 字符串：文档字符串、切片、换行、拆分、规范化和正则清理

### 5.1 单独出现的三引号字符串可能是文档字符串

示例：

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

另一个例子：

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

示例：

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

链式调用可以连续提取两个标记之间的内容：

```python
content = text.partition("<tag>")[2].partition("</tag>")[0].strip()
```

分步写法：

```python
after_opening = text.partition("<tag>")[2]
before_closing = after_opening.partition("</tag>")[0]
content = before_closing.strip()
```

- 第一个 `[2]` 取得 `<tag>` 后面的内容。
- 第二个 `[0]` 取得 `</tag>` 前面的内容。
- `strip()` 删除最终结果首尾的空白。

与 `split(separator, 1)` 相比，`partition()` 会保留分隔符，并且无论是否找到都固定返回三个元素；`split()` 不保留分隔符，返回列表且长度可能不同。`rpartition()` 的规则相同，但从右侧最后一次出现的位置切分。分隔符不能为空字符串，否则会抛出 `ValueError`。

### 5.7 `splitlines()`、`casefold()` 和 `re.sub()`

```python
lines = text.splitlines()
normalized = value.casefold().strip()
```

`splitlines()` 按换行边界拆分字符串：

```python
"问题一\n问题二\n问题三".splitlines()
# ["问题一", "问题二", "问题三"]
```

它和 `split("\n")` 类似，但还能统一处理 `\r\n` 等不同系统的换行形式。

`casefold()` 返回适合做不区分大小写比较的新字符串：

```python
"Python".casefold() == "python".casefold()  # True
```

它不会修改原字符串。和 `lower()` 相比，`casefold()` 对部分非英语字符的大小写归一化更彻底，因此更适合作为去重 key。

`re.sub()` 可以使用正则替换文本：

```python
cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
```

`re.sub(pattern, replacement, text)` 表示把匹配到的内容替换掉。这里 replacement 是空字符串，所以是在删除行首编号：

```python
re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", "1. 第一项").strip()
# "第一项"
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

示例：

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

正则常量通常在模块导入时创建一次，之后重复使用：

```python
# 模块被导入时执行一次：创建 Pattern 对象
ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9_./-]+")
CJK_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")

# 函数每次被调用时：使用 Pattern 对象处理具体文本
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

如果匹配前先执行：

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
text = "Python_service/v1 示例文本-2026！"
normalized = text.lower()

ASCII_TOKEN_PATTERN.findall(normalized)
# ["python_service/v1", "-2026"]

CJK_RUN_PATTERN.findall(normalized)
# ["用中文检索"]
```

这两个模式分别提取英文、数字类片段和连续中文片段。

变量名写成全大写：

```python
ASCII_TOKEN_PATTERN
CJK_RUN_PATTERN
```

表示开发者约定“这个模块级变量定义后按常量使用，不要重新赋值”。
但 Python 没有真正的常量关键字，下面的代码在语法上仍然允许：

```python
ASCII_TOKEN_PATTERN = "changed"
```

因此“常量”描述的是变量的使用约定；`re.Pattern` 描述的是变量当前保存的对象
类型。

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

另一个例子：

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

### 6.4 集合推导式与 `any()`

集合推导式使用 `{}`，会自动去重：

```python
values = ["api", "id", "api", "name"]
result = {value for value in values if len(value) >= 3}
# {"api", "name"}
```

`any()` 接收一个可迭代对象，只要其中有一个真值就返回 `True`：

```python
any(character.isalnum() for character in "---")   # False
any(character.isalnum() for character in "/api/") # True
```

它会短路：遇到第一个真值后立即停止遍历；全部为假时才返回 `False`。

### 6.5 双层列表推导式 `flatten`

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

### 6.6 推导式默认保留遍历顺序

列表推导式会按照源数据的遍历顺序追加元素。只要输入结果本身是按请求顺序返回的，推导后的列表也会保持这个顺序。

### 6.7 生成器表达式与 `list.extend()`

```python
lines.extend(line.strip() for line in text.splitlines())
```

下面这一段：

```python
(line.strip() for line in text.splitlines())
```

是生成器表达式。它和列表推导式外形相似，但不会先创建完整列表，而是在遍历时逐项产生结果。

当生成器表达式是函数调用的唯一参数时，可以省略它自己的圆括号：

```python
lines.extend(line.strip() for line in text.splitlines())
```

`extend()` 会遍历收到的可迭代对象，把其中每一项追加到原列表：

```python
values = ["a"]
values.extend(["b", "c"])

# ["a", "b", "c"]
```

它与 `append()` 不同：

```python
values = [1]
values.append([2, 3])  # [1, [2, 3]]，把整个列表作为一项

values = [1]
values.extend([2, 3])  # [1, 2, 3]，逐项追加
```

`extend()` 会原地修改列表，通常返回 `None`。

### 6.8 `max()` 消费生成器并返回单个最大值

```python
best_relevance = max(
    (item[3] for item in candidates),
    default=0.0,
)
```

`(item[3] for item in candidates)` 是生成器表达式：它遍历 `candidates`，
逐项产生每个元素下标 `3` 对应的值，但不创建结果列表。`max()` 消费这些值，
最终返回其中一个最大值，而不是返回列表或生成器：

```python
values = [0.42, 0.76, 0.51]
max(value for value in values)  # 0.76
```

当可迭代对象为空时，普通 `max()` 会抛出 `ValueError`；传入
`default=0.0` 后则返回这个默认值：

```python
max((value for value in []), default=0.0)  # 0.0
```

## 7. 函数参数：逗号、默认值、`*`、`*args`、`**kwargs`、`**config`

### 7.1 函数参数之间的逗号只是分隔符

```python
def format_text(
    text: str,
    *,
    width: int = 80,
    uppercase: bool = False,
) -> str:
    ...
```

每个逗号把一个参数与下一个参数分开。多行写法和下面的单行写法语义相同：

```python
def format_text(text, *, width=80, uppercase=False):
    ...
```

最后一个参数后的逗号称为尾随逗号，便于以后新增参数和保持格式整齐。

### 7.2 单独的 `*`：后面必须使用参数名传值

签名中的：

```python
*,
width: int = 80,
uppercase: bool = False,
```

表示 `*` 后面的参数是“仅限关键字参数”：

```python
format_text(text, width=100, uppercase=True)  # 正确
format_text(text, 100, True)                  # TypeError
```

### 7.3 有默认值的参数可以不传

```python
def connect(
    host,
    port=443,
    timeout=30,
    secure=True,
):
    ...
```

因此可以只传前两个：

```python
connect("example.com")
```

没有显式传入的参数会使用默认值。也可以覆盖其中一部分：

```python
connect(
    "example.com",
    port=8443,
    timeout=10,
    secure=True,
)
```

Python 根据参数名匹配，不需要“自动识别多个 `int`”。

下面也是关键字参数，参数值恰好是一个列表：

```python
load_files(paths=["/data/"])
```

这里 `paths` 是参数名，`["/data/"]` 是传入的列表值。

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

示例：

```python
def load_dotenv(*_args, **_kwargs):
    return False
```

这里的函数接受任意位置参数和任意关键字参数，但不使用它们。变量名前的 `_` 表示“故意不用”的命名习惯。

### 7.6 调用函数时的 `**config` 是拆字典

```python
config = {
    "width": 100,
    "uppercase": True,
}

format_text(text, **config)
```

等价于：

```python
format_text(
    text,
    width=100,
    uppercase=True,
)
```

要求字典 key 与函数参数名一致。`**` 不会根据多个 `int` 自动猜参数。

定义和调用时的区别：

| 位置 | 写法 | 含义 |
| --- | --- | --- |
| 函数定义 | `def f(**kwargs)` | 收集关键字参数为字典 |
| 函数调用 | `f(**config)` | 把字典拆成关键字参数 |

### 7.7 类和函数本身也可以作为参数或返回值

```python
Formatter = dependencies["Formatter"]
formatter = build_formatter(Formatter)
```

字典中取出的是类对象。Python 中类和函数都可以保存、传参和返回：

```python
def build_formatter(formatter_class):
    return formatter_class(width=80)
```

流程是：

```text
传入 Formatter 类
    ↓
formatter_class 指向该类
    ↓
formatter_class(...) 调用类
    ↓
创建并返回实例
```

入参是“类对象”，返回值是“这个类创建的实例”，不是同一个对象。

函数也可以返回另一个可调用对象，先保存，再像普通函数一样调用：

```python
def get_writer():
    return print


writer = get_writer()       # 第一次调用：取得可调用对象
writer({"stage": "draft"})  # 第二次调用：调用 writer，并传入一个 dict
```

因此下面两行不是重复调用同一个函数：

```python
writer = get_stream_writer()
writer({"stage": "draft", "detail": "正在生成草稿"})
```

第一行调用 `get_stream_writer()` 并把返回的可调用对象保存到变量 `writer`；第二行才是
调用这个 `writer`。如果用类型标注表达，它近似于：

```python
from typing import Any, Callable


writer: Callable[[Any], None]
```

即接收一个任意对象作为参数，执行发送等操作，不靠返回值传递结果。

### 7.8 `lambda` 是匿名函数

```python
lambda value: str(value).strip()
```

它等价于：

```python
def generate(value):
    return str(value).strip()
```

另一个写法：

```python
lambda _: fixed_value
```

`_` 仍然会接收一个参数，但下划线表示“这个参数不使用”。无论传入什么，它都返回
外层已有的 `fixed_value`。

`lambda` 可以读取外层作用域中的变量，这称为闭包捕获。

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

```python
parser.add_argument(
    "--verbose",
    action="store_true",
)

parser.add_argument(
    "--format",
    choices=("text", "json"),
    default="text",
)
```

`add_argument()` 默认使用 `action="store"`：命令行出现选项后，读取它后面的一个值并
保存；`choices` 只负责限制允许的值：

```bash
python demo.py --format json     # args.format == "json"
python demo.py --format xml      # argparse 报错
python demo.py                   # args.format == "text"
```

`default="text"` 表示没有传 `--format` 时使用 `"text"`。

`action="store_true"` 是 `argparse` 规定的固定 action 名称。它把选项变成不带值的布尔开关：

```bash
python demo.py             # args.verbose is False
python demo.py --verbose   # args.verbose is True
```

不能写成 `--verbose true`，因为 `store_true` 本身不读取后续值。

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

示例：

```python
for rank, (item, score) in enumerate(matches, start=1):
    ...
```

假设：

```python
matches = [
    ("a", 0.91),
    ("b", 0.83),
]
```

`enumerate(matches, start=1)` 依次产生：

```python
(1, ("a", 0.91))
(2, ("b", 0.83))
```

循环变量进行了两层拆包：

```text
rank                 <- 1
(item, score)        <- ("a", 0.91)
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
for name, score in zip(names, scores):
    ...
```

每次从 `zip()` 取得一个二元组，再拆成 `name` 和 `score`。详细规则见第 2 节。

## 9. 条件判断：三元表达式、类型检查、属性检查和真假值

### 9.1 Python 的条件表达式

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

另一个例子：

```python
length = len(value) if hasattr(value, "__len__") else 0
```

也可以在条件为假时返回 `None`：

```python
cache = Cache() if use_cache else None
```

表示启用缓存时创建对象，否则使用 `None`。

条件表达式较长时可以放进圆括号中换行：

```python
active_value = (
    existing_value
    if existing_value is not None
    else build_value()
)
```

它等价于：

```python
if existing_value is not None:
    active_value = existing_value
else:
    active_value = build_value()
```

这里的圆括号只用于分组和换行，不是元组。Python 创建元组的关键是逗号，例如
`(existing_value,)`。

更一般地，只要一个表达式还位于 `()`、`[]` 或 `{}` 内，Python 就允许在合适的位置直接换行，这叫隐式续行，不需要在行尾添加 `\`：

```python
total = (
    first_value
    + second_value
    + third_value
)
```

条件表达式只执行被选中的分支。例如：

```python
result = load_value() if should_load else None
```

`should_load` 为假时不会调用 `load_value()`。空列表也可以直接作为条件：

```python
processed_count = process(items) if items else 0
```

```python
bool([])         # False
bool(["a", "b"]) # True
```

`processed_count = ...` 这个条件表达式等价于：

```python
if items:
    processed_count = process(items)
else:
    processed_count = 0
```

同一规则也适用于集合。`intersection()` 返回交集集合；空集合转换为 `bool` 是
`False`，非空集合转换为 `bool` 是 `True`：

```python
left = {"a", "b"}
right = {"b", "c"}

has_common = bool(left.intersection(right))
# bool({"b"}) -> True
```

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
hasattr(obj, "save")
```

表示检查 `obj` 是否有名为 `save` 的属性或方法，返回布尔值。

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
value = value or create_default()
```

如果原来的 `value` 是真值，就继续使用它；否则调用函数创建默认值。

```python
content = getattr(message, "content", "") or ""
```

如果属性不存在、为 `None` 或为空字符串，最终统一得到空字符串。

`or` 会短路：

```python
return not items or is_valid(items)
```

如果 `items` 为空：

```python
not items
# True
```

`or` 左侧已经是 `True`，Python 不再计算右侧，整个表达式直接返回 `True`。只有
`items` 非空、`not items` 为 `False` 时，才调用 `is_valid(items)`。

可以展开成普通 `if`：

```python
if not items:
    return True

return is_valid(items)
```

### 9.7 `continue` 跳过本次循环剩余代码

```python
if not item:
    continue
```

条件满足时，不再执行当前循环后面的语句，直接进入下一轮循环。

### 9.8 `try / except` 捕获异常

```python
try:
    import optional_package
except ImportError:
    optional_package = None
```

含义是：

1. 尝试导入依赖。
2. 如果发生 `ImportError`，执行后备赋值。

下面的写法会保留原异常链：

```python
except ImportError as exc:
    raise RuntimeError("缺少依赖") from exc
```

排错时既能看到新的异常，也能看到最初的导入错误。

### 9.9 自定义异常继承、`raise` 与父类捕获

```python
class TransientDependencyError(ConnectionError):
    """表示暂时性的依赖连接错误。"""
```

`ConnectionError` 是 Python 内置异常类，继承关系是：

```text
ConnectionError → OSError → Exception → BaseException → object
```

上面的 `class` 语句只定义一个新的异常类型，不会立即抛出异常。下面这句也只是创建异常对象：

```python
error = TransientDependencyError("temporary failure")
```

真正中断当前正常执行流程的是 `raise`：

```python
raise TransientDependencyError("temporary failure")
```

执行到 `raise` 后，当前函数不会继续执行后面的 `return`，异常会沿调用栈向上传递，直到被
匹配的 `except` 或框架错误处理机制捕获；始终无人处理时，程序打印 traceback 并以失败状态
结束。

因为子类对象也是父类对象，所以既可以精确捕获自定义类型，也可以通过父类统一捕获：

```python
try:
    raise TransientDependencyError("temporary failure")
except ConnectionError as error:
    print(type(error).__name__)  # TransientDependencyError
```

对应关系为：

```python
issubclass(TransientDependencyError, ConnectionError)  # True
isinstance(error, TransientDependencyError)             # True
isinstance(error, ConnectionError)                      # True
isinstance(error, OSError)                              # True
```

自定义子类的价值是让调用者既能只处理这一种具体故障，也能在需要时按更宽泛的连接错误统一
处理。继承关系本身不决定是否重试；重试、记录、转换或继续抛出由调用方的控制逻辑决定。

## 10. 类、对象、方法、默认工厂和装饰器

### 10.1 `__init__` 在创建实例时初始化属性

```python
class User:
    def __init__(self, name: str):
        self.name = name
```

使用：

```python
user = User("Alice")
```

Python 创建对象时直接调用类，不需要 Java 风格的 `new` 关键字。

执行过程：

1. 创建 `User` 实例。
2. 自动调用 `__init__(self, "Alice")`。
3. 把名字保存到当前实例的 `self.name` 属性。

`self` 代表当前对象本身。

### 10.2 单下划线开头是内部使用的命名约定

```python
def _normalize(self, text: str):
    ...
```

单下划线表示“这是类或模块内部使用的实现细节”。它不是强制私有，外部仍然可以调用：

```python
processor._normalize("text")
```

但通常建议外部使用公开方法：

```python
processor.normalize("text")
```

### 10.3 `@dataclass(frozen=True)` 是装饰器

```python
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class Point:
    x: int
    y: int
```

`@dataclass(...)` 会处理紧随其后的类，自动生成常用方法，例如 `__init__`、`__repr__` 和 `__eq__`。

`frozen=True` 表示实例创建后不允许普通字段重新赋值：

```python
point = Point(x=2, y=3)
point.x = 4  # FrozenInstanceError
```

`frozen=True` 阻止字段重新赋值，但如果字段本身保存可变对象，它不会自动把该对象
递归变成不可变对象。

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

#### `asdict()` 是 dataclasses 模块函数

```python
payload = asdict(point)
# {"x": 2, "y": 3}
```

`asdict()` 是 `dataclasses` 模块函数，不是实例自带的方法；它会递归转换嵌套的
dataclass，并返回一个新字典。

#### 类名、参数名和实例属性是三个不同名称

```python
class Config:
    pass

class Service:
    def __init__(self, config: Config):
        self.config = config
```

- `Config` 是类。
- `config` 是参数变量。
- `self.config` 是当前实例的属性。

类型标注不会创建或转换对象。`self.config = config` 只是把参数当前指向的对象保存到
实例属性中：

```python
config = Config()
service = Service(config)
service.config is config  # True
```

### 10.4 `@property` 把无参数方法变成只读式属性

```python
class Rectangle:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height

    @property
    def area(self) -> int:
        return self.width * self.height
```

调用方读取 property 时不写括号：

```python
rectangle = Rectangle(3, 4)
rectangle.area    # 12
rectangle.area()  # TypeError：前一次属性访问已经得到 int
```

这里没有缓存结果；每次读取 `rectangle.area` 都会重新执行方法体。

### 10.5 `对象.属性 = 值` 是属性赋值

```python
conn.row_factory = sqlite3.Row
```

这不是定义局部变量，而是把 `sqlite3.Row` 保存到 `conn` 对象的 `row_factory` 属性中。

### 10.6 `@classmethod` 与 `cls`

```python
class User:
    def __init__(self, name: str):
        self.name = name

    @classmethod
    def guest(cls):
        return cls(name="guest")
```

`@classmethod` 把方法绑定到类，而不是绑定到某个实例。调用时不需要手动传入 `cls`：

```python
user = User.guest()
```

Python 会自动把 `User` 作为第一个参数 `cls`。接近底层函数的概念形式是：

```python
User.guest.__func__(User)
```

方法内部的：

```python
return cls(name="guest")
```

表示调用当前类创建实例。与三种常见方法对比：

| 方法 | 第一个自动参数 | 常见调用方式 |
| --- | --- | --- |
| 普通实例方法 | `self`，当前实例 | `obj.method()` |
| `@classmethod` | `cls`，当前类 | `ClassName.method()` |
| `@staticmethod` | 没有自动参数 | `ClassName.method()` |

`cls` 和 `self` 都不是 Python 关键字，但属于应当遵守的惯用命名。

### 10.7 可变默认值与 `default_factory=list`

```python
from dataclasses import dataclass, field

@dataclass
class Group:
    people: list[str] = field(default_factory=list)
```

这里传入的是 `list` 函数对象，没有写 `list()`。每次创建 `Group` 时，dataclass 都会
调用它创建一个新列表：

```text
创建第一个 Group → 调用 list() → 得到列表 A
创建第二个 Group → 调用 list() → 得到列表 B
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

核心规则是：需要“每次创建一个新对象”时传工厂函数，不要提前调用并保存同一个可变对象。

### 10.8 一个实例方法可以通过 `self` 调用另一个实例方法

```python
class TextProcessor:
    def _normalize(self, text: str) -> str:
        return text.strip().lower()

    def normalize(self, text: str) -> str:
        return self._normalize(text)

    def normalize_all(self, texts: list[str]) -> list[str]:
        return [self.normalize(text) for text in texts]
```

`self.normalize(text)` 是普通的实例方法调用，Python 会把当前实例自动传给
`normalize()` 的 `self` 参数。列表推导式最终收集成 `list[str]`。

## 11. Python 包、模块、导入和依赖字典

### 11.1 包层级怎么读

```python
from package.subpackage.module import ClassName
```

从左到右：

```text
package                  顶层包
└── subpackage           子包
    └── module           模块
        └── ClassName    导入的类
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
from pathlib import Path as FilePath
```

`as` 可以在当前文件中使用别名。

### 11.3 相对导入、绝对导入与 `python -m`

假设目录结构是：

```text
my_package/
├── __init__.py
├── helpers.py
└── main.py
```

`main.py` 中可以使用相对导入：

```python
from .helpers import build
```

开头的 `.` 表示当前包。通常使用模块方式启动：

```bash
python -m my_package.main
```

`-m` 后面写点分模块名，不写 `/` 和 `.py`。直接运行：

```bash
python my_package/main.py
```

时通常没有父包上下文，因此相对导入可能报
`attempted relative import with no known parent package`。正式包最好统一一种启动方式，
避免用宽泛的 `except ImportError` 掩盖模块内部真正的依赖错误。

### 11.4 函数内部导入是延迟导入

```python
def load_dependencies():
    from pathlib import Path
    return {"Path": Path}
```

只有调用 `load_dependencies()` 时才执行导入。常见用途包括：

- 把可选依赖集中处理。
- 导入失败时给出更清楚的错误。
- 避免仅仅导入当前文件就立刻加载所有重依赖。

每次调用函数都会执行到其中的 `import` 语句，但 Python 通常会从 `sys.modules`
缓存中复用已经导入的模块，不会每次重新加载整个包。

### 11.5 类和函数也可以作为字典的值

```python
class Item:
    pass

dependencies = {"Item": Item}
item_class = dependencies["Item"]
item = item_class()
```

执行过程：

```text
字典保存 Item 类
    ↓
按 key 取出类对象
    ↓
调用类对象创建实例
```

变量可以指向普通值，也可以指向函数或类。

### 11.6 `__all__` 声明模块的公开导出名称

```python
__all__ = [
    "Evidence",
    "LocalKnowledgeRetriever",
    "RetrievalBundle",
    "relevant_quote",
]
```

`__all__` 是一个由名称字符串组成的特殊模块级变量，主要控制：

```python
from local_rag_adapter import *
```

这条通配符导入语句只会导入 `__all__` 列出的名称。如果没有 `__all__`，
Python 默认导入模块中所有不以 `_` 开头的全局名称，可能把 `Path`、
`dataclass` 等仅供模块内部使用的导入也意外暴露出去。

`__all__` 表达的是“推荐的公开 API”，不是访问权限。即使某个名称没有列在
`__all__` 中，仍然可以显式导入：

```python
from local_rag_adapter import _preview
```

所以它不会把 `_preview` 变成真正的私有函数，只是让通配符导入、IDE、
文档工具和模块使用者更清楚地知道哪些名称是稳定对外接口。普通代码仍建议
使用显式导入，而不是 `import *`。

## 12. `Path`、`__file__` 和路径拼接

### 12.1 `__file__` 是当前 Python 文件的路径

示例：

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
/project/package/module.py
```

那么：

```text
parents[0] = /project/package
parents[1] = /project
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

```python
text = path.read_text(encoding="utf-8", errors="replace").strip()
```

假设 `path` 当前是：

```python
Path("data/example.md")
```

这一行读作：

> 让 `path` 这个 `Path` 对象用 UTF-8 编码读取文件；遇到不能按 UTF-8
> 解码的字节时，用替代字符代替；读取完成后，再删除文本首尾的空白字符。

方法签名可以简化理解为：

```python
Path.read_text(self, encoding=None, errors=None)
```

参数对应关系：

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

```python
path = Path("runtime/cache")
path.mkdir(parents=True, exist_ok=True)
```

这表示创建目标目录；缺少的父目录也一起创建；如果目录已经存在则继续执行。

两个参数分别表示：

| 参数 | 含义 |
| --- | --- |
| `parents=True` | 父目录不存在时递归创建父目录 |
| `exist_ok=True` | 目标目录已经存在时不抛出 `FileExistsError` |

例如：

```python
path = Path("runtime/cache")
result = path.mkdir(parents=True, exist_ok=True)

print(result)
# None
```

`mkdir()` 会产生文件系统副作用，正常完成时返回 `None`。它不会清空已经存在的目录。

`exist_ok=True` 只表示“目录已经存在可以接受”。如果目标路径已经是普通文件、父目录
没有写权限或磁盘发生错误，仍然会抛出相应异常。

### 12.5 `Path.rglob("*")` 递归查找目录内容

```python
for path in sorted(source_dir.rglob("*")):
```

其中：

```python
source_dir.rglob("*")
```

读作：

> 从 `source_dir` 目录开始，递归查找它下面所有层级中名称符合 `"*"`
> 的路径项。

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
- 它返回惰性迭代结果，不是已经装好全部结果的 `list`。
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

可以使用 `sorted()` 收集并排序，再通过 `continue` 跳过目录：

```python
found_paths = source_dir.rglob("*")  # generator[Path]
sorted_paths = sorted(found_paths)   # 消耗 generator，得到排序后的 list[Path]

for path in sorted_paths:
    if not path.is_file():
        continue
    print(path)
```

`path.is_file()` 判断是否为普通文件；`continue` 会跳过当前循环剩余代码。

### 12.6 `relative_to().as_posix()` 生成相对路径字符串

```python
relative_text = path.relative_to(base_dir).as_posix()
```

这条链式调用分两步执行。假设：

```python
base_dir = Path("/project/data")
path = Path("/project/data/manual/setup.md")
```

第一步：

```python
relative_path = path.relative_to(base_dir)
```

得到：

```python
Path("manual/setup.md")
```

`relative_to(base_dir)` 的意思是：

> 以 `base_dir` 为起点，计算 `path` 位于它下面的相对路径。

可以从理解效果的角度把它看成删除共同的目录前缀：

```text
完整路径：/project/data/manual/setup.md
起点目录：/project/data
相对结果：              manual/setup.md
```

但它不是普通的字符串替换，而是按照路径层级计算。如果 `path` 不在
`base_dir` 里面，`relative_to()` 会抛出 `ValueError`。

第二步：

```python
relative_text = relative_path.as_posix()
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

这段链式调用可以拆成：

```python
relative_path = path.relative_to(base_dir)   # Path
relative_text = relative_path.as_posix()     # str
```

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

示例：

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
    yield text
```

`async for` 每次异步等待下一项，适合网络流、音频流、模型流式输出等不能一次性得到全部数据的场景。

### 13.6 `str` 与 `bytes`

```python
encoded = word.encode()   # str -> bytes
decoded = encoded.decode() # bytes -> str
b" "                     # bytes 字面量
```

文本处理通常使用 `str`，网络、文件或音频等原始二进制数据经常使用 `bytes`。

### 13.7 同步方法不能把异步方法的协程当成结果

是否异步由定义时的 `async def` 决定：

```python
def get_value(self, text: str) -> str:
    return self._get(text)             # 同步，直接得到结果

async def aget_value(self, text: str) -> str:
    ...                                # 异步，调用后先得到协程
```

因此下面的同步实现有问题：

```python
def get_many(self, texts: list[str]) -> list[str]:
    return [self.aget_value(text) for text in texts]
```

列表中装入的是协程对象，不是 `str`。同步版本应调用同步方法：

```python
def get_many(self, texts: list[str]) -> list[str]:
    return [self.get_value(text) for text in texts]
```

异步批量版本才使用 `await`：

```python
async def aget_many(self, texts: list[str]) -> list[str]:
    return await asyncio.gather(
        *(self.aget_value(text) for text in texts)
    )
```

方法名开头的 `a` 只是常见命名约定；真正的判断标准仍然是它是否由 `async def` 定义。

## 14. `with`、`@contextmanager`、资源管理和回调注册

### 14.1 `with` 使用上下文管理器自动收尾

`with` 会在进入代码块时获取资源，并在离开时执行清理。即使代码块中发生异常，也会调用上下文管理器的退出逻辑。

数据库连接、文件和锁都经常使用 `with`：

```python
with open("data.txt", encoding="utf-8") as file:
    content = file.read()
```

#### `with threading.RLock()` 自动加锁和释放锁

```python
import threading

self._lock = threading.RLock()

with self._lock:
    result = update_shared_state()
```

进入 `with` 时调用锁的 `acquire()`，离开代码块时调用 `release()`。它等价于：

```python
self._lock.acquire()
try:
    result = update_shared_state()
finally:
    self._lock.release()
```

因此即使 `update_shared_state()` 抛出异常，锁也会在 `finally` 阶段释放，避免其他
线程一直无法进入临界区。拿到锁的线程执行 `with` 内部代码时，使用同一个锁的其他
线程会等待。

`with lock:` 使用默认的阻塞式获取锁，没有内置等待超时。锁被其他线程持有时，
当前线程不会直接返回，而是一直等待到锁可用。若业务需要限制等待时间，需要显式
调用 `acquire(timeout=...)`：

```python
acquired = self._lock.acquire(timeout=5.0)
if not acquired:
    raise TimeoutError("等待锁超过 5 秒")

try:
    result = update_shared_state()
finally:
    self._lock.release()
```

这个锁等待超时与 HTTP 请求超时、数据库超时、模型调用超时是相互独立的配置。

`RLock` 中的 `R` 表示 reentrant（可重入）：同一个线程已经持有该锁时，可以再次
获取同一把锁；每次获取都必须有对应的释放。普通 `threading.Lock` 不支持同一线程
重复获取。

这种锁只协调同一 Python 进程中共享同一个锁对象的线程。不同服务实例如果分别创建
自己的 `RLock`，或者程序运行在多个进程/多个服务副本中，它们不会被这把锁互斥；
这时需要文件锁、数据库锁或分布式锁等跨进程协调机制。

### 14.2 `@contextmanager`、`yield` 和 `finally`

```python
from contextlib import contextmanager

@contextmanager
def open_text(path):
    file = open(path, encoding="utf-8")
    try:
        yield file
    finally:
        file.close()
```

调用：

```python
with open_text("data.txt") as file:
    content = file.read()
```

执行顺序是：

```text
运行 yield 之前的代码，打开文件
    ↓
yield file，把文件对象交给 as file
    ↓
执行 with 代码块
    ↓
离开 with 后，从 yield 下一行继续
    ↓
执行 finally，关闭文件
```

`yield` 在这里既交出资源，也标记“进入”和“退出”两个阶段的分界。`finally` 保证即使
`with` 代码块抛出异常，也会执行 `file.close()`。

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
.venv/bin/python app.py
```

否则会出现 `SyntaxError` 或 `IndentationError`，因为 Python 在尝试把 shell 命令解析成 Python 语法。

### 15.2 正确运行脚本

先离开 REPL：

```python
exit()
```

回到类似下面的终端提示符：

```text
user@host:~/project$
```

再执行：

```bash
.venv/bin/python app.py
```

### 15.3 `venv` 是虚拟环境工具，不是 Python 语法

虚拟环境为项目提供独立的 Python 解释器和依赖目录，避免不同项目之间的包版本互相影响。

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 16. Python `dict/list` 与 JSON 的区别

### 16.1 Python 对象还不是 JSON 字符串

```python
result = {
    "name": "Alice",
    "items": [],
    "active": True,
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
  "name": "Alice",
  "items": [],
  "active": true,
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

### 16.2 `json.loads()` 把 JSON 字符串解析成 Python 对象

```python
raw_arguments = '{"location": "Boston"}'
arguments = json.loads(raw_arguments)
```

这里的 JSON 最外层是对象 `{...}`，所以结果是 Python `dict`：

```python
{"location": "Boston"}
```

但 `json.loads()` 并不是固定返回 `dict`。它会根据 JSON 最外层的数据类型，返回对应的 Python 对象：

| JSON 最外层类型 | 示例 | Python 返回类型 |
| --- | --- | --- |
| object | `{"name": "Alice"}` | `dict` |
| array | `[1, 2, 3]` | `list` |
| string | `"hello"` | `str` |
| number | `1` / `1.5` | `int` / `float` |
| boolean | `true` / `false` | `bool` |
| null | `null` | `None` |

例如：

```python
type(json.loads('{"name": "Alice"}'))  # dict
type(json.loads('[1, 2, 3]'))          # list
```

下面这行代码分两步执行：

```python
payload = json.loads(path.read_text(encoding="utf-8"))
```

等价于：

```python
text = path.read_text(encoding="utf-8")  # 先读取文件，得到 str
payload = json.loads(text)               # 再解析 JSON，得到对应的 Python 对象
```

因此，只有当文件内容最外层是 `{...}` 时，`payload` 才是 `dict`；如果最外层是 `[...]`，它就是 `list`。

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
| `[]` | `items[0]` | 索引取值 |
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
| `*` | `[first, *values]` | 在列表字面量中逐项展开可迭代对象 |
| `**` | `def f(**kwargs)` | 收集关键字参数 |
| `**` | `f(**config)` | 拆开字典作为关键字参数 |
| `|` | `str | None` | 联合类型 |
| `|` | `{1, 2} | {2, 3}` | 集合并集 |
| `/` | `10 / 2` | 数值除法 |
| `/` | `Path("a") / "b"` | `Path` 重载后的路径拼接 |

### 17.2 `|` 的含义取决于两侧对象

```python
str | None                  # 联合类型
{1, 2} | {2, 3}             # 集合并集：{1, 2, 3}
{"a": 1} | {"b": 2}         # 字典合并：{"a": 1, "b": 2}
```

Python 运算符会根据两侧对象的类型执行不同操作；自定义类也可以通过特殊方法重载
运算符。

### 17.3 列表字面量中的 `*` 解包

```python
messages = ["用户消息", "工具消息"]
combined = ["系统消息", *messages]

# 等价结果：
# ["系统消息", "用户消息", "工具消息"]
```

`*messages` 会把 `messages` 中的元素逐项放入新列表，并且不会修改原列表。它近似
等价于：

```python
combined = ["系统消息"] + messages
```

如果不写 `*`：

```python
nested = ["系统消息", messages]
# ["系统消息", ["用户消息", "工具消息"]]
```

此时第二项是完整的子列表，结构变成了嵌套列表。

## 18. 语法速查

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

Model | None = None
    参数类型可为 Model 或 None，默认值是 None

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

for rank, (item, score) in enumerate(..., start=1)
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

list[list[str]]
    二维列表；外层和内层元素类型都通过泛型标注表达

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

def get_value(...) / async def aget_value(...)
    前者直接返回结果；后者调用后先返回协程，必须 await 才得到结果

Python REPL 的 >>>
    只能输入 Python；source 和脚本启动命令应在 shell 中执行
```
