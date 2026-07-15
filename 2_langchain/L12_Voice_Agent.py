import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Literal
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_SITE_PACKAGES = (
    PROJECT_ROOT
    / ".venv"
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)
if VENV_SITE_PACKAGES.exists():
    sys.path.insert(0, str(VENV_SITE_PACKAGES))
from _runtime import env



ZHIPU_API_KEY = env("ZHIPU_API_KEY")
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
RUN_LIVE_DEMO = True
STABLE_TEMPERATURE = 0.1

OFFICIAL_SOURCE = "https://docs.langchain.com/oss/python/langchain/voice-agent"

# Python 没有 Java 那样的 new 关键字。通过一个方便的方法，自动帮你创建正确类型的对象
# @dataclass 的作用是：帮这个类自动生成常用的初始化方法 __init__、对象打印形式等。
@dataclass
class VoiceAgentEvent:
    type: Literal["stt_chunk", "stt_output", "agent_chunk", "tts_chunk"]
    # 可以是字符串或者None 不传就是默认None
    text: str | None = None #中间文本
    transcript: str | None = None #最终语音转文本，交给agent
    audio: bytes | None = None

    # @classmethod 不是类型注解，而是 Python 的装饰器：把方法变成“类方法”。
    # cls 是 Python 自动传入的“当前类对象”，调用时你不用自己传。
    # event = VoiceAgentEvent.stt_chunk("你好") 等价如下
    # VoiceAgentEvent.stt_chunk(VoiceAgentEvent, "你好")
    @classmethod
    def stt_chunk(cls, text: str):
        # stt_chunk 是"语音识别进行中的文本片段"
        return cls(type="stt_chunk", text=text, transcript=text)

    @classmethod
    def stt_output(cls, transcript: str):
        # 触发 agent 的最终转写
        return cls(type="stt_output", text=transcript, transcript=transcript)

    @classmethod
    def agent_chunk(cls, text: str):
        # agent 生成的文本片段
        return cls(type="agent_chunk", text=text)

    @classmethod
    def tts_chunk(cls, audio: bytes):
        # tts_chunk 文本转语音后得到的音频片段
        return cls(type="tts_chunk", audio=audio)


def load_dependencies():
    try:
        from langchain.agents import create_agent
        from langchain.messages import HumanMessage
        from langchain_core.runnables import RunnableGenerator
        from langchain_openai import ChatOpenAI
        from langgraph.checkpoint.memory import InMemorySaver
    except ImportError as exc:
        raise RuntimeError(
            "加载失败。需要安装 langchain、langchain-core、langchain-openai、langgraph。"
            f"原始错误: {type(exc).__name__}: {exc}"
        ) from exc

    return {
        "ChatOpenAI": ChatOpenAI,
        "HumanMessage": HumanMessage,
        "InMemorySaver": InMemorySaver,
        "RunnableGenerator": RunnableGenerator,
        "create_agent": create_agent,
    }


def build_model(ChatOpenAI, temperature=STABLE_TEMPERATURE, **kwargs):
    if not ZHIPU_API_KEY:
        raise RuntimeError("请先在文件顶部填写 ZHIPU_API_KEY，再运行真实语音 agent demo。")
    return ChatOpenAI(
        model=ZHIPU_CHAT_MODEL,
        temperature=temperature,
        openai_api_key=ZHIPU_API_KEY,
        openai_api_base=ZHIPU_BASE_URL,
        timeout=60,
        **kwargs,
    )


def model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, bytes):
        return {"bytes": len(value), "preview": value[:40].decode(errors="ignore")}
    if isinstance(value, VoiceAgentEvent):
        return {
            "type": value.type,
            "text": value.text,
            "transcript": value.transcript,
            "audio": model_dump(value.audio) if value.audio else None,
        }
    if isinstance(value, dict):
        return {key: model_dump(item) for key, item in value.items()}
    if isinstance(value, list):
        return [model_dump(item) for item in value]
    return value


def add_to_order(item: str, quantity: int) -> str:
    """Add an item to the customer's sandwich order."""
    return f"Added {quantity} x {item} to the order."


