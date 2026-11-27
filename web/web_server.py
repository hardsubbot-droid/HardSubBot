import asyncio
import hmac
import logging
from flask import Flask, request, jsonify
from telegram import Update

log = logging.getLogger(__name__)
telegram_application = None
telegram_loop = None

def set_telegram_runtime(application, loop):
    global telegram_application, telegram_loop
    telegram_application = application
    telegram_loop = loop

def create_flask_app(is_ready):
    app = Flask(__name__)

    @app.get("/")
    def home():
        return "HardSubBot is running", 200

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "telegram_ready": bool(is_ready())}), 200

    @app.post("/telegram/webhook")
    def telegram_webhook():
        if telegram_application is None or telegram_loop is None or not is_ready():
            return jsonify({"error": "Telegram application is not ready"}), 503

        from config import WEBHOOK_SECRET
        if WEBHOOK_SECRET:
            supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if not hmac.compare_digest(supplied, WEBHOOK_SECRET):
                return jsonify({"error": "unauthorized"}), 403

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "invalid update"}), 400

        try:
            update = Update.de_json(data, telegram_application.bot)
            telegram_loop.call_soon_threadsafe(
                telegram_application.update_queue.put_nowait, update
            )
            return jsonify({"ok": True}), 200
        except Exception:
            log.exception("Could not enqueue Telegram update")
            return jsonify({"error": "internal error"}), 500

    return app
