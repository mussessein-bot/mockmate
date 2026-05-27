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

# ── Binary protocol constants (per official V3 docs) ──────────────────────────
_VERSION = 0x01
_HDR_SIZE = 0x01  # 4-byte header

# Client → Server message types
_TYPE_FULL_CLIENT = 0x01
# Server → Client message types
_TYPE_AUDIO_ONLY = 0x0B  # TTSResponse (audio data)
_TYPE_SERVER = 0x09      # JSON responses (SentenceStart/End, SessionFinished)

# Serialization / compression
_SERIAL_JSON = 0x01
_SERIAL_RAW = 0x00
_COMPRESS_NO = 0x00

# Message type specific flags
_FLAGS_NO_EVENT = 0x00
_FLAGS_WITH_EVENT = 0x04  # 0b0100 — event number present in bytes 4-7

# Event codes (server → client)
EVENT_TTS_SENTENCE_START = 350
EVENT_TTS_SENTENCE_END = 351
EVENT_TTS_RESPONSE = 352
EVENT_SESSION_FINISHED = 152

# Event codes (client → server)
EVENT_FINISH_CONNECTION = 2
EVENT_CONNECTION_FINISHED = 52


def _frame(payload: bytes, msg_type: int = _TYPE_FULL_CLIENT,
           flags: int = _FLAGS_NO_EVENT, serial: int = _SERIAL_JSON) -> bytes:
    header = bytes([
        (_VERSION << 4) | _HDR_SIZE,
        (msg_type << 4) | flags,
        (serial << 4) | _COMPRESS_NO,
        0x00,
    ])
    return header + struct.pack(">I", len(payload)) + payload


def _finish_connection_frame() -> bytes:
    """Build a FinishConnection frame (client → server, event=2)."""
    payload = json.dumps({}).encode("utf-8")
    header = bytes([
        (_VERSION << 4) | _HDR_SIZE,
        (_TYPE_FULL_CLIENT << 4) | _FLAGS_WITH_EVENT,
        (_SERIAL_JSON << 4) | _COMPRESS_NO,
        0x00,
    ])
    return header + struct.pack(">I", EVENT_FINISH_CONNECTION) + struct.pack(">I", len(payload)) + payload


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


def _parse_response_frame(raw: bytes):
    """Parse a V3 binary response frame per official protocol.

    Returns (msg_type, flags, event_code, payload_bytes) or None if too short.
    Frame layout:
      [0-3]  header
      [4-7]  event number (only if flags & 0x04)
      [8-11] session_id length
      [12..] session_id
      then:  payload_length (4B) + payload
    """
    if len(raw) < 4:
        return None

    msg_type = (raw[1] >> 4) & 0x0F
    flags = raw[1] & 0x0F

    offset = 4
    event_code = None
    if flags & 0x04:  # event number present
        if offset + 4 > len(raw):
            return None
        event_code = struct.unpack(">I", raw[offset:offset + 4])[0]
        offset += 4

    # session_id
    if offset + 4 > len(raw):
        return None
    sid_len = struct.unpack(">I", raw[offset:offset + 4])[0]
    offset += 4 + sid_len

    # payload
    if offset + 4 > len(raw):
        return None
    payload_len = struct.unpack(">I", raw[offset:offset + 4])[0]
    offset += 4
    payload = raw[offset:offset + payload_len]

    return msg_type, flags, event_code, payload


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
            # Send text request
            await ws.send(_frame(json.dumps(request).encode("utf-8")))

            audio_buf = bytearray()
            session_finished = False

            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=15.0)
                except asyncio.TimeoutError:
                    break
                except websockets.exceptions.ConnectionClosed:
                    break

                if not isinstance(raw, (bytes, bytearray)) or len(raw) < 4:
                    continue

                parsed = _parse_response_frame(raw)
                if parsed is None:
                    continue

                msg_type, flags, event_code, payload = parsed

                if msg_type == _TYPE_AUDIO_ONLY:
                    # TTSResponse — raw audio data
                    audio_buf.extend(payload)

                elif msg_type == _TYPE_SERVER:
                    if event_code == EVENT_SESSION_FINISHED:
                        try:
                            resp = json.loads(payload)
                            status = resp.get("status_code")
                            if status is not None and status != 20000000:
                                raise TTSError(f"Volcano TTS error: {resp}")
                        except (json.JSONDecodeError, KeyError):
                            pass
                        session_finished = True
                        break
                    elif event_code in (EVENT_TTS_SENTENCE_START, EVENT_TTS_SENTENCE_END):
                        pass  # informational, skip
                    else:
                        # Unknown server event — try to check for errors
                        try:
                            resp = json.loads(payload)
                            if isinstance(resp, dict) and resp.get("code", 0) not in (0, None):
                                raise TTSError(f"Volcano TTS error: {resp}")
                        except (json.JSONDecodeError, KeyError):
                            pass

            # Send FinishConnection if we got SessionFinished
            if session_finished:
                try:
                    await ws.send(_finish_connection_frame())
                    await asyncio.wait_for(ws.recv(), timeout=5.0)
                except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                    pass

    except websockets.exceptions.WebSocketException as e:
        raise TTSError(f"WebSocket error: {e}") from e

    if not audio_buf:
        raise TTSError("No audio data received from Volcano TTS")

    async with aiofiles.open(str(output_path), "wb") as f:
        await f.write(bytes(audio_buf))
