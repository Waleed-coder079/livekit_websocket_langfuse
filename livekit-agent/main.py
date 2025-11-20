from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession
from livekit.agents.llm import LLM, ChatChunk, ChoiceDelta
from livekit.plugins import deepgram, silero, elevenlabs
import os
import asyncio
import websockets
from contextlib import asynccontextmanager

# ✅ Load environment variables
load_dotenv(dotenv_path=".env")

# ✅ Initialize Langfuse with safe imports
LANGFUSE_ENABLED = False
langfuse = None

try:
    from langfuse import Langfuse

    langfuse = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    )

    # Check authentication
    if hasattr(langfuse, 'auth_check') and langfuse.auth_check():
        LANGFUSE_ENABLED = True
        print("✅ Langfuse connected successfully")
    else:
        print("⚠️ Langfuse auth check not available or failed")
except Exception as e:
    print(f"⚠️ Langfuse not available: {e}")


class WebSocketLLM(LLM):
    def __init__(self, url: str):
        super().__init__()
        self.url = url

    @asynccontextmanager
    async def chat(self, chat_ctx, **kwargs):
        async def gen():
            trace = None
            generation = None

            try:
                # ✅ Extract user message
                all_messages = chat_ctx.items
                mesg = all_messages[-1] if all_messages else None
                user_msg = mesg.content if mesg else "Hi"
                if isinstance(user_msg, list):
                    user_msg = " ".join(str(part) for part in user_msg)
                user_msg = user_msg.strip() or "Hi"

                print(f"[DEBUG] Sending to WebSocket: {user_msg}")

                # ✅ Start Langfuse trace (only if supported)
                if LANGFUSE_ENABLED and langfuse and hasattr(langfuse, 'trace'):
                    try:
                        trace = langfuse.trace(
                            name="voice-agent-turn",
                            input={"user_message": user_msg},
                            metadata={"component": "livekit-agent"}
                        )
                        
                        if hasattr(trace, 'generation'):
                            generation = trace.generation(
                                name="websocket-llm",
                                model="custom-websocket",
                                input=user_msg
                            )
                    except Exception as e:
                        print(f"⚠️ Langfuse trace failed: {e}")

                # ✅ Connect to WebSocket server
                async with websockets.connect(self.url) as ws:
                    await ws.send(user_msg)
                    reply = await ws.recv()
                    print(f"[WebSocket] Reply: {reply}")

                    # ✅ End generation (only if it exists)
                    if generation and hasattr(generation, 'end'):
                        try:
                            generation.end(output=reply)
                        except Exception as e:
                            print(f"⚠️ Langfuse generation.end failed: {e}")

                    yield ChatChunk(
                        id="ws-chunk",
                        delta=ChoiceDelta(role="assistant", content=reply)
                    )

                # ✅ Flush Langfuse logs
                if LANGFUSE_ENABLED and langfuse and hasattr(langfuse, 'flush'):
                    try:
                        langfuse.flush()
                    except Exception as e:
                        print(f"⚠️ Langfuse flush failed: {e}")

            except Exception as e:
                print(f"[ERROR] {e}")
                import traceback
                traceback.print_exc()

        yield gen()


class Assistant(Agent):
    def __init__(self):
        super().__init__(instructions="You are a helpful and friendly voice assistant.")


async def entrypoint(ctx: agents.JobContext):
    # ✅ Start session trace (only if supported)
    session_trace = None
    if LANGFUSE_ENABLED and langfuse and hasattr(langfuse, 'trace'):
        try:
            session_trace = langfuse.trace(
                name="livekit-agent-session",
                metadata={
                    "room": getattr(ctx.room, 'name', 'console'),
                    "session_type": "voice-agent"
                }
            )
            print("✅ Langfuse session trace started")
        except Exception as e:
            print(f"⚠️ Langfuse session trace failed: {e}")

    websocket_llm = WebSocketLLM(
        url=os.getenv("WS_SERVER_URL", "ws://127.0.0.1:8080/ws")
    )

    session = AgentSession(
        stt=deepgram.STT(model="nova-2", language="en"),
        llm=websocket_llm,
        tts=elevenlabs.TTS(
            **{
                k: v
                for k, v in {
                    "voice_id": os.getenv("ELEVENLABS_VOICE_ID"),
                    "model": os.getenv("ELEVENLABS_TTS_MODEL"),
                    "api_key": os.getenv("ELEVENLABS_API_KEY"),
                }.items()
                if v
            },
            streaming_latency=int(os.getenv("ELEVENLABS_STREAMING_LATENCY", "0")),
        ),
        vad=silero.VAD.load(),
    )

    await session.start(room=ctx.room, agent=Assistant())
    await session.say("Hi there! How can I help you today?")

    # ✅ End session trace
    if session_trace and hasattr(session_trace, 'update'):
        try:
            session_trace.update(output={"status": "completed"})
        except Exception as e:
            print(f"⚠️ Langfuse session update failed: {e}")
            
    if LANGFUSE_ENABLED and langfuse and hasattr(langfuse, 'flush'):
        try:
            langfuse.flush()
        except Exception as e:
            print(f"⚠️ Langfuse final flush failed: {e}")


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))