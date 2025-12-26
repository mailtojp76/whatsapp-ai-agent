import json
import logging
import os

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from flask import Flask, jsonify, request

# ---------------- Logging Setup ----------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("whatsapp-webhook")

# ---------------- App Setup ----------------
app = FastAPI()


VERIFY_TOKEN = "ABCD1234"
ACCESS_TOKEN = "EAATTWBiJcfABQdv4ZAb2Jwxp2kx2flJ6yPWXde8HyThO3AvlGaVjYoZAWcAbsNH8ZAbPJJ2cCCM0h6wPi3VELlzYYuBpktqWWNPghkURfWoqZCZBnCB3vYsdgCxL7hUC2m7GN9vXGaiBWIZBJ5RzlbeZBEkh0r2BUf4K65KZBE9vMZAjDtND6Y8yu0XbCtAOyibHBOgZArt9XPKZBsTWBsnqPUCsaL3t8QkbqJlzo5OAKelJ7dODUFAiHAPuHvgTAyzZB6Bik1JKVeEjX1QVXpmmZAbhyHlQaVwZDZD"
PHONE_NUMBER_ID = "947839265078025"


# ---------------- Health Check ----------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.route("/webhook", methods=["GET"])
def verify_webhook(request: Request):
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def receive_message(request: Request):
    data = request.json
    print("Incoming:", data)

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = message["from"]
        text = message["text"]["body"]

        send_message(sender, f"You said: {text}")

    except Exception as e:
        print("Error:", e)

    return jsonify(status="ok"), 200


def send_message(to, text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    payload = {"messaging_product": "whatsapp", "to": to, "text": {"body": text}}

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    requests.post(url, json=payload, headers=headers)


# ---------------- Webhook Verification ----------------
# @app.get("/webhook", response_class=PlainTextResponse)
# async def verify_webhook(request: Request):
#     mode = request.query_params.get("hub.mode")
#     token = request.query_params.get("hub.verify_token")
#     challenge = request.query_params.get("hub.challenge")

#     logger.info(f"Verification request received | mode={mode}")

#     if mode == "subscribe" and token == VERIFY_TOKEN:
#         logger.info("Webhook verified successfully")
#         return challenge

#     logger.error("Webhook verification failed")
#     raise HTTPException(status_code=403, detail="Verification failed")

# # ---------------- Webhook Receiver ----------------
# @app.post("/webhook")
# async def receive_webhook(request: Request):
#     payload = await request.json()

#     logger.info("Webhook event received")
#     logger.debug(json.dumps(payload, indent=2))

#     # Extract useful info if present
#     try:
#         entry = payload.get("entry", [])[0]
#         change = entry.get("changes", [])[0]
#         value = change.get("value", {})

#         if "messages" in value:
#             logger.info("Incoming user message detected")

#         if "statuses" in value:
#             status = value["statuses"][0]
#             logger.info(
#                 f"Message status update | "
#                 f"id={status.get('id')} | "
#                 f"status={status.get('status')}"
#             )

#             if status.get("status") == "failed":
#                 logger.error(f"Message failed | errors={status.get('errors')}")

#     except Exception as e:
#         logger.warning(f"Failed to parse webhook payload: {e}")

#     return {"status": "ok"}
