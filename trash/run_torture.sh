#!/data/data/com.termux/files/usr/bin/bash

echo "=================================================="
echo "   BOCCONCINI STRESS TEST AUTOMATICO (NO SCONTI)  "
echo "=================================================="

# 1. Trova automaticamente il file della libreria nella cartella corrente
TARGET_FILE=$(ls -1 *.py 2>/dev/null | grep -E -i "bocconcini|chunk|crunch" | head -n 1)

if [ -z "$TARGET_FILE" ]; then
    echo "[!] Nessun file chiamato *bocconcini*.py trovato qui."
    echo "    File .py presenti: $(ls -1 *.py 2>/dev/null | tr '\n' ' ')"
    echo "    Spostati nella cartella della libreria e rilancia."
    exit 1
fi

MODULE_NAME="${TARGET_FILE%.py}"
echo "[*] Libreria rilevata: $TARGET_FILE (modulo: $MODULE_NAME)"

# 2. Controlla stato RAM e Temperatura batteria/sistema prima del test
echo "[*] Stato Hardware Iniziale (S20 Ultra):"
free -h | awk '/Mem:/ {print "    RAM Totale: " $2 " | Usata: " $3 " | Libera: " $4}'
if [ -f /sys/class/power_supply/battery/temp ]; then
    TEMP=$(cat /sys/class/power_supply/battery/temp)
    echo "    Temperatura Batteria: $((TEMP / 10)).$((TEMP % 10)) °C"
fi

# 3. Genera lo script Python di tortura dinamico (si auto-adatta alle firme del modulo)
cat << 'PYEOF' > _tmp_torture_runner.py
import sys
import time
import json
import inspect
import threading
import importlib
from http.server import BaseHTTPRequestHandler, HTTPServer

mod_name = sys.argv[1]
bcc = importlib.import_module(mod_name)

print("\n[*] Ispezione API pubbliche rilevate nel modulo:")
funcs = {name: obj for name, obj in inspect.getmembers(bcc, inspect.isfunction) if not name.startswith("_")}
print("   ", list(funcs.keys()))

# Helper per invocare funzioni ignorando parametri non supportati
def smart_call(func, *args, **kwargs):
    sig = inspect.signature(func)
    valid_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return func(*args, **valid_kwargs)

# Trova la funzione di chunking e quella di chat/ask
chunk_fn = next((funcs[k] for k in funcs if "chunk" in k or "split" in k), None)
ask_fn = next((funcs[k] for k in funcs if k in ("ask", "chat", "chat_full", "invia_adattivo", "generate")), None)

print("\n--- TEST 1: JSON ASSASSINO (Parser & Escape & Profondità) ---")
if chunk_fn:
    trappola = [
        {
            "id": i,
            "trappola": "Stringa bastarda con }}}} {{{{ e \\\"virgolette finte\\\" e \n a capo",
            "dati": "A" * 400
        } for i in range(400)
    ]
    raw_json = json.dumps(trappola)
    t0 = time.time()
    try:
        res = list(smart_call(chunk_fn, raw_json, max_tokens=256, budget=256))
        dt = time.time() - t0
        tot_len = sum(len(x) if isinstance(x, str) else len(str(x)) for x in res)
        loss = 100 - (tot_len / len(raw_json) * 100)
        print(f"    Chunks: {len(res)} | Tempo: {dt:.2f}s | Perdita caratteri: {loss:.1f}%")
        if loss > 5.0:
            print("    [FAIL] Il parser ha mangiato troppi dati!")
        else:
            print("    [PASS] Parser JSON intatto.")
    except Exception as e:
        print(f"    [CRASH] {type(e).__name__}: {e}")
else:
    print("    [SKIP] Nessuna funzione di chunking trovata.")

