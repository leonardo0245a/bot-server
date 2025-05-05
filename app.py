from flask import Flask, request, jsonify, Response
import threading
import time
import os

app = Flask(__name__)
running_bots = {}

# Log de todas las solicitudes entrantes (útil para depurar)


@app.before_request
def log_request_info():
    print(
        f"Request: {request.method} {request.url} | Body: {request.get_data()}")

# Simulación de bot en segundo plano


def bot_worker(bot_id, config):
    while config["running"]:
        print(f"[{bot_id}] Ejecutando bot con configuración: {config}")
        time.sleep(5)

# Página de prueba


@app.route("/")
def index():
    return Response("<h1>Bot server is online</h1><p>Use /api/start_bot para iniciar</p>", mimetype='text/html')

# Iniciar bot


@app.route("/api/start_bot", methods=["POST"])
def start_bot():
    data = request.json
    bot_id = data.get("id")
    if not bot_id:
        return jsonify({"error": "Falta el ID del bot"}), 400
    if bot_id in running_bots:
        return jsonify({"error": f"Bot '{bot_id}' ya está en ejecución"}), 400

    config = {"running": True, **data}
    thread = threading.Thread(
        target=bot_worker, args=(bot_id, config), daemon=True)
    running_bots[bot_id] = {"thread": thread, "config": config}
    thread.start()
    return jsonify({"status": f"Bot '{bot_id}' iniciado"})

# Detener bot


@app.route("/api/stop_bot", methods=["POST"])
def stop_bot():
    data = request.json
    bot_id = data.get("id")
    bot = running_bots.get(bot_id)
    if not bot:
        return jsonify({"error": f"Bot '{bot_id}' no encontrado"}), 404

    bot["config"]["running"] = False
    return jsonify({"status": f"Bot '{bot_id}' detenido"})

# Obtener bots activos


@app.route("/api/bots", methods=["GET"])
def list_bots():
    return jsonify({"bots": list(running_bots.keys())})


# Recibir bots desde cliente
@app.route("/api/report_bots", methods=["POST"])
def report_bots():
    data = request.json
    print("📥 Lista de bots recibida desde cliente:")
    for bot in data:
        print(f"  - {bot['symbol']} en {bot['exchange']}")
    return jsonify({"status": "Bots recibidos correctamente"})


# Ejecutar localmente o en Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