def confirm_order(order_summary: str) -> str:
    """Confirm the final order with the customer."""
    return f"Order confirmed: {order_summary}. Sending to kitchen."


def build_voice_agent(deps):
    return deps["create_agent"](
        model=build_model(deps["ChatOpenAI"]),
        #普通python函数对象，LangChain 的 create_agent() 可以直接接收，自动把这两个函数转换成 Tool，
        #除非content_and_artifact（content给模型看的文本，artifact程序保留的Docment列表）、args_schema需要额外标注功能，自动转换无法表达
        tools=[add_to_order, confirm_order],
        system_prompt=(
            "你是三明治店语音点餐助手。回答要简短、自然、适合 TTS 朗读。"
            "不要使用 Markdown、表格、emoji 或特殊符号。"
        ),
        checkpointer=deps["InMemorySaver"](),
    )


# 伪音频流: 把文本按词切分，逐块模拟输出音频二进制数据
# 对应的消费demo
# async for chunk in fake_audio_stream("hello world"):
#     print(chunk)
# AsyncIterator：这个对象可以被异步迭代，并且每次产出的元素类型是 bytes。
# 这个对象可以被异步迭代，并且每次产出的元素类型是 bytes。
async def fake_audio_stream(text: str) -> AsyncIterator[bytes]:
    for word in text.split():
        # 异步让出一次事件循环执行权。
        # 演示“这里可以异步等待”
        await asyncio.sleep(0)
        # 产出一个值给调用方，然后暂停函数，等待下一次继续
        yield word.encode() + b" "


# 异步模拟音频解码 一次处理一个音频块，产出转写结果
# 每多一个输入 chunk，通常就多一个中间输出事件；等输入结束时，再额外输出一次最终结果。
async def stt_stream(audio_stream: AsyncIterator[bytes]) -> AsyncIterator[VoiceAgentEvent]:
    parts = []
    async for audio_chunk in audio_stream:
        text = audio_chunk.decode(errors="ignore")
        parts.append(text)
        yield VoiceAgentEvent.stt_chunk("".join(parts).strip())
    yield VoiceAgentEvent.stt_output("".join(parts).strip())


# yield:产出一个值给消费者
# → 函数暂停，但不结束
# → 下次消费者要下一个值时，从暂停处继续
async def agent_stream(
    deps,
    event_stream: AsyncIterator[VoiceAgentEvent],
    agent=None,
) -> AsyncIterator[VoiceAgentEvent]:
    agent = agent or build_voice_agent(deps)
    # 生成唯一会话 ID。因为 Agent 配了 InMemorySaver
    thread_id = str(uuid4())
    async for event in event_stream:
        # 先把上游收到的事件原样传给下游
        yield event
        if event.type != "stt_output" or not event.transcript:
            continue

        # 同一个 agent_stream() 调用内如果出现多次，都会使用同一个 thread_id，从而保留本次会话历史。
        # 创建 Agent 的异步结果流，astream() 本身返回异步迭代器
        # → HumanMessage 传给 Agent
        # → 模型自行判断是否需要调用工具
        # → LangChain 执行工具
        # → 工具结果作为 ToolMessage 回给模型
        # → 模型根据工具结果组织最终回复
        # → 最终 AIMessage.content
        # → VoiceAgentEvent.agent_chunk(text=...)
        # stream 包含整个 Agent 执行过程的 AsyncIterator（包含完整的上述工具调用）
        stream = agent.astream(
            {"messages": [deps["HumanMessage"](content=event.transcript)]},
            {"configurable": {"thread_id": thread_id}},
            stream_mode="values",
        )
        seen = ""
        async for chunk in stream:
            message = chunk["messages"][-1]
            # type == "ai"且没有 tool_calls 就是工具执行完成后，模型组织出的最终回复
            if getattr(message, "type", None) != "ai":
                continue
            if getattr(message, "tool_calls", None):
                continue

            content = getattr(message, "content", "") or ""
            if content and content != seen:
                delta = content[len(seen) :] if content.startswith(seen) else content
                seen = content
                if delta:  # 只有内容非空、并且与上一次已处理内容不同，才继续处理，避免同一快照重复输出
                    yield VoiceAgentEvent.agent_chunk(delta)


