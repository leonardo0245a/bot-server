import os
import threading
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

# Diccionario global para controlar los bots
active_bots = {}

# Función simulada de un bot


def run_bot(bot_id, symbol, monto):
    while active_bots.get(bot_id, {}).get("running"):
        print(f"🟢 Bot {bot_id} ejecutando con {symbol} y monto {monto}")
        time.sleep(5)
    print(f"🔴 Bot {bot_id} detenido")


@app.route("/api/start_bot", methods=["POST"])
def start_bot():
    data = request.json
    bot_id = data["id"]
    symbol = data["symbol"]
    monto = data["monto"]

    # Si ya está activo, detenerlo primero
    if bot_id in active_bots and active_bots[bot_id]["running"]:
        return jsonify({"error": "Este bot ya está en ejecución"}), 400

    active_bots[bot_id] = {
        "symbol": symbol,
        "monto": monto,
        "running": True,
        "thread": threading.Thread(target=run_bot, args=(bot_id, symbol, monto))
    }

    active_bots[bot_id]["thread"].start()
    return jsonify({"status": f"Bot {bot_id} iniciado correctamente"})


@app.route("/api/stop_bot", methods=["POST"])
def stop_bot():
    data = request.json
    bot_id = data["id"]

    if bot_id in active_bots and active_bots[bot_id]["running"]:
        active_bots[bot_id]["running"] = False
        return jsonify({"status": f"Bot {bot_id} detenido"})
    return jsonify({"error": "Bot no está en ejecución"}), 400


@app.route("/api/bots", methods=["GET"])
def list_bots():
    estado = {bot_id: {
        "symbol": bot["symbol"],
        "monto": bot["monto"],
        "running": bot["running"]
    } for bot_id, bot in active_bots.items()}
    return jsonify(estado)


@app.route("/")
def home():
    return "<h1>Servidor de bots está activo</h1>"
