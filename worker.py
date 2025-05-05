from app import load_active_bots, running_bots
import time

print("🟢 Worker iniciando...")

# Cargar y ejecutar bots guardados
load_active_bots()

# Mantener el proceso vivo
while True:
    activos = list(running_bots.keys())
    print(f"[WORKER] Bots activos: {activos}")
    time.sleep(30)
