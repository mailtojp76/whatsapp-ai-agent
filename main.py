import json
import logging
import os

import requests
from flask import Flask, jsonify, request

# --- Logging ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- App config and questions ---
app = Flask(__name__)
VERIFY_TOKEN = "my_verify_token_123"
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "YOUR_WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "YOUR_PHONE_NUMBER_ID")
QUESTIONS_FILE = "questions_master.json"
ANSWERS_FILE = "loan_user_answers_session.jsonl"


def load_questions():
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


QUESTIONS = load_questions()

USER_STATES = {}


# --- Health/Meta platform verification GET ---
@app.route("/", methods=["GET"])
def health():
    return "Webhook is live 🚀"


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


# --- Main WhatsApp webhook POST ---
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

            # --- DETERMINE what kind of reply user sent
            msg_type = message.get("type")

            if msg_type == "button":
                # Button reply: user clicked a button
                text = (
                    (message.get("button") or {}).get("text")
                    or (message.get("text") or {}).get(
                        "body"
                    )  # sometimes redundant, but adds safety
                    or ""
                )
            elif msg_type == "list_reply":
                # List reply: user picked from a list
                text = (message.get("list_reply") or {}).get("title") or ""
            elif message.get("text") and message["text"].get("body") is not None:
                # Standard WhatsApp text message
                text = message["text"]["body"].strip()
            else:
                # Fallback for unrecognized/no text
                text = ""

            # --- DETERMINE what kind of reply user sent
            # msg_type = message.get("type")
            # if msg_type == "button":
            #     text = message.get("button", {}).get("text") or message.get("text", {}).get("body")
            # elif msg_type == "list_reply":
            #     text = message.get("list_reply", {}).get("title")
            # else:
            #     text = message.get("text", {}).get("body").strip()

            logger.info(f"Sender: {sender}")
            logger.info(f"Text received: {text} (msg type: {msg_type})")

            # --- Main chat logic ---
            text_lower = text.lower()
            if text_lower in ["loan", "start loan"]:
                USER_STATES[sender] = {"current": 0, "answers": []}
                send_question(sender, 0)
            elif sender in USER_STATES:
                state = USER_STATES[sender]
                idx = state["current"]
                if idx < len(QUESTIONS):
                    q = QUESTIONS[idx]
                    state["answers"].append({"key": q["key"], "answer": text})
                    idx += 1
                    state["current"] = idx
                # Ask next or finish
                if idx < len(QUESTIONS):
                    send_question(sender, idx)
                else:
                    store_user_answers(sender, state["answers"])
                    summary = "\n".join(
                        [
                            f"{i+1}. {a['key'].replace('_',' ').title()}: {a['answer']}"
                            for i, a in enumerate(state["answers"])
                        ]
                    )
                    reply = "Thank you! Your application is submitted:\n\n" + summary
                    send_whatsapp_message(sender, reply)
                    del USER_STATES[sender]
            else:
                reply = ai_reply(text)
                send_whatsapp_message(sender, reply)
    except Exception:
        logger.exception("Error processing message")
    return jsonify({"status": "received"}), 200


# --- Helpers for sending WhatsApp questions as interactive messages ---
def send_question(to, idx):
    """Send the idx-th question via WhatsApp, using buttons or list."""
    q = QUESTIONS[idx]
    choices = q["choices"]
    if len(choices) <= 3:
        send_whatsapp_buttons(to, q["text"], choices)
    else:
        send_whatsapp_list(to, q["text"], choices)


def send_whatsapp_buttons(to, question, choices):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    buttons = [
        {"type": "reply", "reply": {"id": f"choice_{i}", "title": c}}
        for i, c in enumerate(choices, 1)
    ]
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": question},
            "action": {"buttons": buttons},
        },
    }
    send_whatsapp_payload(payload, to)


def send_whatsapp_list(to, question, choices):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    sections = [
        {
            "title": "Options",
            "rows": [
                {"id": f"choice_{i}", "title": c} for i, c in enumerate(choices, 1)
            ],
        }
    ]
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "Select an answer below"},
            "body": {"text": question},
            "footer": {"text": "Tap to expand options"},
            "action": {"button": "Choose...", "sections": sections},
        },
    }
    send_whatsapp_payload(payload, to)


def send_whatsapp_message(to, text):
    """Send plain WhatsApp text message."""
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    payload = {"messaging_product": "whatsapp", "to": to, "text": {"body": text}}
    send_whatsapp_payload(payload, to)


def send_whatsapp_payload(payload, to):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers)
        logger.info(f"WhatsApp [{to}] resp: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message to [{to}]: {e}")


# --- AI fallback answer ---
def ai_reply(text):
    t = text.lower().strip()
    if t in ["hi", "hello", "hey"]:
        return "Hello 👋 How can I help you today?\nType 'loan' to begin a home loan eligibility check."
    elif t == "help":
        return "Try:\n• hi\n• loan\n• pricing\n• contact"
    elif t == "pricing":
        return "Our pricing starts at ₹999/month 💰"
    elif t == "contact":
        return "Contact us at support@example.com 📧"
    else:
        return "Type 'loan' to check home loan eligibility."


# --- File storage on completion ---
def store_user_answers(phone, answers):
    entry = {"phone": phone, "answers": answers}
    with open(ANSWERS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --- Start Flask app ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
