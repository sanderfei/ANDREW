from L1_guidelines import get_completion


lamp_review = """
我需要一盏适合卧室的漂亮台灯，
这款不仅带有额外收纳空间，价格也不算太高。
到货很快。
运输过程中，台灯的拉绳坏了，
商家公司很爽快地寄来了一个新的，
几天内也送到了。
组装起来很简单。
我还少了一个零件，于是联系了他们的客服，
他们很快就把缺失的零件寄给了我！
在我看来，Lumina 是一家很棒的公司，
很关心他们的客户和产品！
"""


prompt = f"""
下面是一条由三个反引号分隔的产品评论。
这条产品评论的情感倾向是什么？

评论文本：```{lamp_review}```
"""
response = get_completion(prompt)
print(response)


prompt = f"""
下面是一条由三个反引号分隔的产品评论。
这条产品评论的情感倾向是什么？

请只用一个词回答：“正面”或“负面”。

评论文本：```{lamp_review}```
"""
response = get_completion(prompt)
print(response)


prompt = f"""
识别下面评论作者正在表达的情绪。
列表最多包含 5 项。
请把答案格式化为用逗号分隔的小写中文词语列表。

评论文本：```{lamp_review}```
"""
response = get_completion(prompt)
print(response)


prompt = f"""
下面是一条由三个反引号分隔的评论。
评论作者是否正在表达愤怒？
请回答“是”或“否”。

评论文本：```{lamp_review}```
"""
response = get_completion(prompt)
print(response)


prompt = f"""
请从评论文本中识别以下信息：
- 评论者购买的商品
- 制造该商品的公司

评论由三个反引号分隔。
请将响应格式化为 JSON 对象，
并使用 "Item" 和 "Brand" 作为键。
如果信息不存在，请使用 "unknown" 作为值。
请让响应尽可能简短。

评论文本：```{lamp_review}```
"""
response = get_completion(prompt)
print(response)


prompt = f"""
请从评论文本中识别以下信息：
- 情感倾向（正面或负面）
- 评论者是否正在表达愤怒（true 或 false）
- 评论者购买的商品
- 制造该商品的公司

评论由三个反引号分隔。
请将响应格式化为 JSON 对象，
并使用 "Sentiment", "Anger", "Item", "Brand" 作为键。
如果信息不存在，请使用 "unknown" 作为值。
请让响应尽可能简短。
请将 Anger 的值格式化为布尔值。

评论文本：```{lamp_review}```
"""
response = get_completion(prompt)
print(response)


story = """
在最近一次由政府开展的调查中，
公共部门员工被要求评价他们对所在部门的满意度。
结果显示，NASA 是最受欢迎的部门，满意度达到 95%。

一位 NASA 员工 John Smith 对调查结果发表评论说：
“NASA 名列第一并不让我意外。
这里是一个很棒的工作场所，有优秀的人和难得的机会。
我很自豪能成为这样一个创新组织的一员。”

NASA 管理团队也对结果表示欢迎。
主管 Tom Johnson 表示：
“听到员工对他们在 NASA 的工作感到满意，我们非常高兴。
我们拥有一支才华出众、敬业投入的团队，
他们不知疲倦地努力实现目标，
看到他们的努力获得回报非常令人欣慰。”

调查还显示，社会保障署的满意度最低，
只有 45% 的员工表示对自己的工作满意。
政府承诺将处理员工在调查中提出的担忧，
并努力提高所有部门的工作满意度。
"""


prompt = f"""
判断下面由三个反引号分隔的文本中正在讨论的 5 个主题。

每个主题使用 1 到 2 个词。

请将响应格式化为用逗号分隔的主题列表。

文本样本：```{story}```
"""
response = get_completion(prompt)
print(response)


print(response.split(sep=","))


topic_list = [
    "nasa",
    "local government",
    "engineering",
    "employee satisfaction",
    "federal government",
]


prompt = f"""
判断下面主题列表中的每一项，
是否是下方由三个反引号分隔的文本中的主题。

请每行输出一个主题，格式必须是：
topic: 0
或：
topic: 1

0 表示不是主题，1 表示是主题。

主题列表：{", ".join(topic_list)}

文本样本：```{story}```
"""
response = get_completion(prompt)
print(response)


topic_dict = {}
for item in response.splitlines():
    if ": " not in item:
        continue
    topic, value = item.split(": ", 1)
    topic_dict[topic.strip()] = int(value.strip())

if topic_dict.get("nasa") == 1:
    print("提醒：出现新的 NASA 新闻！")
