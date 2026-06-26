"""Outbound voice-agent API: ElevenLabs Conversational AI + Twilio.

Two endpoints:
  POST /call               -> start an outbound call, INJECTING data into the agent
  POST /webhook/elevenlabs -> receive the post-call result, EXTRACTING data out

Run it (varlock injects the env vars from .env.schema / Bitwarden):
  npx varlock run -- uvicorn app:app --reload --port 8000
"""

import hashlib
import hmac
import os
import time

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

# --- Config (injected by varlock; see .env.schema) ---
XI_API_KEY = os.environ["XI_API_KEY"]
AGENT_ID = os.environ["ELEVENLABS_AGENT_ID"]
AGENT_PHONE_NUMBER_ID = os.environ["ELEVENLABS_AGENT_PHONE_NUMBER_ID"]
WEBHOOK_SECRET = os.environ["ELEVENLABS_WEBHOOK_SECRET"]

ELEVENLABS_BASE = "https://api.elevenlabs.io"

app = FastAPI(title="voice-agent-elevenlabs")


# ---------------------------------------------------------------------------
# 1) TRIGGER THE CALL  — inject data via dynamic_variables
# ---------------------------------------------------------------------------
class CallRequest(BaseModel):
    to_number: str  # E.164 format, e.g. "+14155550123"
    # Whatever your agent prompt references as {{customer_name}}, {{appointment_date}}, etc.
    dynamic_variables: dict[str, str] = {}


@app.post("/call")
async def start_call(req: CallRequest):
    """Tell ElevenLabs to dial out through your imported Twilio number.

    The values in `dynamic_variables` replace the {{placeholders}} in the
    agent's system prompt and first message.
    """
    payload = {
        "agent_id": AGENT_ID,
        "agent_phone_number_id": AGENT_PHONE_NUMBER_ID,
        "to_number": req.to_number,
        "conversation_initiation_client_data": {
            "dynamic_variables": req.dynamic_variables,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{ELEVENLABS_BASE}/v1/convai/twilio/outbound-call",
            headers={"xi-api-key": XI_API_KEY},
            json=payload,
        )

    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.text)

    # Response includes conversation_id + callSid you can store/track.
    return resp.json()


# ---------------------------------------------------------------------------
# 2) RECEIVE THE RESULT — extract collected data from the conversation
# ---------------------------------------------------------------------------
def _verify_signature(raw_body: bytes, signature_header: str) -> None:
    """Validate the ElevenLabs HMAC signature so only ElevenLabs can post here.

    Header format: "t=<unix_ts>,v0=<hex_hmac_sha256>"
    The signed message is "<t>.<raw_body>".
    """
    if not signature_header:
        raise HTTPException(401, "missing signature")

    parts = dict(p.split("=", 1) for p in signature_header.split(","))
    timestamp, sent_hash = parts.get("t"), parts.get("v0")
    if not timestamp or not sent_hash:
        raise HTTPException(401, "malformed signature")

    # Reject stale requests (replay protection): 30 min window.
    if abs(time.time() - int(timestamp)) > 30 * 60:
        raise HTTPException(401, "signature timestamp too old")

    signed = f"{timestamp}.{raw_body.decode()}".encode()
    expected = hmac.new(WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sent_hash):
        raise HTTPException(401, "bad signature")


@app.post("/webhook/elevenlabs")
async def webhook(request: Request, elevenlabs_signature: str = Header(default="")):
    """ElevenLabs POSTs here after each call ends (post-call webhook)."""
    raw = await request.body()
    _verify_signature(raw, elevenlabs_signature)

    event = await request.json()
    data = event.get("data", {})

    conversation_id = data.get("conversation_id")
    transcript = data.get("transcript")  # full turn-by-turn transcript

    # The structured fields you defined under Agent -> Analysis -> Data collection:
    analysis = data.get("analysis", {})
    collected = analysis.get("data_collection_results", {})  # {field: {value, rationale}}
    criteria = analysis.get("evaluation_criteria_results", {})  # {goal: {result, rationale}}

    # TODO: persist these to your DB / push to CRM, etc.
    print(f"[{conversation_id}] collected={collected} criteria={criteria}")

    return {"ok": True}


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Alternative to the webhook: pull a conversation's data on demand."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{ELEVENLABS_BASE}/v1/convai/conversations/{conversation_id}",
            headers={"xi-api-key": XI_API_KEY},
        )
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.text)
    return resp.json()
