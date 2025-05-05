from flask import Flask, request, jsonify, Response
import threading
import time
import os
import json

app = Flask(__name__)
running_bots = {}
active_bots_file = "active_bots.json"

# Cargar bots activos al iniciar el servidor


def load_active_bots():
    if os.path.exists(active_bots_file):
        try:
            with open(active_bots_file, "r") as f:
                bots = json.load(f)
            for bot in bots:
                start_bot_worker(bot["id"], bot)
            print("✅ Bots restaurados desde active_bots.json")
        except Exception as e:
            print(f"[ERROR] Cargando bots activos: {e}")

# Guardar bots activos en JSON


def save_active_bots():
    try:
        bots_data = []
        for bot_id, data in running_bots.items():
            bots_data.append({"id": bot_id, **data["config"]})
        with open(active_bots_file, "w") as f:
            json.dump(bots_data, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Guardando bots activos: {e}")

# Lógica del bot en segundo plano


def bot_worker(bot_id, config):
    while config.get("running", False):
        print(f"[{bot_id}] Ejecutando bot con configuración: {config}")
        time.sleep(5)
    print(f"[{bot_id}] Bot detenido.")

# Lanzar un bot


def start_bot_worker(bot_id, config):
    config["running"] = True
    thread = threading.Thread(
        target=bot_worker, args=(bot_id, config), daemon=True)
    running_bots[bot_id] = {"thread": thread, "config": config}
    thread.start()
    save_active_bots()

# Detener un bot


def stop_bot_worker(bot_id):
    bot = running_bots.get(bot_id)
    if bot:
        bot["config"]["running"] = False
        running_bots.pop(bot_id)
        save_active_bots()

# Logs de entrada


@app.before_request
def log_request():
    print(f"[{request.method}] {request.url} | Body: {request.get_data()}")

# Página raíz


@app.route("/")
def index():
    return Response("<h1>Bot server is online</h1><p>Use /api/start_bot para iniciar</p>", mimetype="text/html")

# Iniciar un bot desde la interfaz


@app.route("/api/start_bot", methods=["POST"])
def start_bot():
    data = request.json
    bot_id = data.get("id")
    if not bot_id:
        return jsonify({"error": "Falta el ID del bot"}), 400
    if bot_id in running_bots:
        return jsonify({"error": f"Bot '{bot_id}' ya está en ejecución"}), 400

    start_bot_worker(bot_id, data)
    return jsonify({"status": f"Bot '{bot_id}' iniciado en el servidor"})

# Detener un bot


@app.route("/api/stop_bot", methods=["POST"])
def stop_bot():
    data = request.json
    bot_id = data.get("id")
    if bot_id not in running_bots:
        return jsonify({"error": f"Bot '{bot_id}' no está en ejecución"}), 404

    stop_bot_worker(bot_id)
    return jsonify({"status": f"Bot '{bot_id}' detenido"})

# Listar bots en ejecución


@app.route("/api/bots", methods=["GET"])
def list_bots():
    return jsonify({"bots": list(running_bots.keys())})

# Recibir reporte de bots (opcional, para sincronizar)


@app.route("/api/report_bots", methods=["POST"])
def report_bots():
    data = request.json
    print("📥 Lista de bots recibida desde la interfaz:")
    for bot in data:
        print(f" - {bot['symbol']} en {bot['exchange']}")
    return jsonify({"status": "Bots reportados correctamente"})

# Recibir configuración (opcional)


@app.route("/api/config", methods=["POST"])
def config():
    data = request.json
    print("📥 Configuración recibida:", data)
    return jsonify({"status": "Configuración guardada"})



@app.route("/api/bot_status", methods=["GET"])
def bot_status():
    bot_id = request.args.get("id")
    bot = running_bots.get(bot_id)
    if not bot:
        return jsonify({"error": "Bot no encontrado"}), 404
    return jsonify(bot["config"])


# Iniciar servidor
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("🟢 Iniciando servidor...")
    load_active_bots()
    app.run(host="0.0.0.0", port=port)
