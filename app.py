from flask import Flask, request, jsonify, Response
import threading
import time
import os
import json
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
import ccxt

app = Flask(__name__)
running_bots = {}
active_bots_file = "active_bots.json"


def ajustar_qty(qty, step_size):
    step = Decimal(str(step_size))
    return float((Decimal(str(qty)).quantize(step, rounding=ROUND_DOWN)))


def bot_worker(bot_id, config):
    try:
        exchange_id = config["exchange"]
        api_key = config["apiKey"]
        api_secret = config["apiSecret"]
        symbol = config["symbol"]
        monto = float(config["monto"])
        tp_pct = float(config["tp_pct"])
        sep_pct = float(config["sep_pct"])
        os_num = int(config["os_num"])
        dca_pct = float(config.get("dca_pct", "0.5%").replace("%", "")) / 100
        sl = config.get("sl", "")
        tp_plus = config.get("tp_plus", "")
        reiniciar = config.get("reiniciar", True)
        reiniciar_os = config.get("reiniciar_os", True)

        config["vnc_total"] = float(config.get("vnc_total", 0))
        config["vnc_total_cost"] = float(config.get("vnc_total_cost", 0))
        config["contador_ciclos"] = int(config.get("contador_ciclos", 0))

        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True
        })
        exchange.load_markets()
        market = exchange.markets[symbol]

        # Compra inicial
        price = exchange.fetch_ticker(symbol)["last"]
        qty = ajustar_qty(monto / price, market["precision"]["amount"])
        order = exchange.create_order(
            symbol=symbol, type="market", side="buy", amount=qty)
        print(f"[{bot_id}] Compra inicial: {qty} @ {price}")

        tp_price = price * (1 + tp_pct / 100)
        tp_price = float(Decimal(tp_price).quantize(
            Decimal(str(1 / (10 ** market["precision"]["price"]))), rounding=ROUND_DOWN))
        exchange.create_order(symbol=symbol, type="limit",
                              side="sell", amount=qty, price=tp_price)
        print(f"[{bot_id}] TP colocado: {tp_price}")

        # Colocar órdenes DCA
        for i in range(1, os_num + 1):
            os_price = price * (1 - (sep_pct / 100) * i)
            os_price = float(Decimal(os_price).quantize(
                Decimal(str(1 / (10 ** market["precision"]["price"]))), rounding=ROUND_DOWN))
            qty_os = ajustar_qty(
                monto / os_price, market["precision"]["amount"])
            exchange.create_order(
                symbol=symbol, type="limit", side="buy", amount=qty_os, price=os_price)

        entry_time = int(time.time() * 1000)

        while config["running"]:
            try:
                price = exchange.fetch_ticker(symbol)["last"]
                print(f"[{bot_id}] Monitoreando precio: {price}")

                # TP+
                if tp_plus:
                    tp_plus_price = float(tp_plus)
                    if price >= tp_plus_price:
                        print(
                            f"[{bot_id}] TP+ alcanzado: {price} >= {tp_plus_price}")
                        sell_all(exchange, symbol, market, price, config)
                        if reiniciar:
                            config["contador_ciclos"] += 1
                            return start_bot_worker(bot_id, config)
                        else:
                            config["running"] = False
                            return

                # SL
                if sl:
                    sl_price = float(sl)
                    if price <= sl_price:
                        print(f"[{bot_id}] SL alcanzado: {price} <= {sl_price}")
                        sell_all(exchange, symbol, market, price, config)
                        config["running"] = False
                        return

                # Autosell DCA
                if config["vnc_total"] > 0:
                    dca = config["vnc_total_cost"] / config["vnc_total"]
                    if price >= dca * (1 + dca_pct):
                        print(
                            f"[{bot_id}] Autosell alcanzado: {price} >= {dca * (1 + dca_pct)}")
                        sell_all(exchange, symbol, market, price, config)
                        config["vnc_total"] = 0
                        config["vnc_total_cost"] = 0

                # Monitoreo de órdenes abiertas
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
                print(f"[{bot_id} ERROR loop] {e}")
                time.sleep(5)

    except Exception as e:
        print(f"[{bot_id} ERROR fatal] {e}")


def cancel_all(exchange, symbol, orders):
    for order in orders:
        try:
            exchange.cancel_order(order["id"], symbol)
        except:
            pass


def sell_all(exchange, symbol, market, price, config):
    symbol_base = symbol.split("/")[0]
    balance = exchange.fetch_balance()
    qty = balance.get(symbol_base, {}).get("free", 0)
    qty = ajustar_qty(qty, market["precision"]["amount"])
    if qty > 0:
        exchange.create_order(symbol=symbol, type="market",
                              side="sell", amount=qty)
        print(f"[{symbol}] Vendido todo ({qty}) a mercado @ {price}")

        # Actualizar VNC y ciclo si aplica
        config["vnc_total"] = 0
        config["vnc_total_cost"] = 0


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

# ================= FLASK ===================


@app.before_request
def log_request():
    print(f"[{request.method}] {request.url} | Body: {request.get_data()}")


@app.route("/")
def index():
    return Response("<h1>Bot server is online</h1><p>Use /api/start_bot para iniciar</p>", mimetype="text/html")


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


@app.route("/api/bots", methods=["GET"])
def list_bots():
    return jsonify({"bots": list(running_bots.keys())})


@app.route("/api/config", methods=["POST"])
def receive_config():
    data = request.json
    print("📥 Configuración recibida:", data)
    return jsonify({"status": "Configuración guardada"})


@app.route("/api/report_bots", methods=["POST"])
def report_bots():
    data = request.json
    print("📥 Bots reportados desde interfaz:")
    for b in data:
        print(f" - {b['symbol']} en {b['exchange']}")
    return jsonify({"status": "Reportado correctamente"})

# ===========================================


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("🟢 Iniciando servidor Flask...")
    load_active_bots()
    app.run(host="0.0.0.0", port=port)
