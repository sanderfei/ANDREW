import json

import requests

API_KEY = "sk-lLKjavEquIsN4nk6eguOXFlhBXbXntGLHo5tOhbQWkBztYbj"
API_URL = "https://ai-hub.digiwincloud.com.cn/v1/chat/completions"
MODEL = "ep-cl-glm-5.1"
DEBUG = False


def get_completion(
    prompt,
    system_prompt="你是一个乐于助人的助手。",
    temperature=0,
    max_tokens=2000,
):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    return get_completion_from_messages(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def get_completion_from_messages(messages, temperature=0, max_tokens=2000):
    if not API_KEY:
        raise RuntimeError("API_KEY 为空。")

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if DEBUG:
        print("请求载荷：")
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    response = requests.post(API_URL, headers=headers, json=payload, timeout=180)
    if response.status_code >= 400:
        print("响应状态码：")
        print(response.status_code)
        print("响应内容：")
        print(response.text)
        response.raise_for_status()

    data = response.json()
    if DEBUG:
        print("响应数据：")
        print(json.dumps(data, ensure_ascii=False, indent=2))

    return data["choices"][0]["message"]["content"]


def main():
    text = f"""
写提示词时，应该尽可能清楚、具体地表达你希望模型完成什么任务。
清晰的指令可以引导模型朝着你期望的方向输出，
也能减少模型给出无关回答或错误回答的概率。
不要把“清晰的提示词”误解成“很短的提示词”。
很多时候，稍微长一点的提示词可以提供更多上下文，
反而能让模型生成更详细、更相关的内容。
"""
    prompt = f"""
请把三个反引号包裹的文本总结成一句中文。
```{text}```
"""
    response = get_completion(prompt)
    print(response)

    prompt = f"""
生成三个虚构的书名，附上它们的作者和类型。
请使用 JSON 格式返回，并包含以下键：
book_id, title, author, genre。
"""
    response = get_completion(prompt)
    print(response)

    text_1 = f"""
泡一杯茶很简单！首先，你需要把一些水烧开。
在烧水的时候，拿一个杯子，并把茶包放进去。
等水足够热以后，直接把水倒在茶包上。
让它静置一会儿，这样茶就能充分浸泡。
几分钟后，把茶包取出来。
如果你喜欢，可以按口味加入糖或牛奶。
就这样！你就得到了一杯可以享用的美味茶饮。
"""
    prompt = f"""
你将收到一段由三个双引号分隔的文本。
如果它包含一系列说明，请按以下格式重写这些说明：

步骤 1 - ...
步骤 2 - ...
...
步骤 N - ...

如果文本不包含一系列说明，则只需写：“未提供步骤。”

\"\"\"{text_1}\"\"\"
"""
    response = get_completion(prompt)
    print("文本 1 的完成结果：")
    print(response)

    text_2 = f"""
今天阳光明媚，鸟儿在歌唱。
这是一个去公园散步的美好日子。
花儿正在盛开，树木在微风中轻轻摇曳。
人们都外出活动，享受这宜人的天气。
有些人在野餐，有些人在玩游戏，
也有人只是躺在草地上放松。
这是一个适合在户外度过、
并欣赏自然之美的完美日子。
"""
    prompt = f"""
你将收到一段由三个双引号分隔的文本。
如果它包含一系列说明，请按以下格式重写这些说明：

步骤 1 - ...
步骤 2 - ...
...
步骤 N - ...

如果文本不包含一系列说明，则只需写：“未提供步骤。”

\"\"\"{text_2}\"\"\"
"""
    response = get_completion(prompt)
    print("文本 2 的完成结果：")
    print(response)

    prompt = f"""
你的任务是以一致的风格作答。

<孩子>：教我理解耐心。

<祖辈>：能够冲刷出最深山谷的河流，
源自一眼不起眼的泉水；
最宏大的交响乐，
始于一个单独的音符；
最精巧的织锦，
始于一根孤独的丝线。

<孩子>：教我理解韧性。
"""
    response = get_completion(prompt)
    print(response)

    text = f"""
在一个迷人的村庄里，兄妹杰克和吉尔出发去山顶的井里打水。
他们一边欢快地唱着歌，一边向上攀登，却不幸遭遇意外：
杰克被一块石头绊倒，滚下了山坡，吉尔也跟着摔了下去。
虽然两人受了点轻伤，但他们回到家后得到了温暖的拥抱。
尽管发生了这场小意外，他们的冒险精神并没有减弱，
依然满怀喜悦地继续探索。
"""
    prompt_1 = f"""
请完成以下操作：
1 - 用一句话总结下面由三个反引号分隔的文本。
2 - 将摘要翻译成法语。
3 - 列出法语摘要中的每个名字。
4 - 输出一个 JSON 对象，包含以下键：french_summary, num_names。

请用换行分隔你的答案。

文本：
```{text}```
"""
    response = get_completion(prompt_1)
    print("prompt 1 的完成结果：")
    print(response)

    prompt_2 = f"""
你的任务是完成以下操作：
1 - 用一句话总结下面由尖括号 <> 包裹的文本。
2 - 将摘要翻译成法语。
3 - 列出法语摘要中的每个名字。
4 - 输出一个 JSON 对象，包含以下键：french_summary, num_names。

请使用以下格式：
文本：<要总结的文本>
摘要：<摘要>
翻译：<摘要的译文>
名字：<法语摘要中的名字列表>
输出 JSON：<包含摘要和名字数量的 JSON>

文本：<{text}>
"""
    response = get_completion(prompt_2)
    print("\nprompt 2 的完成结果：")
    print(response)

    prompt = f"""
判断学生的解答是否正确。

问题：
我正在建设一个太阳能发电设施，需要帮忙计算财务成本。
- 土地成本为每平方英尺 100 美元
- 我可以以每平方英尺 250 美元的价格购买太阳能板
- 我谈成了一份维护合同，费用为每年固定 10 万美元，
  另加每平方英尺 10 美元
第一年运营的总成本是多少？请用平方英尺数表示为函数。

学生的解答：
设 x 为该设施的面积，单位是平方英尺。
成本：
1. 土地成本：100x
2. 太阳能板成本：250x
3. 维护成本：100,000 + 100x
总成本：100x + 250x + 100,000 + 100x = 450x + 100,000
"""
    response = get_completion(prompt)
    print(response)

    prompt = f"""
你的任务是判断学生的解答是否正确。
为了解决这个问题，请按以下步骤操作：
- 首先，自己完整解出这道题。
- 然后，将你的解答与学生的解答进行比较，
  并评估学生的解答是否正确。
在你自己完成这道题之前，不要判断学生的解答是否正确。

请使用以下格式：
问题：
```
这里写问题
```
学生的解答：
```
这里写学生的解答
```
实际解答：
```
这里写推导步骤和你的解答
```
学生的解答是否与你刚刚算出的实际解答相同：
```
是或否
```
学生评分：
```
正确或错误
```

问题：
```
我正在建设一个太阳能发电设施，需要帮忙计算财务成本。
- 土地成本为每平方英尺 100 美元
- 我可以以每平方英尺 250 美元的价格购买太阳能板
- 我谈成了一份维护合同，费用为每年固定 10 万美元，
  另加每平方英尺 10 美元
第一年运营的总成本是多少？请用平方英尺数表示为函数。
```
学生的解答：
```
设 x 为该设施的面积，单位是平方英尺。
成本：
1. 土地成本：100x
2. 太阳能板成本：250x
3. 维护成本：100,000 + 100x
总成本：100x + 250x + 100,000 + 100x = 450x + 100,000
```
实际解答：
"""
    response = get_completion(prompt)
    print(response)

    prompt = f"""
介绍一下 Boie 的 AeroGlide UltraSlim Smart Toothbrush。
"""
    response = get_completion(prompt)
    print(response)


if __name__ == "__main__":
    main()
