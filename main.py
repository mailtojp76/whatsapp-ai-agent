
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
import os
import json
import logging

# ---------------- Logging Setup ----------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("whatsapp-webhook")

# ---------------- App Setup ----------------
app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "change_me")

# ---------------- Health Check ----------------
@app.get("/health")
async def health():
    return {"status": "ok"}

# ---------------- Webhook Verification ----------------
@app.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    logger.info(f"Verification request received | mode={mode}")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return challenge

    logger.error("Webhook verification failed")
    raise HTTPException(status_code=403, detail="Verification failed")

# ---------------- Webhook Receiver ----------------
@app.post("/webhook")
async def receive_webhook(request: Request):
    payload = await request.json()

    logger.info("Webhook event received")
    logger.debug(json.dumps(payload, indent=2))

    # Extract useful info if present
    try:
        entry = payload.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        value = change.get("value", {})

        if "messages" in value:
            logger.info("Incoming user message detected")

        if "statuses" in value:
            status = value["statuses"][0]
            logger.info(
                f"Message status update | "
                f"id={status.get('id')} | "
                f"status={status.get('status')}"
            )

            if status.get("status") == "failed":
                logger.error(f"Message failed | errors={status.get('errors')}")

    except Exception as e:
        logger.warning(f"Failed to parse webhook payload: {e}")

    return {"status": "ok"}
