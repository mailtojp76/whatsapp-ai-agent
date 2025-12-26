import logging
import os

import requests
from flask import Flask, jsonify, request

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

VERIFY_TOKEN = "my_verify_token_123"
# =====================
# CONFIG
# =====================
VERIFY_TOKEN = "my_verify_token_123"
ACCESS_TOKEN = "EAATTWBiJcfABQQe9m5yRmgxZCm0wNLoE2Qx40WUP69A3Ltd2ZCpDfzwuHH7kEuT3UQZBzZCmDqSw0L50abxCmNimvUA5sbv9Yv1xKoykllZCZBtgHucxnXc9ZBeLSmwZAcpdeQqRZBAphg4uYPZAVEP9XckrQ96TrgB4FbI7Nq4PeiZCQxYPgaMTQmyfiqxYiSZCuYNNawWvhEZBfZBJFCXq4jy3sUyiUedx8bvo2UYB1KFhZAfFO5pn586Ijh83dEvUvGD9qWLKOUHXBvef9dAAlAnEtpl2mVZC"
PHONE_NUMBER_ID = "947839265078025"


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
    logger.info(f"wehook triggered1")
    # ✅ Step 1: Webhook verification
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("Webhook verified successfully")
            return challenge, 200
        else:
            print("Webhook verification failed")
            return "Forbidden", 403

    # ✅ Step 2: Receive messages
    data = request.get_json(silent=True)
    logger.info(f"Incoming payload: {data}")

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" in value:
            message = value["messages"][0]
            sender = message["from"]
            text = message["text"]["body"].strip().lower()

            logger.info(f"Sender: {sender}")
            logger.info(f"Text received: {text}")
            logger.error(f"Error processing message: {e}")

            reply = ai_reply(text)
            send_whatsapp_message(sender, reply)

    except Exception as e:
        print("Error processing message:", e)
        logger.error(f"Error processing message: {e}")

    return jsonify({"status": "received"}), 200


# =====================
# SIMPLE AI FUNCTION
# =====================
def ai_reply(text: str) -> str:
    if text in ["hi", "hello", "hey"]:
        return "Hello 👋 How can I help you today?"
    elif text == "help":
        return "Here are some things you can try:\n" "• hi\n" "• pricing\n" "• contact"
    elif text == "pricing":
        return "Our pricing starts at ₹999/month 💰"
    elif text == "contact":
        return "You can reach us at support@example.com 📧"
    else:
        return "🤖 I’m still learning.\n" "Try typing *hi* or *help*."


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
    print("Send response:", response.status_code, response.text)


# @app.route("/", methods=["GET"])
# def health():
#     return "Webhook is live 🚀"


# @app.route("/webhook", methods=["GET", "POST"])
# def webhook():

#     # ✅ Step 1: Webhook verification (Meta calls this)
#     if request.method == "GET":
#         mode = request.args.get("hub.mode")
#         token = request.args.get("hub.verify_token")
#         challenge = request.args.get("hub.challenge")

#         if mode == "subscribe" and token == VERIFY_TOKEN:
#             print("Webhook verified successfully")
#             return challenge, 200
#         else:
#             print("Webhook verification failed")
#             return "Forbidden", 403

#     # ✅ Step 2: Incoming messages (POST)
#     data = request.get_json(silent=True)
#     print("Incoming payload:", data)

#     return jsonify({"status": "received"}), 200


if __name__ == "__main__":
    port = 5000
    app.run(host="0.0.0.0", port=port)
