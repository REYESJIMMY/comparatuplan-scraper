import hmac
import hashlib
import json
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL    = os.getenv("SUPABASE_WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
ANON_KEY       = os.getenv("SUPABASE_ANON_KEY")

def _sign(payload: bytes) -> str:
    """Genera firma HMAC-SHA256 del payload."""
    return hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

async def send_plans(plans: list[dict]) -> None:
    if not WEBHOOK_URL or not WEBHOOK_SECRET or not ANON_KEY:
        raise ValueError("Faltan SUPABASE_WEBHOOK_URL, WEBHOOK_SECRET o SUPABASE_ANON_KEY en .env")

    payload = json.dumps({"plans": plans}, ensure_ascii=False).encode("utf-8")
    signature = _sign(payload)

    headers = {
        "Content-Type":     "application/json",
        "Authorization":    f"Bearer {ANON_KEY}",
        "x-webhook-secret": signature,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(WEBHOOK_URL, data=payload, headers=headers) as resp:
            if resp.status not in (200, 201):
                body = await resp.text()
                raise Exception(f"Webhook error {resp.status}: {body}")
            print(f"✅ Webhook respondió {resp.status}")