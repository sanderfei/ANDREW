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


ZHIPU_API_KEY = "sk-lLKjavEquIsN4nk6eguOXFlhBXbXntGLHo5tOhbQWkBztYbj"
ZHIPU_BASE_URL = "https://ai-hub.digiwincloud.com.cn/v1"
ZHIPU_CHAT_MODEL = "ep-cl-glm-5.1"
RUN_LIVE_DEMO = False
STABLE_TEMPERATURE = 0.1

OFFICIAL_SOURCE = "https://docs.langchain.com/oss/python/langchain/voice-agent"


@dataclass
class VoiceAgentEvent:
    type: Literal["stt_chunk", "stt_output", "agent_chunk", "tts_chunk"]
    text: str | None = None
    transcript: str | None = None
    audio: bytes | None = None

    @classmethod
    def stt_chunk(cls, text: str):
        return cls(type="stt_chunk", text=text, transcript=text)

    @classmethod
    def stt_output(cls, transcript: str):
        return cls(type="stt_output", text=transcript, transcript=transcript)

    @classmethod
    def agent_chunk(cls, text: str):
        return cls(type="agent_chunk", text=text)

    @classmethod
    def tts_chunk(cls, audio: bytes):
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
        tools=[add_to_order, confirm_order],
        system_prompt=(
            "你是三明治店语音点餐助手。回答要简短、自然、适合 TTS 朗读。"
            "不要使用 Markdown、表格、emoji 或特殊符号。"
        ),
        checkpointer=deps["InMemorySaver"](),
    )


async def fake_audio_stream(text: str) -> AsyncIterator[bytes]:
    for word in text.split():
        await asyncio.sleep(0)
        yield word.encode() + b" "


async def stt_stream(audio_stream: AsyncIterator[bytes]) -> AsyncIterator[VoiceAgentEvent]:
    parts = []
    async for audio_chunk in audio_stream:
        text = audio_chunk.decode(errors="ignore")
        parts.append(text)
        yield VoiceAgentEvent.stt_chunk("".join(parts).strip())
    yield VoiceAgentEvent.stt_output("".join(parts).strip())


async def agent_stream(
    deps,
    event_stream: AsyncIterator[VoiceAgentEvent],
    agent=None,
) -> AsyncIterator[VoiceAgentEvent]:
    agent = agent or build_voice_agent(deps)
    thread_id = str(uuid4())
    async for event in event_stream:
        yield event
        if event.type != "stt_output" or not event.transcript:
            continue

        stream = agent.astream(
            {"messages": [deps["HumanMessage"](content=event.transcript)]},
            {"configurable": {"thread_id": thread_id}},
            stream_mode="values",
        )
        seen = ""
        async for chunk in stream:
            message = chunk["messages"][-1]
            content = getattr(message, "content", "") or ""
            if content and content != seen:
                delta = content[len(seen) :] if content.startswith(seen) else content
                seen = content
                if delta:
                    yield VoiceAgentEvent.agent_chunk(delta)


async def tts_stream(
    event_stream: AsyncIterator[VoiceAgentEvent],
) -> AsyncIterator[VoiceAgentEvent]:
    async for event in event_stream:
        yield event
        if event.type == "agent_chunk" and event.text:
            yield VoiceAgentEvent.tts_chunk(event.text.encode("utf-8"))


def build_pipeline(deps):
    return (
        deps["RunnableGenerator"](stt_stream)
        | deps["RunnableGenerator"](lambda stream: agent_stream(deps, stream))
        | deps["RunnableGenerator"](tts_stream)
    )


async def pipeline_demo(deps):
    pipeline = build_pipeline(deps)
    events = []
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
