import time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bocconcini
print("=== TEST 3 - MARATONETA ===")
try:
    client = bocconcini.Bocconcini(base_url="http://127.0.0.1:8082")
except Exception:
    client = bocconcini.LlamaCppClient(base_url="http://127.0.0.1:8082")
prompt = "Scrivi una storia lunga di un carroarmato che attraversa un deserto, deve arrivare a un'oasi. Scrivi tanto, senza fermarti."
print(f"Prompt len: {len(prompt)}")
t0 = time.time()
testo = None
for nome in ["chat", "completa", "genera", "ask"]:
    fn = getattr(client, nome, None)
    if callable(fn):
        try:
            r = fn(prompt, max_tokens=1024)
            testo = r if isinstance(r, str) else getattr(r, "testo", str(r))
            print(f"Metodo usato: {nome}")
            break
        except Exception as e:
            print(f"Metodo {nome} errore: {e}")
            continue
dt = time.time() - t0
print("--- RISULTATO ---")
print(f"Tempo: {dt:.1f}s")
print(f"Out len: {len(testo) if testo else 0}")
print(f"Testo inizio: {(testo or '')[:200]!r}")
print(f"Testo fine: {(testo or '')[-200:]!r}")
print("TEST 3: PASS" if testo and len(testo.strip())>0 else "TEST 3: FAIL")
