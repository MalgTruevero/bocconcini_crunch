import time, sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bocconcini
print("=== TEST 4 - SPILL ===")
# Pulizia: cancella vecchi spill, così vediamo solo quelli nuovi
for f in glob.glob("spill*.txt") + glob.glob("spill*.json") + glob.glob("*.spill"):
    try: os.remove(f)
    except: pass
print("Vecchi spill cancellati")
try:
    client = bocconcini.Bocconcini(base_url="http://127.0.0.1:8082")
except Exception:
    client = bocconcini.LlamaCppClient(base_url="http://127.0.0.1:8082")
prompt = "Scrivi una storia lunghissima di un carroarmato che attraversa 10 deserti, 10 oasi, 10 citta. Scrivi tantissimo, senza fermarti, capitolo dopo capitolo."
print(f"Prompt len: {len(prompt)}")
t0 = time.time()
testo = None
spill = None
for nome in ["chat", "completa", "genera", "ask"]:
    fn = getattr(client, nome, None)
    if callable(fn):
        try:
            r = fn(prompt, max_tokens=2048)
            if isinstance(r, str):
                testo = r
            elif hasattr(r, "testo"):
                testo = r.testo
                spill = getattr(r, "spill_files", None) or getattr(r, "spill", None)
            elif isinstance(r, dict):
                testo = r.get("testo") or r.get("text") or str(r)
                spill = r.get("spill_files") or r.get("spill")
            else:
                testo = str(r)
            print(f"Metodo usato: {nome}")
            break
        except Exception as e:
            print(f"Metodo {nome} errore: {e}")
            continue
dt = time.time() - t0
# Cerca file spill nuovi
nuovi = glob.glob("spill*.txt") + glob.glob("spill*.json") + glob.glob("*.spill") + glob.glob("bocconcini_spill*")
print("--- RISULTATO ---")
print(f"Tempo: {dt:.1f}s")
print(f"Out len: {len(testo) if testo else 0}")
print(f"Testo inizio: {(testo or '')[:200]!r}")
print(f"Spill da libreria: {spill}")
print(f"Spill file trovati: {nuovi}")
if nuovi:
    for f in nuovi:
        print(f"File spill: {f} size: {os.path.getsize(f)} byte")
    print("TEST 4: PASS - Spill vero, ha scritto su disco")
elif testo and len(testo) > 5000:
    print("TEST 4: PASS parziale - Lungo, ma senza spill su disco")
else:
    print("TEST 4: CHECK - Corto, spill non triggerato")
