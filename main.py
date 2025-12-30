import json
import os
import logging

import requests
from flask import Flask, request, jsonify

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
VERIFY_TOKEN = "my_verify_token_123"  # <--- Set this to your Meta verify token
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "YOUR_WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "YOUR_PHONE_NUMBER_ID")

QUESTIONS_FILE = "questions_master.json"
ANSWERS_FILE = "loan_user_answers_session.jsonl"

# Load questions at startup
def load_questions():
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
QUESTIONS = load_questions()

# User state tracking in-memory
USER_STATES = {}

# =====================
# HEALTH CHECK
# =====================
@app.route("/", methods=["GET"])
def health():
    return "Webhook is live 🚀"

# =====================
# WHATSAPP WEBHOOK VERIFY (GET)
# =====================
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    logger.info("Webhook verification hit")

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return challenge, 200

    logger.warning("Webhook verification failed")
    return "Forbidden", 403

# =====================
# WHATSAPP WEBHOOK MESSAGE (POST)
# =====================
@app.route("/webhook", methods=["POST"])
def receive_message():
    logger.info("Webhook POST hit")

    data = request.get_json(silent=True)
    logger.info(f"Incoming payload: {data}")

    if not data:
        return jsonify({"status": "no data"}), 200

    try:
        value = data["entry"][0]["changes"][0]["value"]

        if "messages" in value:
            message = value["messages"][0]
            sender = message["from"]
            text = message["text"]["body"].strip()

            logger.info(f"Sender: {sender}")
            logger.info(f"Text received: {text}")

            # ---- Chatbot Loan Q&A Flow ----
            text_lower = text.lower()
            if text_lower in ["loan", "start loan"]:
                # Reset user state, start Q1
                USER_STATES[sender] = {"current": 0, "answers": []}
                reply = format_question(0)
                send_whatsapp_message(sender, reply)
            # If in session, handle per-question-answer
            elif sender in USER_STATES:
                state = USER_STATES[sender]
                idx = state["current"]
                if idx < len(QUESTIONS):
                    q = QUESTIONS[idx]
                    reply_in = text
                    # Allow number/choice mapping
                    if text.isdigit():
                        cidx = int(text) - 1
                        if 0 <= cidx < len(q["choices"]):
                            reply_in = q["choices"][cidx]
                    state["answers"].append({"key": q["key"], "answer": reply_in})
                    idx += 1
                    state["current"] = idx
                # Next question or summary
                if idx < len(QUESTIONS):
                    reply = format_question(idx)
                else:
                    # Complete, store and summarize
                    store_user_answers(sender, state["answers"])
                    summary = "\n".join([f"{i+1}. {a['key'].replace('_',' ').title()}: {a['answer']}" for i, a in enumerate(state["answers"])])
                    reply = "Thank you! Your application is submitted:\n\n" + summary
                    del USER_STATES[sender]
                send_whatsapp_message(sender, reply)
            else:
                reply = ai_reply(text)
                send_whatsapp_message(sender, reply)
    except Exception:
        logger.exception("Error processing message")
    return jsonify({"status": "received"}), 200

# =====================
# FORMAT QUESTION
# =====================
def format_question(idx):
    q = QUESTIONS[idx]
    body = q["text"] + "\n"
    for i, choice in enumerate(q["choices"], 1):
        body += f"{i}. {choice}\n"
    body += "\nReply with the number or option."
    return body

# =====================
# AI FALLBACK
# =====================
def ai_reply(text: str) -> str:
    text_lower = text.strip().lower()
    if text_lower in ["hi", "hello", "hey"]:
        return "Hello 👋 How can I help you today?\nType 'loan' to begin a home loan eligibility check."
    elif text_lower == "help":
        return "Try:\n• hi\n• loan\n• pricing\n• contact"
    elif text_lower == "pricing":
        return "Our pricing starts at ₹999/month 💰"
    elif text_lower == "contact":
        return "Contact us at support@example.com 📧"
    else:
        return "Type 'loan' to check home loan eligibility."

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
    try:
        response = requests.post(url, json=payload, headers=headers)
        logger.info(f"WhatsApp send status: {response.status_code}")
        logger.info(f"WhatsApp response: {response.text}")
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message to [{to}]: {e}")

# =====================
# STORE ANSWERS IN FILE
# =====================
def store_user_answers(phone, answers):
    entry = {"phone": phone, "answers": answers}
    with open(ANSWERS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# =====================
# MAIN
# =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)