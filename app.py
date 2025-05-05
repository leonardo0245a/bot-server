from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

@app.route("/api/config", methods=["POST"])
def save_config():
    data = request.json
    with open("config.json", "w") as f:
        json.dump(data, f, indent=4)
    return jsonify({"status": "config saved"})

@app.route("/api/bots", methods=["POST"])
def save_bots():
    data = request.json
    with open("bots.json", "w") as f:
        json.dump(data, f, indent=4)
    return jsonify({"status": "bots saved"})

@app.route("/api/ping")
def ping():
    return jsonify({"status": "online"})