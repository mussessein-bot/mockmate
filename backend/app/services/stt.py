import asyncio
import uuid
import httpx
import logging

logger = logging.getLogger(__name__)

from app.config import (
    VOLCANO_SPEECH_KEY, VOLCANO_STT_SUBMIT, VOLCANO_STT_QUERY,
    VOLCANO_STT_RESOURCE, BACKEND_URL, AUDIO_DIR,
)
from app.core.exceptions import LLMError  # reuse for STT errors


class STTError(Exception):
    pass


# Status codes returned in X-Api-Status-Code response header
_STATUS_SUCCESS = "20000000"
_STATUS_PROCESSING = "20000001"
_STATUS_IN_QUEUE = "20000002"
_STATUS_SILENT = "20000003"


async def transcribe_audio(filename: str, language: str = "zh") -> str:
    """
    Submit audio file to Volcano batch STT and poll for result.
    filename: just the name (e.g. 'abc.webm'), file lives in AUDIO_DIR.
    Returns transcript string.
    """
    if not VOLCANO_SPEECH_KEY:
        raise STTError("VOLCANO_SPEECH_KEY not set in .env")

    audio_url = f"{BACKEND_URL}/audio/{filename}"
    req_id = str(uuid.uuid4())

    # Detect format from filename extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"

    # Submit and query share the same auth headers; query omits X-Api-Sequence
    _base_headers = {
        "Content-Type": "application/json",
        "X-Api-Key": VOLCANO_SPEECH_KEY,        # new-console key format
        "X-Api-Resource-Id": VOLCANO_STT_RESOURCE,
        "X-Api-Request-Id": req_id,
    }
    submit_headers = {**_base_headers, "X-Api-Sequence": "-1"}

    submit_body = {
        "user": {"uid": "mockmate"},
        "audio": {
            "url": audio_url,
            "format": ext,          # e.g. webm / mp4 / mp3 / wav / ogg
            # codec/rate/bits/channel omitted: only relevant for raw PCM;
            # for compressed audio (webm/opus, mp4/aac) the API auto-detects.
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Submit
        # Per API docs, response body is empty; status lives in response headers.
        resp = await client.post(VOLCANO_STT_SUBMIT, json=submit_body, headers=submit_headers)
        submit_status = resp.headers.get("X-Api-Status-Code", "")
        submit_msg = resp.headers.get("X-Api-Message", "")
        logger.info(f"STT submit: status={submit_status} message={submit_msg}")

        if submit_status != _STATUS_SUCCESS:
            raise STTError(f"STT submit failed: code={submit_status} msg={submit_msg}")

        # Step 2: Poll for result (max 60 s, 2 s interval)
        for attempt in range(30):
            await asyncio.sleep(2)
            qresp = await client.post(VOLCANO_STT_QUERY, json={}, headers=_base_headers)
            q_status = qresp.headers.get("X-Api-Status-Code", "")
            q_msg = qresp.headers.get("X-Api-Message", "")
            logger.info(f"STT query attempt {attempt}: status={q_status} message={q_msg}")

            if q_status in (_STATUS_PROCESSING, _STATUS_IN_QUEUE):
                continue

            if q_status == _STATUS_SILENT:
                raise STTError("STT failed: no speech detected in audio")

            if q_status == _STATUS_SUCCESS:
                qdata = qresp.json()
                result = qdata.get("result", {})
                utterances = result.get("utterances", [])
                if utterances:
                    return " ".join(u.get("text", "") for u in utterances).strip()
                return result.get("text", "").strip()

            raise STTError(f"STT query failed: code={q_status} msg={q_msg}")

    raise STTError("STT timed out after 60 seconds")