print("\n--- TEST 2: PYTHON MONOLITE (Blocco indivisibile gigante) ---")
if chunk_fn:
    monolite = "def blocco_atomico():\n" + "".join([f"    var_{i} = 'x' * 300\n" for i in range(80)])
    try:
        res = list(smart_call(chunk_fn, monolite, max_tokens=128, budget=128))
        max_c = max(len(str(x)) for x in res)
        print(f"    Chunks: {len(res)} | Chunk più grande: {max_c} char (~{max_c//4} token stimati)")
        if max_c > 128 * 6:
            print("    [WARN] Un chunk sfora pesantemente il budget! Rischio overflow contesto.")
        else:
            print("    [PASS] Contenimento budget rispettato.")
    except Exception as e:
        print(f"    [CRASH] {type(e).__name__}: {e}")

print("\n--- TEST 3: SERVER ZOMBIE (Blocco silenzioso a metà stream) ---")
class ZombieHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"default_generation_settings": {"n_ctx": 2048}}')
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        self.wfile.write(b'data: {"choices": [{"delta": {"content": "Token iniziale... "}}]}\n\n')
        self.wfile.flush()
        time.sleep(35) # Simula freeze totale da thermal throttling / swap

if ask_fn:
    srv = HTTPServer(('127.0.0.1', 0), ZombieHandler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    t0 = time.time()
    try:
        out = smart_call(ask_fn, "Rispondi", base_url=f"http://127.0.0.1:{port}", url=f"http://127.0.0.1:{port}", timeout=4, idle_limit=4)
        dt = time.time() - t0
        print(f"    [WARN] Nessun errore dopo {dt:.1f}s. Output: {str(out)[:60]}")
    except Exception as e:
        dt = time.time() - t0
        if dt < 25:
            print(f"    [PASS] Watchdog ha ucciso il socket appeso in {dt:.1f}s ({type(e).__name__})")
        else:
            print(f"    [FAIL] Watchdog troppo lento o bloccato su readline ({dt:.1f}s)!")
    finally:
        srv.shutdown()
else:
    print("    [SKIP] Nessuna funzione di rete trovata.")

print("\n--- TEST 4: REALE SU SERVER LOCALE ATTIVO (Con Embedding in RAM) ---")
if ask_fn:
    # Cerca porte comuni locali (8080 llama.cpp, 11434 ollama, 5001 kobold)
    import socket
    active_port = None
    for p in (8080, 11434, 5001, 8000):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', p)) == 0:
                active_port = p
                break
    if active_port:
        print(f"    Server reale rilevato su porta {active_port}. Invio carico reale...")
        t0 = time.time()
        try:
            prompt_reale = "Riassumi questo concetto tecnico in 3 righe: " + ("analisi dati edge computing " * 150)
            out = smart_call(ask_fn, prompt_reale, base_url=f"http://127.0.0.1:{active_port}", url=f"http://127.0.0.1:{active_port}")
            dt = time.time() - t0
            print(f"    [PASS] Risposta reale ricevuta in {dt:.1f}s ({len(str(out))} char).")
        except Exception as e:
            dt = time.time() - t0
            print(f"    [FAIL] Errore su server reale dopo {dt:.1f}s: {type(e).__name__}: {e}")
    else:
        print("    [SKIP] Nessun server LLM attivo rilevato su porte standard (8080/11434/5001).")
PYEOF

# 4. Esegui il runner e pulisci i temporanei
python3 _tmp_torture_runner.py "$MODULE_NAME"
rm -f _tmp_torture_runner.py

# 5. Controllo finale RAM e Temperatura dopo lo stress
echo ""
echo "[*] Stato Hardware Finale post-test:"
free -h | awk '/Mem:/ {print "    RAM Totale: " $2 " | Usata: " $3 " | Libera: " $4}'
if [ -f /sys/class/power_supply/battery/temp ]; then
    TEMP=$(cat /sys/class/power_supply/battery/temp)
    echo "    Temperatura Batteria: $((TEMP / 10)).$((TEMP % 10)) °C"
fi
echo "=================================================="
