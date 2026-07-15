from L1_guidelines import get_completion_from_messages


def build_context():
    return [
        {
            "role": "system",
            "content": """
你是 OrderBot，一个为披萨餐厅收集订单的自动化服务。
你首先问候顾客，然后收集订单，
接着询问是自取还是配送。
你需要等到完整收集订单后，
再总结订单，并最后确认顾客是否还想添加其他内容。
如果是配送，你需要询问地址。
最后你需要收集付款信息。
请确保澄清所有选项、附加项和尺寸，
以便唯一确定菜单中的商品。
请使用简短、非常口语化且友好的风格回复。
菜单包括：
意大利辣香肠披萨 12.95, 10.00, 7.00
芝士披萨 10.95, 9.25, 6.50
茄子披萨 11.95, 9.75, 6.75
薯条 4.50, 3.50
希腊沙拉 7.25
配料：
额外芝士 2.00
蘑菇 1.50
香肠 3.00
加拿大培根 3.50
AI 酱 1.50
青椒 1.00
饮料：
可乐 3.00, 2.00, 1.00
雪碧 3.00, 2.00, 1.00
瓶装水 5.00
""",
        }
    ]


def summarize_order(context):
    messages = context.copy()
    messages.append(
        {
            "role": "system",
            "content": """
请为前面的食品订单创建一个 JSON 摘要。
请逐项列出每个商品的价格。
字段应包括：
1) pizza，包含尺寸
2) toppings 列表
3) drinks 列表，包含尺寸
4) sides 列表，包含尺寸
5) total_price
如果订单信息还不完整，请根据已有信息输出，并把缺失信息写入 missing_fields。
""",
        }
    )
    return get_completion_from_messages(messages, temperature=0)


def chat_once(context, user_input):
    context.append({"role": "user", "content": user_input})
    response = get_completion_from_messages(context)
    context.append({"role": "assistant", "content": response})
    return response


def main():
    context = build_context()
    print("OrderBot 命令行聊天已启动。")
    print("输入内容后回车即可对话；输入 summary 查看订单 JSON；输入 exit 或 退出 结束。")
    print()

    while True:
        try:
            user_input = input("用户> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "q"} or user_input in {"退出", "结束"}:
            print("已退出。")
            break

        if user_input.lower() in {"summary", "/summary"} or user_input in {"摘要", "订单摘要"}:
            try:
                summary = summarize_order(context)
            except Exception as exc:
                print(f"生成订单摘要失败：{exc}")
            else:
                print(f"订单摘要> {summary}")
            continue

        try:
            response = chat_once(context, user_input)
        except Exception as exc:
            print(f"调用模型失败：{exc}")
            continue

        print(f"助手> {response}")


if __name__ == "__main__":
    main()
