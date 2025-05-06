from flask import Flask, request, jsonify, Response
import threading
import time
import os
import json
import ccxt
from decimal import Decimal, ROUND_DOWN

app = Flask(__name__)
running_bots = {}
active_bots_file = "active_bots.json"


def ajustar_qty(qty, step_size):
    step = Decimal(str(step_size))
    return float((Decimal(str(qty)).quantize(step, rounding=ROUND_DOWN)))


def start_bot_worker(bot_id, config):
    config["running"] = True
    thread = threading.Thread(
        target=bot_worker, args=(bot_id, config), daemon=True)
    running_bots[bot_id] = {"thread": thread, "config": config}
    thread.start()
    save_active_bots()


def stop_bot_worker(bot_id):
    bot = running_bots.get(bot_id)
    if bot:
        bot["config"]["running"] = False
        running_bots.pop(bot_id)
        save_active_bots()


def save_active_bots():
    try:
        bots_data = []
        for bot_id, data in running_bots.items():
            bots_data.append({"id": bot_id, **data["config"]})
        with open(active_bots_file, "w") as f:
            json.dump(bots_data, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Guardando bots activos: {e}")


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


def sell_all(exchange, symbol, market, config):
    try:
        symbol_base = symbol.split("/")[0]
        balance = exchange.fetch_balance()
        qty = balance.get(symbol_base, {}).get("free", 0)
        qty = ajustar_qty(qty, market["precision"]["amount"])
        if qty > 0:
            exchange.create_order(
                symbol=symbol, type="market", side="sell", amount=qty)
            print(f"[{symbol}] Vendido {qty} a mercado")
            config["vnc_total"] = 0
            config["vnc_total_cost"] = 0
    except Exception as e:
        print(f"[ERROR] vendiendo todo: {e}")


def cancel_all(exchange, symbol, orders):
    for order in orders:
        try:
            exchange.cancel_order(order["id"], symbol)
        except:
            pass


def bot_worker(bot_id, config):
    try:
        exchange_class = getattr(ccxt, config["exchange"])
        exchange = exchange_class({
            'apiKey': config["apiKey"],
            'secret': config["apiSecret"],
            'enableRateLimit': True
        })
        exchange.load_markets()
        symbol = config["symbol"]
        market = exchange.markets[symbol]

        monto = float(config["monto"])
        tp_pct = float(config["tp_pct"])
        sep_pct = float(config["sep_pct"])
        os_num = int(config["os_num"])

        vnc_total = float(config.get("vnc_total", 0))
        vnc_total_cost = float(config.get("vnc_total_cost", 0))
        contador_ciclos = int(config.get("contador_ciclos", 0))

        last_price = exchange.fetch_ticker(symbol)["last"]
        qty = ajustar_qty(monto / last_price, market["precision"]["amount"])
        exchange.create_order(symbol=symbol, type="market",
                              side="buy", amount=qty)
        print(f"[{bot_id}] Compra inicial: {qty} @ {last_price}")

        tp_price = last_price * (1 + tp_pct / 100)
        tp_price = float(Decimal(tp_price).quantize(
            Decimal(str(1 / (10 ** market["precision"]["price"]))), rounding=ROUND_DOWN))
        exchange.create_order(symbol=symbol, type="limit",
                              side="sell", amount=qty, price=tp_price)

        for i in range(1, os_num + 1):
            os_price = last_price * (1 - (sep_pct / 100) * i)
            os_price = float(Decimal(os_price).quantize(
                Decimal(str(1 / (10 ** market["precision"]["price"]))), rounding=ROUND_DOWN))
            qty_os = ajustar_qty(
                monto / os_price, market["precision"]["amount"])
            exchange.create_order(
                symbol=symbol, type="limit", side="buy", amount=qty_os, price=os_price)

        while config["running"]:
            try:
                price = exchange.fetch_ticker(symbol)["last"]
                sl = float(config.get("sl") or 0)
                tp_plus = float(config.get("tp_plus") or 0)
                dca_pct = float(
                    str(config.get("dca_pct", "0.5%")).replace("%", "")) / 100
                reiniciar = config.get("reiniciar", False)
                reiniciar_os = config.get("reiniciar_os", False)

                # TP+
                if tp_plus and price >= tp_plus:
                    print(f"[{bot_id}] TP+ alcanzado @ {price}")
                    sell_all(exchange, symbol, market, config)
                    if reiniciar:
                        config["contador_ciclos"] = contador_ciclos + 1
                        return start_bot_worker(bot_id, config)
                    else:
                        config["running"] = False
                        return

                # SL
                if sl and price <= sl:
                    print(f"[{bot_id}] SL alcanzado @ {price}")
                    sell_all(exchange, symbol, market, config)
                    config["running"] = False
                    return

                # Autosell DCA
                if config.get("vnc_total", 0) > 0:
                    dca = config["vnc_total_cost"] / config["vnc_total"]
                    if price >= dca * (1 + dca_pct):
                        print(f"[{bot_id}] Autosell alcanzado @ {price}")
                        sell_all(exchange, symbol, market, config)

                # Monitoreo de órdenes
                open_orders = exchange.fetch_open_orders(symbol)
                buy_orders = [o for o in open_orders if o["side"] == "buy"]
                sell_orders = [o for o in open_orders if o["side"] == "sell"]

                if reiniciar and not sell_orders:
                    cancel_all(exchange, symbol, buy_orders)
                    config["contador_ciclos"] += 1
                    return start_bot_worker(bot_id, config)

                if reiniciar_os and not buy_orders:
                    cancel_all(exchange, symbol, sell_orders)
                    config["contador_ciclos"] += 1
                    return start_bot_worker(bot_id, config)

                time.sleep(5)
            except Exception as e:
                print(f"[{bot_id} ERROR] {e}")
                time.sleep(5)

    except Exception as e:
        print(f"[{bot_id} FATAL ERROR] {e}")

# ========= RUTAS FLASK =========


@app.before_request
def log_request():
    print(f"[{request.method}] {request.url} | Body: {request.get_data()}")


@app.route("/")
def index():
    return Response("<h1>Bot server online</h1>", mimetype="text/html")


@app.route("/api/start_bot", methods=["POST"])
def start_bot():
    data = request.json
    bot_id = data.get("id")
    if not bot_id or "apiKey" not in data or "apiSecret" not in data:
        return jsonify({"error": "Faltan datos obligatorios"}), 400
    if bot_id in running_bots:
        return jsonify({"error": f"Bot '{bot_id}' ya está en ejecución"}), 400
    start_bot_worker(bot_id, data)
    return jsonify({"status": f"Bot '{bot_id}' iniciado"})


@app.route("/api/stop_bot", methods=["POST"])
def stop_bot():
    data = request.json
    bot_id = data.get("id")
    if bot_id not in running_bots:
        return jsonify({"error": f"Bot '{bot_id}' no está en ejecución"}), 404
    stop_bot_worker(bot_id)
    return jsonify({"status": f"Bot '{bot_id}' detenido"})


@app.route("/api/update_bot", methods=["POST"])
def update_bot():
    data = request.json
    bot_id = data.get("id")
    if bot_id not in running_bots:
        return jsonify({"error": f"Bot '{bot_id}' no está en ejecución"}), 404

    bot_config = running_bots[bot_id]["config"]
    actualizables = [
        "tp_pct", "tp_plus", "sl", "dca_pct",
        "reiniciar", "reiniciar_os", "monto", "sep_pct", "os_num"
    ]
    for key in actualizables:
        if key in data:
            bot_config[key] = data[key]

    save_active_bots()
    print(f"[UPDATE] {bot_id} actualizado: {data}")
    return jsonify({"status": f"Bot '{bot_id}' actualizado correctamente"})


@app.route("/api/bots", methods=["GET"])
def list_bots():
    return jsonify({"bots": list(running_bots.keys())})


@app.route("/api/config", methods=["POST"])
def receive_config():
    print("📥 Configuración recibida")
    return jsonify({"status": "ok"})


@app.route("/api/report_bots", methods=["POST"])
def report_bots():
    print("📥 Bots reportados desde la interfaz")
    return jsonify({"status": "ok"})

# ========= INICIAR SERVIDOR =========


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("🟢 Iniciando servidor Flask...")
    load_active_bots()
    app.run(host="0.0.0.0", port=port)
