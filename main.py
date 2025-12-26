import logging
import os

import requests
from flask import Flask, jsonify, request

# =====================
# LOGGING CONFIG
# =====================
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# =====================
# CONFIG (ENV VARS)
# =====================
VERIFY_TOKEN = "my_verify_token_123"
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")


# =====================
# HEALTH CHECK
# =====================
@app.route("/", methods=["GET"])
def health():
    return "Webhook is live 🚀"


# =====================
# WEBHOOK
# =====================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    logger.info("Webhook hit")

    # ✅ Verification
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Webhook verified successfully")
            return challenge, 200

        logger.warning("Webhook verification failed")
        return "Forbidden", 403

    # ✅ Incoming message
    data = request.get_json(silent=True)
    logger.info(f"Incoming payload: {data}")

    if not data:
        return jsonify({"status": "no data"}), 200

    try:
        value = data["entry"][0]["changes"][0]["value"]

        if "messages" in value:
            message = value["messages"][0]
            sender = message["from"]
            text = message["text"]["body"].strip().lower()

            logger.info(f"Sender: {sender}")
            logger.info(f"Text received: {text}")

            reply = ai_reply(text)
            send_whatsapp_message(sender, reply)

    except Exception as e:
        logger.exception("Error processing message")

    return jsonify({"status": "received"}), 200


# =====================
# SIMPLE AI LOGIC
# =====================
def ai_reply(text: str) -> str:
    if text in ["hi", "hello", "hey"]:
        return "Hello 👋 How can I help you today?"
    elif text == "help":
        return "Try:\n• hi\n• pricing\n• contact"
    elif text == "pricing":
        return "Our pricing starts at ₹999/month 💰"
    elif text == "contact":
        return "Contact us at support@example.com 📧"
    else:
        return "🤖 I’m still learning. Try *hi* or *help*."


# =====================
# SEND WHATSAPP MESSAGE
# =====================
def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    payload = {"messaging_product": "whatsapp", "to": to, "text": {"body": text}}

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers)
    logger.info(f"WhatsApp send status: {response.status_code}")
    logger.info(f"WhatsApp response: {response.text}")


# =====================
# START
# =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
