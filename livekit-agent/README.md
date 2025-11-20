# LiveKit Voice/WebSocket Agent with Langfuse Tracing

This project combines a LiveKit voice agent with a custom FastAPI WebSocket backend and optional Langfuse observability. Spoken user input is transcribed (STT), sent to a lightweight WebSocket "LLM" endpoint, and the response is synthesized to speech (TTS) while traces are recorded when Langfuse credentials are present.

## Components
- **`main.py`**: LiveKit agent entrypoint. Wires together:
  - Deepgram STT (`deepgram.STT`)
  - Custom WebSocket LLM (`WebSocketLLM`) → sends text over a WebSocket (`WS_SERVER_URL`) and streams back a single reply
  - ElevenLabs TTS (`elevenlabs.TTS`) for speech output (optional if keys provided)
  - Silero VAD for voice activity detection
  - Langfuse tracing (session + generations) when valid credentials exist
- **`fastapi_websocket_server.py`**: Minimal FastAPI WebSocket server acting as a placeholder LLM/backend. Echoes processed responses and optionally records Langfuse session + generation data.
- **`start-agent.ps1`**: Legacy helper script referencing a non‑existent `livekit_basic_agent.py` (left for backward compatibility; prefer `python main.py`).

## Features
- Voice → Text → WebSocket → Text → Voice loop
- Graceful Langfuse degradation: all tracing calls guarded by capability checks
- Modular plugin architecture via `livekit.agents`
- Single-turn generation wrapping for each user message

## Prerequisites
- Python 3.10+ recommended
- (Windows) Ensure microphone access permissions are granted
- Optional: `ffmpeg` if future audio transformations are needed
- LiveKit Cloud project (API key/secret) if you intend to join real rooms rather than a local console session

## Installation (Windows PowerShell)
```powershell
# From repository root (livekit-agent directory)
python -m venv venv
venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
# Install extra plugins if not bundled
pip install livekit-agents livekit-plugins-deepgram livekit-plugins-elevenlabs livekit-plugins-silero langfuse uvicorn fastapi websockets python-dotenv
```

> If some `livekit` subpackages are missing, install the specific plugin wheels (names may vary by release).

## Environment Variables (`.env` suggested)
Create a `.env` file beside `main.py` or in project root:
```
# LiveKit (if using real rooms)
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_HOST=wss://your-livekit-host (optional)

# WebSocket backend
WS_SERVER_URL=ws://127.0.0.1:8080/ws

# Deepgram
DEEPGRAM_API_KEY=your_deepgram_key

# ElevenLabs (optional TTS)
ELEVENLABS_API_KEY=your_elevenlabs_key
ELEVENLABS_VOICE_ID=your_voice_id (optional)
ELEVENLABS_TTS_MODEL=eleven_monolingual_v1 (optional)
ELEVENLABS_STREAMING_LATENCY=0

# Langfuse (optional tracing)
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com (optional)
```
Any missing value simply disables that feature gracefully.

## Running
1. Start the FastAPI WebSocket server (acts as a minimal LLM backend):
```powershell
venv\Scripts\Activate.ps1
python fastapi_websocket_server.py
```
2. In a second terminal, start the LiveKit agent:
```powershell
venv\Scripts\Activate.ps1
python main.py
```
3. Speak into your microphone after session initialization. The agent will greet you with: "Hi there! How can I help you today?"

## How It Works (Flow)
1. Audio captured → VAD gates speech → Deepgram transcribes.
2. Latest user text sent via WebSocket to FastAPI server.
3. Server returns a processed text response.
4. ElevenLabs synthesizes response to speech.
5. Langfuse (if enabled) records a session trace and per-message generations.

## Langfuse Tracing Details
- `trace`: Created per agent session and per WebSocket session.
- `generation`: Created for each user message processed.
- All `.end()`, `.update()`, and `.flush()` calls are guarded to avoid runtime errors on older versions or missing permissions.

## Customizing
- Replace the WebSocket server logic in `fastapi_websocket_server.py` with calls to a real model API.
- Extend `WebSocketLLM` to stream tokens instead of single messages (yield multiple `ChatChunk` objects).
- Add retry logic or exponential backoff for transient WebSocket failures.

## Troubleshooting
| Issue | Cause | Fix |
|-------|-------|-----|
| No audio / silence | Mic permission / VAD threshold | Check OS mic access; adjust Silero VAD config |
| Missing STT results | Deepgram key invalid | Verify `DEEPGRAM_API_KEY` in `.env` |
| TTS not playing | ElevenLabs key/voice unset | Provide `ELEVENLABS_API_KEY` & `ELEVENLABS_VOICE_ID` |
| Langfuse disabled message | Bad credentials or host | Recheck keys & `LANGFUSE_HOST` URL |
| WebSocket connection refused | Server not started / wrong port | Start `fastapi_websocket_server.py`; confirm `WS_SERVER_URL` |
| Script references `livekit_basic_agent.py` | Legacy artifact | Run `python main.py` instead |

## Next Ideas
- Multi-turn context threading in the FastAPI server
- Stream partial transcription for faster TTS start
- Add authentication / rate limiting on WebSocket endpoint
- Persist traces or analytics dashboards

## Disclaimer
The placeholder WebSocket server is intentionally simple (echo-style processing). Replace it before production use.

