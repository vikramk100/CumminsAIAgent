"""
Simple Flask backend for the AI agent chat.
Delegates all AI logic to the LangChain-based multi-agent orchestrator.
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

load_dotenv()

app = Flask(__name__, static_folder="static")
CORS(app)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not GEMINI_API_KEY:
    raise ValueError("Set GEMINI_API_KEY in .env")


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Missing 'message' in body"}), 400
    user_message = data["message"]
    print(f"User message: {user_message}")
    try:
        from agents import run_orchestrator
        print(f"About to call run_orchestrator")

        text = run_orchestrator(user_message)

        return jsonify({"reply": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
