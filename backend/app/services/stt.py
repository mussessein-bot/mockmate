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


_STT_HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": "",           # filled at call time
    "X-Api-Resource-Id": VOLCANO_STT_RESOURCE,
}


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

    headers = {
        "Content-Type": "application/json",
        "x-api-key": VOLCANO_SPEECH_KEY,
        "X-Api-Resource-Id": VOLCANO_STT_RESOURCE,
        "X-Api-Request-Id": req_id,
        "X-Api-Sequence": "-1",
    }

    # Detect format from filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"

    submit_body = {
        "user": {"uid": "mockmate"},
        "audio": {
            "url": audio_url,
            "format": ext,
            "codec": "raw",
            "rate": 16000,
            "bits": 16,
            "channel": 1,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": False,
            "enable_speaker_info": False,
            "show_utterances": False,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Submit
        resp = await client.post(VOLCANO_STT_SUBMIT, json=submit_body, headers=headers)
        resp.raise_for_status()
        submit_data = resp.json()

        logger.info(f"STT submit response: {submit_data}")
        code = submit_data.get("resp", {}).get("code", 0)  # treat missing as OK
        if code not in (0, 1000):
            raise STTError(f"STT submit failed: {submit_data}")

        # Step 2: Poll for result (max 60 seconds, 2s interval)
        query_headers = {
            "Content-Type": "application/json",
            "x-api-key": VOLCANO_SPEECH_KEY,
            "X-Api-Resource-Id": VOLCANO_STT_RESOURCE,
            "X-Api-Request-Id": req_id,
        }

        for attempt in range(30):
            await asyncio.sleep(2)
            qresp = await client.post(VOLCANO_STT_QUERY, json={}, headers=query_headers)
            qresp.raise_for_status()
            qdata = qresp.json()

            logger.info(f"STT query attempt {attempt}: {qdata}")

            # Volcano may return result directly without resp.code
            if "result" in qdata:
                result = qdata.get("result", {})
                utterances = result.get("utterances", [])
                if utterances:
                    return " ".join(u.get("text", "") for u in utterances).strip()
                return result.get("text", "").strip()

            resp_obj = qdata.get("resp", {})
            q_code = resp_obj.get("code", -1)

            if q_code == 1000:  # still processing
                continue
            if q_code == 0:  # success with resp.code format
                result = qdata.get("result", {})
                utterances = result.get("utterances", [])
                if utterances:
                    return " ".join(u.get("text", "") for u in utterances).strip()
                return result.get("text", "").strip()
            else:
                raise STTError(f"STT query failed: {qdata}")

    raise STTError("STT timed out after 60 seconds")
