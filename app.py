from flask import Flask, request, jsonify
import threading
import time

app = Flask(__name__)

# Diccionario para guardar bots activos
active_bots = {}

# Función simulada del bot


def run_bot(bot_id, config):
    print(f"Bot {bot_id} iniciado con config:", config)
    while active_bots.get(bot_id, {}).get("running"):
        time.sleep(5)
        print(f"Bot {bot_id} ejecutándose...")

    print(f"Bot {bot_id} detenido.")

# Ruta para iniciar un bot


@app.route("/api/bots/start", methods=["POST"])
def start_bot():
    data = request.json
    bot_id = data["id"]
    config = data["config"]

    if bot_id in active_bots and active_bots[bot_id]["running"]:
        return jsonify({"error": "Bot ya está en ejecución"}), 400

    active_bots[bot_id] = {
        "config": config,
        "running": True
    }

    t = threading.Thread(target=run_bot, args=(bot_id, config))
    t.start()

    return jsonify({"status": f"Bot {bot_id} iniciado"})

# Ruta para detener un bot


@app.route("/api/bots/stop", methods=["POST"])
def stop_bot():
    data = request.json
    bot_id = data["id"]

    if bot_id not in active_bots or not active_bots[bot_id]["running"]:
        return jsonify({"error": "Bot no está en ejecución"}), 400

    active_bots[bot_id]["running"] = False
    return jsonify({"status": f"Bot {bot_id} detenido"})

# Ruta para listar bots activos


@app.route("/api/bots", methods=["GET"])
def list_bots():
    return jsonify(active_bots)

# Ruta simple de verificación


@app.route("/")
def home():
    return "<h1>Bot server online</h1>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
