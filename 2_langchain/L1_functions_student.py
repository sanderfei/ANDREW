import json

import requests
from _runtime import env


API_KEY = env("ZHIPU_API_KEY")
API_URL = "https://ai-hub.digiwincloud.com.cn/v1/chat/completions"
MODEL = "ep-cl-glm-5.1"


def get_current_weather(location, unit="fahrenheit"):
    """Get the current weather in a given location."""
    weather_info = {
        "location": location,
        "temperature": "72",
        "unit": unit,
        "forecast": ["sunny", "windy"],
    }
    return json.dumps(weather_info)


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    },
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        },
    }
]


def print_json(title, data):
    print(title)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def chat_completion(messages, log_title=None):
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    if log_title:
        print_json(f"\n{log_title}入参：", payload)

    response = requests.post(API_URL, headers=headers, json=payload, timeout=180)
    if response.status_code >= 400:
        print("响应内容：")
        print(response.text)
        response.raise_for_status()

    data = response.json()
    if log_title:
        print_json(f"\n{log_title}响应：", data)

    return data


def call_function(tool_call):
    function = tool_call["function"]
    if function["name"] != "get_current_weather":
        return json.dumps({"error": f"Unknown function: {function['name']}"})

    raw_arguments = function["arguments"]
    arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
    return get_current_weather(
        location=arguments.get("location"),
        unit=arguments.get("unit", "fahrenheit"),
    )


def main():
    messages = [
        {
            "role": "user",
            "content": "What's the weather like in Boston?",
        }
    ]

    response = chat_completion(messages)
    message = response["choices"][0]["message"]

    print("模型第一次响应：")
    print(json.dumps(message, ensure_ascii=False, indent=2))

    if message.get("tool_calls"):
        messages.append(message)
        for tool_call in message["tool_calls"]:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": call_function(tool_call),
                }
            )

        final_response = chat_completion(messages, log_title="第二次请求")
        print("\n模型拿到函数结果后的最终回答：")
        print(final_response["choices"][0]["message"]["content"])


if __name__ == "__main__":
    main()
