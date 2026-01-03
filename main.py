import json
import logging
import os

import psycopg2
import requests
from flask import Flask, jsonify, request
from psycopg2.extras import Json

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

VERIFY_TOKEN = "my_verify_token_123"
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "YOUR_WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "YOUR_PHONE_NUMBER_ID")
QUESTIONS_FILE = "questions_master.json"
# PG_URL = os.environ.get("DATABASE_URL", "postgresql://user:pass@host:5432/dbname")
PG_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://whatsapp_ai_agent_db_user:rXi4qo6nzf7Z4UV772z11s5s2skdRff5@dpg-d5bc1s75r7bs73aae900-a/whatsapp_ai_agent_db",
)
# internal
# postgresql://whatsapp_ai_agent_db_user:rXi4qo6nzf7Z4UV772z11s5s2skdRff5@dpg-d5bc1s75r7bs73aae900-a/whatsapp_ai_agent_db

# external
# postgresql://whatsapp_ai_agent_db_user:rXi4qo6nzf7Z4UV772z11s5s2skdRff5@dpg-d5bc1s75r7bs73aae900-a.virginia-postgres.render.com/whatsapp_ai_agent_db


def get_conn():
    return psycopg2.connect(PG_URL, sslmode="require")


def load_questions():
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


QUESTIONS = load_questions()
USER_STATES = {}


def log_to_db(level, message, logger_name=None, extra=None):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO app_logs (level, logger, message, extra) VALUES (%s, %s, %s, %s)",
                    (level, logger_name, message, Json(extra) if extra else None),
                )
                conn.commit()
    except Exception as e:
        print(f"DB LOGGING ERROR: {e}: {message}")


@app.route("/", methods=["GET"])
def health():
    return "Webhook is live 🚀"


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        log_to_db("INFO", "Webhook verified", "verify_webhook")
        return challenge, 200
    logger.warning("Webhook verification failed")
    log_to_db("WARNING", "Webhook verification failed", "verify_webhook")
    return "Forbidden", 403


def extract_user_text(message):
    msg_type = message.get("type")
    # Button type: either from 'button.text' or fallback to text.body
    if msg_type == "button":
        btn = message.get("button")
        if btn and "text" in btn and btn["text"]:
            return btn["text"]
        txt = message.get("text")
        if txt and "body" in txt and txt["body"]:
            return txt["body"]
        return ""
    # List reply type: from list_reply.title
    if msg_type == "list_reply":
        list_reply = message.get("list_reply")
        if list_reply and "title" in list_reply and list_reply["title"]:
            return list_reply["title"]
        return ""
    # Regular text
    if message.get("text") and message["text"].get("body"):
        return message["text"]["body"].strip()
    # Other types
    return ""


@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json(silent=True)
    logger.info(f"Payload: {data}")
    log_to_db("INFO", "Received webhook POST", "receive_message", {"payload": data})
    if not data:
        log_to_db("WARNING", "No data in POST", "receive_message")
        return jsonify({"status": "no data"}), 200
    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" in value:
            message = value["messages"][0]
            sender = message["from"]
            text = extract_user_text(message)
            logger.info(f"Sender: {sender}, Text: {text}, Type: {message.get('type')}")
            log_to_db(
                "INFO",
                f"Handle msg: {text}",
                "receive_message",
                {"sender": sender, "type": message.get("type")},
            )

            text_lower = text.lower()
            if text_lower in ["loan", "start loan"]:
                USER_STATES[sender] = {"current": 0, "answers": []}
                send_question(sender, 0)
                log_to_db(
                    "INFO", f"Started loan session", "chatbot", {"sender": sender}
                )
            elif sender in USER_STATES:
                state = USER_STATES[sender]
                idx = state["current"]
                if idx < len(QUESTIONS):
                    q = QUESTIONS[idx]
                    state["answers"].append({"key": q["key"], "answer": text})
                    idx += 1
                    state["current"] = idx
                if idx < len(QUESTIONS):
                    send_question(sender, idx)
                else:
                    store_user_answers_db(sender, state["answers"])
                    summary = "\n".join(
                        [
                            f"{i+1}. {a['key'].replace('_',' ').title()}: {a['answer']}"
                            for i, a in enumerate(state["answers"])
                        ]
                    )
                    reply = "Thank you! Your application is submitted:\n\n" + summary
                    send_whatsapp_message(sender, reply)
                    log_to_db(
                        "INFO",
                        "Session completed",
                        "chatbot",
                        {"sender": sender, "answers": state["answers"]},
                    )
                    del USER_STATES[sender]
            else:
                reply = ai_reply(text)
                send_whatsapp_message(sender, reply)
                log_to_db(
                    "INFO",
                    "AI replied to unknown state",
                    "chatbot",
                    {"sender": sender, "text": text},
                )
    except Exception as e:
        logger.exception("Error processing message")
        log_to_db("ERROR", str(e), "receive_message", {"data": data})
    return jsonify({"status": "received"}), 200