async def tts_stream(
    event_stream: AsyncIterator[VoiceAgentEvent],
) -> AsyncIterator[VoiceAgentEvent]:
    async for event in event_stream:
        yield event
        if event.type == "agent_chunk" and event.text:
            yield VoiceAgentEvent.tts_chunk(event.text.encode("utf-8"))


# 音频流
# → STT 事件流
# → Agent 事件流
# → TTS 事件流
def build_pipeline(deps):
    # RunnableGenerator 需要真正的异步生成器函数；这里同时把 deps 绑定给 agent_stream。
    # RunnableGenerator 只能自动传入上游的一个 stream 参数，所以这里把外层的 deps 先“绑定”进去。
    async def agent_stage(
        stream: AsyncIterator[VoiceAgentEvent],
    ) -> AsyncIterator[VoiceAgentEvent]:
        async for event in agent_stream(deps, stream):
            yield event

    return (
        deps["RunnableGenerator"](stt_stream)
        | deps["RunnableGenerator"](agent_stage)
        | deps["RunnableGenerator"](tts_stream)
    )


async def pipeline_demo(deps):
    pipeline = build_pipeline(deps)
    events = []
    # pipeline.atransform具体开始执行
    async for event in pipeline.atransform(
        fake_audio_stream("I want two turkey sandwiches")
    ):
        events.append(event)
    return events


def architecture_demo():
    return {
        "official_source": OFFICIAL_SOURCE,
        "architecture": "STT -> LangChain agent -> TTS",
        "events": [
            "stt_chunk: 语音识别中的部分转写",
            "stt_output: 触发 agent 的最终转写",
            "agent_chunk: agent 生成的文本片段",
            "tts_chunk: TTS 返回的音频片段",
        ],
        "local_adaptation": (
            "本地文件使用 fake_audio_stream/stt_stream/tts_stream 演示架构；"
            "接 AssemblyAI 或 Cartesia 时替换 STT/TTS 两个 adapter。"
        ),
    }


def main():
    try:
        deps = load_dependencies()
    except RuntimeError as exc:
        print(exc)
        return

    print(json.dumps(model_dump(architecture_demo()), ensure_ascii=False, indent=2))
    if RUN_LIVE_DEMO:
        print(json.dumps(model_dump(asyncio.run(pipeline_demo(deps))), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

# "I want two turkey sandwiches"
# → 模拟切成音频 bytes 流
# → STT 流式累积成文字
# → 最终转写交给 Agent
# → Agent 决定调用 add_to_order
# → 工具执行并返回结果
# → Agent 根据工具结果生成最终回复
# → TTS 把最终回复转成 bytes 流

# [
#   {
#     "type": "stt_chunk",流式识别文字
#     "text": "I",
#     "transcript": "I",
#     "audio": null
#   },
#   {
#     "type": "stt_chunk",
#     "text": "I want",
#     "transcript": "I want",
#     "audio": null
#   },
#   ......
#   {
#     "type": "stt_chunk",
#     "text": "I want two turkey sandwiches",
#     "transcript": "I want two turkey sandwiches",
#     "audio": null
#   },
#   {
#     "type": "stt_output", 完整文字
#     "text": "I want two turkey sandwiches",
#     "transcript": "I want two turkey sandwiches",
#     "audio": null
#   },Agent + Tool
#   {
#     "type": "agent_chunk",最终回答文字
#     "text": "Got it, two turkey sandwiches added to your order. Would you like anything else, like drinks or chips?",
#     "transcript": null,
#     "audio": null
#   },
#   {
#     "type": "tts_chunk",模拟音频 bytes
#     "text": null,
#     "transcript": null,
#     "audio": {
#       "bytes": 102,
#       "preview": "Got it, two turkey sandwiches added to y"
#     }
#   }
# ]