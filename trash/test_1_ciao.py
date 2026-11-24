import time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bocconcini
print("=== TEST 1 - CIAO - LIBRERIA NUOVA ===")
print(f"File: {bocconcini.__file__}")
try:
    client = bocconcini.Bocconcini(base_url="http://127.0.0.1:8082")
except Exception:
    try:
        client = bocconcini.LlamaCppClient(base_url="http://127.0.0.1:8082")
    except Exception as e:
        print(f"ERRORE creo client: {e}")
        sys.exit(1)
t0 = time.time()
try:
    testo = None
    for nome in ["chat", "completa", "genera", "ask"]:
        fn = getattr(client, nome, None)
        if callable(fn):
            try:
                r = fn("Ciao, rispondi in 1 frase sola.", max_tokens=32)
                if isinstance(r, str):
                    testo = r
                elif hasattr(r, "testo"):
                    testo = r.testo
                elif isinstance(r, dict):
                    testo = r.get("testo") or r.get("text") or str(r)
                else:
                    testo = str(r)
                print(f"Metodo usato: {nome}")
                break
            except Exception as e:
                print(f"Metodo {nome} errore: {e}")
                continue
    dt = time.time() - t0
    print("--- RISULTATO ---")
    print(f"Tempo: {dt:.1f}s")
    print(f"Lunghezza: {len(testo) if testo else 0} char")
    print(f"Testo: {testo!r}")
    if testo and len(testo.strip()) > 0:
        print("TEST 1: PASS - Vive, risponde")
    else:
        print("TEST 1: FAIL - Vuoto, non risponde")
except Exception as e:
    print(f"TEST 1: FAIL eccezione: {e}")
    import traceback; traceback.print_exc()
