from flask import Response
from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)


@app.route("/api/config", methods=["POST"])
def save_config():
    data = request.json
    print("✔ Recibido /api/config:", data)  # <-- Añade esto para ver datos
    with open("config.json", "w") as f:
        json.dump(data, f, indent=4)
    return jsonify({"status": "config saved"})


@app.route("/api/bots", methods=["POST"])
def save_bots():
    data = request.json
    print("✔ Recibido /api/bots:", data)  # <-- Añade esto también
    with open("bots.json", "w") as f:
        json.dump(data, f, indent=4)
    return jsonify({"status": "bots saved"})


@app.route("/api/ping")
def ping():
    return jsonify({"status": "online"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


@app.route("/")
def home():
    html = "<h1>Bot server is online</h1><p>Everything is working!</p>"
    return Response(html, mimetype='text/html')


@app.route("/files/bots.json", methods=["GET"])
def serve_bots_file():
    try:
        with open("bots.json", "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
