from difflib import unified_diff

from L1_guidelines import get_completion


prompt = f"""
请将下面的英文文本翻译成西班牙语：
```Hi, I would like to order a blender```
"""
response = get_completion(prompt)
print(response)


prompt = f"""
告诉我下面这句话是什么语言：
```Combien coûte le lampadaire?```
"""
response = get_completion(prompt)
print(response)


prompt = f"""
请将下面的文本翻译成法语、西班牙语和英文海盗风格：
```I want to order a basketball```
"""
response = get_completion(prompt)
print(response)


prompt = f"""
请将下面的文本分别翻译成正式和非正式两种西班牙语表达：
'Would you like to order a pillow?'
"""
response = get_completion(prompt)
print(response)


user_messages = [
    "La performance du système est plus lente que d'habitude.",  # 系统性能比平时更慢。
    "Mi monitor tiene píxeles que no se iluminan.",  # 我的显示器有些像素点不亮。
    "Il mio mouse non funziona",  # 我的鼠标不能工作。
    "Mój klawisz Ctrl jest zepsuty",  # 我的 Ctrl 键坏了。
    "我的屏幕在闪烁",  # 我的屏幕在闪烁。
]


for issue in user_messages:
    prompt = f"告诉我下面这段文本是什么语言：```{issue}```"
    lang = get_completion(prompt)
    print(f"原始消息（{lang}）：{issue}")

    prompt = f"""
    请将下面的文本翻译成英语和韩语：
    ```{issue}```
    """
    response = get_completion(prompt)
    print(response, "\n")


prompt = f"""
请把下面的口语化表达改写成商务信函：
'Dude, This is Joe, check out this spec on this standing lamp.'
"""
response = get_completion(prompt)
print(response)


data_json = {
    "餐厅员工": [
        {"name": "Shyam", "email": "shyamjaiswal@gmail.com"},
        {"name": "Bob", "email": "bob32@gmail.com"},
        {"name": "Jai", "email": "jai87@gmail.com"},
    ]
}

prompt = f"""
请将下面这个 Python 字典从 JSON 结构转换为 HTML 表格，
表格需要包含列标题和标题：{data_json}
"""
response = get_completion(prompt)
print(response)


text = [
    "The girl with the black and white puppies have a ball.",  # 应为 has。
    "Yolanda has her notebook.",  # 正确。
    "Its going to be a long day. Does the car need it’s oil changed?",  # 同音词。
    "Their goes my freedom. There going to bring they’re suitcases.",  # 同音词。
    "Your going to need you’re notebook.",  # 同音词。
    "That medicine effects my ability to sleep. Have you heard of the butterfly affect?",  # 同音词。
    "This phrase is to cherck chatGPT for speling abilitty",  # 拼写。
]
for t in text:
    prompt = f"""
    请校对并修正下面的英文文本，
    然后重写修正后的版本。
    如果没有发现错误，只需说“No errors found”。
    不要在文本外添加任何标点符号：
    ```{t}```
    """
    response = get_completion(prompt)
    print(response)


text = f"""
Got this for my daughter for her birthday cuz she keeps taking
mine from my room. Yes, adults also like pandas too. She takes
it everywhere with her, and it's super soft and cute. One of the
ears is a bit lower than the other, and I don't think that was
designed to be asymmetrical. It's a bit small for what I paid for it
though. I think there might be other options that are bigger for
the same price. It arrived a day earlier than expected, so I got
to play with it myself before I gave it to my daughter.
"""
prompt = f"请校对并修正下面这条英文评论：```{text}```"
response = get_completion(prompt)
print(response)


diff = unified_diff(
    text.splitlines(),
    response.splitlines(),
    fromfile="原文",
    tofile="修正版",
    lineterm="",
)
print("\n".join(diff))


prompt = f"""
请校对并修正下面这条英文评论，让它更有吸引力。
确保它符合 APA 风格指南，并面向高阶读者。
请使用 Markdown 格式输出。

文本：```{text}```
"""
response = get_completion(prompt)
print(response)
