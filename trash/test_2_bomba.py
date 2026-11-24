import time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bocconcini
print("=== TEST 2 - BOMBA PROMPT 8K - LIBRERIA NUOVA ===")
try:
    client = bocconcini.Bocconcini(base_url="http://127.0.0.1:8082")
except Exception:
    client = bocconcini.LlamaCppClient(base_url="http://127.0.0.1:8082")
prompt = ("Ripeti e continua questa storia senza fermarti. " * 200) + "\n\nLa storia parla di un carroarmato che deve attraversare un deserto. Continua per molto tempo."
print(f"Prompt len: {len(prompt)} char")
t0 = time.time()
testo = None
for nome in ["chat", "completa", "genera", "ask"]:
    fn = getattr(client, nome, None)
    if callable(fn):
        try:
            r = fn(prompt, max_tokens=512)
            testo = r if isinstance(r, str) else getattr(r, "testo", str(r))
            print(f"Metodo usato: {nome}")
            break
        except Exception as e:
            print(f"Metodo {nome} errore: {e}")
            continue
dt = time.time() - t0
print("--- RISULTATO ---")
print(f"Tempo: {dt:.1f}s")
print(f"Out len: {len(testo) if testo else 0} char")
print(f"Testo inizio: {(testo or '')[:200]!r}")
if testo and len(testo.strip()) > 0:
    print("TEST 2: PASS - Vive con bomba 8K")
else:
    print("TEST 2: FAIL - Vuoto con bomba 8K")