@app.route("/webhook", methods=["POST"])
def receive_message_old():
    data = request.get_json(silent=True)
    logger.info(f"Payload: {data}")
    log_to_db("INFO", "Received webhook POST", "receive_message", {"payload": data})
    if not data:
        log_to_db("WARNING", "No data in POST", "receive_message")
        return jsonify({"status": "no data"}), 200
    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" in value:
            message = value["messages"][0]
            sender = message["from"]
            msg_type = message.get("type")
            if msg_type == "button":
                text = (
                    (message.get("button") or {}).get("text")
                    or (message.get("text") or {}).get("body")
                    or ""
                )
            elif msg_type == "list_reply":
                text = (message.get("list_reply") or {}).get("title") or ""
            elif message.get("text") and message["text"].get("body") is not None:
                text = message["text"]["body"].strip()
            else:
                text = ""
            logger.info(f"Sender: {sender}, Text: {text}, Type: {msg_type}")
            log_to_db(
                "INFO",
                f"Handle msg: {text}",
                "receive_message",
                {"sender": sender, "type": msg_type},
            )

            text_lower = text.lower()
            if text_lower in ["loan", "start loan"]:
                USER_STATES[sender] = {"current": 0, "answers": []}
                send_question(sender, 0)
                log_to_db(
                    "INFO", f"Started loan session", "chatbot", {"sender": sender}
                )
            elif sender in USER_STATES:
                state = USER_STATES[sender]
                idx = state["current"]
                if idx < len(QUESTIONS):
                    q = QUESTIONS[idx]
                    state["answers"].append({"key": q["key"], "answer": text})
                    idx += 1
                    state["current"] = idx
                if idx < len(QUESTIONS):
                    send_question(sender, idx)
                else:
                    store_user_answers_db(sender, state["answers"])
                    summary = "\n".join(
                        [
                            f"{i+1}. {a['key'].replace('_',' ').title()}: {a['answer']}"
                            for i, a in enumerate(state["answers"])
                        ]
                    )
                    reply = "Thank you! Your application is submitted:\n\n" + summary
                    send_whatsapp_message(sender, reply)
                    log_to_db(
                        "INFO",
                        "Session completed",
                        "chatbot",
                        {"sender": sender, "answers": state["answers"]},
                    )
                    del USER_STATES[sender]
            else:
                reply = ai_reply(text)
                send_whatsapp_message(sender, reply)
                log_to_db(
                    "INFO",
                    "AI replied to unknown state",
                    "chatbot",
                    {"sender": sender, "text": text},
                )
    except Exception as e:
        logger.exception("Error processing message")
        log_to_db("ERROR", str(e), "receive_message", {"data": data})
    return jsonify({"status": "received"}), 200


def send_question(to, idx):
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
        log_to_db(
            "INFO",
            f"Send WhatsApp [{to}]",
            "send_whatsapp_payload",
            {"payload": payload, "status_code": resp.status_code},
        )
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message to [{to}]: {e}")
        log_to_db(
            "ERROR",
            f"Failed WhatsApp send to {to}: {e}",
            "send_whatsapp_payload",
            {"payload": payload},
        )


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


def store_user_answers_db(phone, answers):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO loan_user_answers (phone, answer) VALUES (%s, %s)",
                    (phone, Json(answers)),
                )
                conn.commit()
        logger.info(f"Stored user answers for {phone} in DB")
        log_to_db(
            "INFO",
            "Stored user answers",
            "store_user_answers_db",
            {"phone": phone, "answers": answers},
        )
    except Exception as e:
        logger.error(f"Could not store answers for {phone}: {e}")
        log_to_db(
            "ERROR",
            f"Unable to store answers: {e}",
            "store_user_answers_db",
            {"phone": phone, "answers": answers},
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
