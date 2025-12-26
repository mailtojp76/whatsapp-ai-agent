import os

from flask import Flask, jsonify, request

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_verify_token_123")


@app.route("/", methods=["GET"])
def health():
    return "Webhook is live 🚀"


@app.route("/webhook", methods=["GET", "POST"])
def webhook():

    # ✅ Step 1: Webhook verification (Meta calls this)
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

    # ✅ Step 2: Incoming messages (POST)
    data = request.get_json(silent=True)
    print("Incoming payload:", data)

    return jsonify({"status": "received"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
