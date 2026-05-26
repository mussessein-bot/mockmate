import asyncio
import json
import struct
import uuid
import aiofiles
import websockets

from app.config import (
    VOLCANO_SPEECH_KEY, VOLCANO_TTS_WS, VOLCANO_TTS_RESOURCE,
    PERSONA_VOICES, AUDIO_DIR,
)
from app.core.exceptions import TTSError

# ── Binary protocol constants ────────────────────────────────────────────────
_VERSION    = 0x01
_HDR_SIZE   = 0x01   # 1 × 4 bytes = 4-byte header
_TYPE_CLIENT = 0x01  # FullClientRequest
_TYPE_SERVER = 0x09  # FullServerResponse  (JSON payload)
_TYPE_AUDIO  = 0x0B  # AudioOnlyServer     (raw audio bytes)
_SERIAL_JSON = 0x01
_COMPRESS_NO = 0x00
_EVENT_FINISHED = 50  # SessionFinished event code

def _frame(payload: bytes) -> bytes:
    header = bytes([
        (_VERSION << 4) | _HDR_SIZE,
        (_TYPE_CLIENT << 4) | 0x00,
        (_SERIAL_JSON << 4) | _COMPRESS_NO,
        0x00,
    ])
    return header + struct.pack(">I", len(payload)) + payload


def _voice(persona: str, language: str) -> str:
    return PERSONA_VOICES.get(persona, PERSONA_VOICES["sarah"]).get(language, "zh_female_vv_uranus_bigtts")


# Track last audio file per session (only keep current question)
_current_audio: dict[str, str] = {}


async def generate_audio(text: str, persona: str, language: str, session_id: str) -> str:
    """Generate TTS audio via Volcano WebSocket. Returns filename."""
    if not VOLCANO_SPEECH_KEY:
        raise TTSError("VOLCANO_SPEECH_KEY not set in .env")

    speaker = _voice(persona, language)
    filename = f"{session_id}_{uuid.uuid4().hex[:8]}.mp3"
    output_path = AUDIO_DIR / filename

    # Delete previous audio for this session
    prev = _current_audio.get(session_id)
    if prev:
        prev_path = AUDIO_DIR / prev
        if prev_path.exists():
            prev_path.unlink()

    await _synthesize(text, speaker, output_path)
    _current_audio[session_id] = filename
    return filename


async def generate_preview(persona: str, language: str) -> str:
    """Generate a short persona preview clip. Cached by persona+language."""
    previews_zh = {
        "sarah": "你好！我是 Sarah Chen，很高兴认识你，期待今天的面试。",
        "marcus": "好，开始吧。我希望你的回答简洁、具体、有数据支撑。",
        "alex": "时间有限，直接开始。准备好了吗？",
    }
    previews_en = {
        "sarah": "Hello! I'm Sarah Chen, so glad to meet you. Looking forward to our interview.",
        "marcus": "Alright, let's begin. I expect concise, specific answers backed by data.",
        "alex": "No time to waste. Ready? Let's go.",
    }
    text = (previews_zh if language == "zh" else previews_en).get(persona, "Hello.")
    speaker = _voice(persona, language)
    filename = f"preview_{persona}_{language}.mp3"
    output_path = AUDIO_DIR / filename
    await _synthesize(text, speaker, output_path)
    return filename


async def _synthesize(text: str, speaker: str, output_path) -> None:
    """Core WebSocket TTS → write MP3 to output_path."""
    headers = {
        "X-Api-Key": VOLCANO_SPEECH_KEY,
        "X-Api-Resource-Id": VOLCANO_TTS_RESOURCE,
        "X-Api-Request-Id": str(uuid.uuid4()),
    }
    request = {
        "user": {"uid": str(uuid.uuid4())},
        "req_params": {
            "speaker": speaker,
            "audio_params": {"format": "mp3", "sample_rate": 24000},
            "text": text,
        },
    }

    try:
        async with websockets.connect(
            VOLCANO_TTS_WS,
            additional_headers=headers,
            max_size=10 * 1024 * 1024,
        ) as ws:
            await ws.send(_frame(json.dumps(request).encode("utf-8")))

            audio_buf = bytearray()
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=8.0)
                except asyncio.TimeoutError:
                    break  # no more data; stream is done (proxy may drop close frame)
                except websockets.exceptions.ConnectionClosed:
                    break  # server closed connection normally
                if not isinstance(raw, (bytes, bytearray)) or len(raw) < 8:
                    continue

                msg_type = (raw[1] >> 4) & 0x0F
                payload_size = struct.unpack(">I", raw[4:8])[0]
                payload = raw[8 : 8 + payload_size]

                if msg_type == _TYPE_AUDIO:
                    # Each payload has a binary header: [4B meta_len][meta_len B metadata][4B audio_len][audio...]
                    if len(payload) > 8:
                        meta_len = struct.unpack(">I", payload[:4])[0]
                        audio_offset = 4 + meta_len + 4
                        if audio_offset < len(payload):
                            audio_buf.extend(payload[audio_offset:])
                    else:
                        audio_buf.extend(payload)
                elif msg_type == _TYPE_SERVER:
                    try:
                        # Payload has a binary/text prefix before the JSON object
                        decoded = payload.decode("utf-8", errors="replace")
                        json_start = decoded.find("{")
                        if json_start == -1:
                            continue
                        resp = json.loads(decoded[json_start:])
                        if resp.get("event") == _EVENT_FINISHED:
                            break
                        if not resp:  # empty {} is the stream-end sentinel
                            break
                        if resp.get("code", 0) not in (0, None):
                            raise TTSError(f"Volcano TTS error: {resp}")
                    except (json.JSONDecodeError, KeyError):
                        continue  # ignore malformed server metadata messages

    except websockets.exceptions.WebSocketException as e:
        raise TTSError(f"WebSocket error: {e}") from e

    if not audio_buf:
        raise TTSError("No audio data received from Volcano TTS")

    async with aiofiles.open(str(output_path), "wb") as f:
        await f.write(bytes(audio_buf))
