#!/usr/bin/env python3
# TEST DI SOPRAVVIVENZA - BOCCONCINI SU S20 ULTRA
# Se passa questo, e' un carroarmato. Se si rompe, si rompe qui, non dentro MALG.
# Metti questo file accanto a bocconcini.py
# Prima avvia llama-server su porta 8082, poi lancia: python test_sopravvivenza.py
# NON toccare il telefono durante il test. Lascia che soffra.

import time, os, sys, json, traceback, gc, resource
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import bocconcini
    print(f"BOCCONCINI: {getattr(bocconcini, '__version__', '?')} file={bocconcini.__file__}")
except Exception as e:
    print(f"ERRORE import bocconcini: {e}")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8082"
LOG_FILE = "sopravvivenza_report.jsonl"
REPORT = []

def log(risultato):
    REPORT.append(risultato)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(risultato, ensure_ascii=False) + "\n")
    print(f"[{risultato['test']}] {risultato['stato']} - {risultato.get('dettaglio','')}")

def memoria_mb():
    try:
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:
        return -1

def crea_client():
    for nome in ["Bocconcini", "Client", "Bocconcino", "LLM"]:
        cls = getattr(bocconcini, nome, None)
        if cls:
            try:
                return cls(base_url=BASE_URL)
            except TypeError:
                try:
                    return cls(BASE_URL)
                except Exception:
                    pass
            except Exception:
                pass
    return bocconcini

def chiama(client, prompt, max_tokens=512, **kw):
    for metodo in ["chat", "completa", "genera", "ask", "complete", "generate", "chiedi"]:
        fn = getattr(client, metodo, None)
        if callable(fn):
            try:
                r = fn(prompt, max_tokens=max_tokens, **kw)
                if isinstance(r, str):
                    return r, {}
                if hasattr(r, "testo"):
                    return r.testo, {"ha_json": getattr(r, "ha_json_nel_testo", None), "json": getattr(r, "json_nel_testo", None)}
                if hasattr(r, "text"):
                    return r.text, {}
                if isinstance(r, dict):
                    return r.get("testo") or r.get("text") or str(r), r
                return str(r), {}
            except TypeError:
                try:
                    r = fn(prompt)
                    return str(r), {}
                except Exception as e:
                    return "", {"errore": str(e)}
            except Exception as e:
                return "", {"errore": str(e)}
    for metodo in ["chat", "completa"]:
        fn = getattr(bocconcini, metodo, None)
        if callable(fn):
            return str(fn(prompt)), {}
    raise RuntimeError("Non trovo chat/completa/genera in bocconcini - adatta crea_client()/chiama()")

def test_1_ciao():
    t0=time.time()
    try:
        testo, meta = chiama(crea_client(), "Ciao", max_tokens=32)
        ok = len(testo.strip())>0
        log({"test":"1_CIAO","stato":"PASS" if ok else "FAIL","dettaglio":f"len={len(testo)} tempo={time.time()-t0:.1f}s testo={testo[:80]!r} mem={memoria_mb()}MB"})
    except Exception as e:
        log({"test":"1_CIAO","stato":"FAIL","dettaglio":f"eccezione: {e} {traceback.format_exc()[:500]}"})

def test_2_bomba_prompt():
    prompt = ("Ripeti e continua questa storia senza fermarti. " * 200) + "\n\nLa storia parla di un carroarmato che deve attraversare un deserto. Continua per molto tempo."
    t0=time.time()
    try:
        testo, meta = chiama(crea_client(), prompt, max_tokens=512)
        log({"test":"2_BOMBA_PROMPT_8K","stato":"PASS" if len(testo)>0 else "FAIL","dettaglio":f"prompt_len={len(prompt)} out_len={len(testo)} tempo={time.time()-t0:.1f}s mem={memoria_mb()}MB"})
    except Exception as e:
        log({"test":"2_BOMBA_PROMPT_8K","stato":"FAIL","dettaglio":str(e)[:400]})

def test_3_maratoneta():
    prompt = "Scrivi un racconto lunghissimo, dettagliato, di almeno 2000 parole, su un S20 Ultra che diventa un carroarmato e attraversa il deserto senza fermarsi mai. Non fermarti a meta, vai fino in fondo."
    t0=time.time()
    try:
        testo, meta = chiama(crea_client(), prompt, max_tokens=2048)
        dt=time.time()-t0
        tps = len(testo)/max(dt,1)
        log({"test":"3_MARATONETA_2048tok","stato":"PASS" if len(testo)>500 else "FAIL","dettaglio":f"out_len={len(testo)} tempo={dt:.1f}s char/s={tps:.1f} mem={memoria_mb()}MB"})
    except Exception as e:
        log({"test":"3_MARATONETA_2048tok","stato":"FAIL","dettaglio":str(e)[:400]})

def test_4_spill():
    prompt = "Elenca 5000 nomi di citta del mondo, una per riga, con una descrizione di 2 frasi per ognuna. Non fermarti. Continua fino alla fine."
    t0=time.time()
    try:
        testo, meta = chiama(crea_client(), prompt, max_tokens=4096)
        dt=time.time()-t0
        spill_files = [f for f in os.listdir(".") if "spill" in f.lower() or f.endswith(".tmp")]
        log({"test":"4_SPILL_GIGANTE","stato":"PASS" if len(testo)>0 else "FAIL","dettaglio":f"out_len={len(testo)} tempo={dt:.1f}s mem={memoria_mb()}MB spill_files={spill_files[:3]}"})
    except Exception as e:
        log({"test":"4_SPILL_GIGANTE","stato":"FAIL","dettaglio":str(e)[:400]})

def test_5_raffica():
    domande = [f"Domanda {i}: dimmi in 2 frasi chi era Leonardo da Vinci, ma con un dettaglio diverso ogni volta." for i in range(1,11)]
    t0=time.time()
    ok=0
    for i,q in enumerate(domande,1):
        try:
            testo,_ = chiama(crea_client(), q, max_tokens=128)
            if len(testo)>0: ok+=1
            print(f"  raffica {i}/10 len={len(testo)} mem={memoria_mb()}MB")
            gc.collect()
        except Exception as e:
            print(f"  raffica {i} ERRORE: {e}")
    log({"test":"5_RAFFICA_10X","stato":"PASS" if ok>=8 else "FAIL","dettaglio":f"riuscite={ok}/10 tempo_tot={time.time()-t0:.1f}s mem={memoria_mb()}MB"})

def test_6_json_sporco():
    prompt = 'Rispondi SOLO con questo JSON, senza altro testo: {"parla": "Ciao, sono MALG"}'
    try:
        testo, meta = chiama(crea_client(), prompt, max_tokens=128)
        ha_json = "parla" in testo and "Ciao" in testo
        log({"test":"6_JSON_SPORCO","stato":"PASS" if ha_json else "CHECK","dettaglio":f"testo={testo[:200]!r} meta={str(meta)[:200]}"})
    except Exception as e:
        log({"test":"6_JSON_SPORCO","stato":"FAIL","dettaglio":str(e)[:400]})

def test_7_contesto_esploso():
    prompt = "Parla di Roma. " * 800
    try:
        testo,_ = chiama(crea_client(), prompt, max_tokens=256)
        log({"test":"7_CONTESTO_OLTRE_4096","stato":"PASS" if len(testo)>0 else "FAIL","dettaglio":f"prompt_len={len(prompt)} out_len={len(testo)} mem={memoria_mb()}MB"})
    except Exception as e:
        log({"test":"7_CONTESTO_OLTRE_4096","stato":"FAIL","dettaglio":str(e)[:400]})

def test_8_doppio_lavoro():
    import threading
    risultati = {}
    def lavoro(nome, prompt):
        try:
            t,_ = chiama(crea_client(), prompt, max_tokens=256)
            risultati[nome]=len(t)
        except Exception as e:
            risultati[nome]=f"ERR: {e}"[:200]
    th1=threading.Thread(target=lavoro, args=("A","Scrivi un racconto su un gatto astronauta, lungo e dettagliato."))
    th2=threading.Thread(target=lavoro, args=("B","Scrivi un racconto su un cane pirata, lungo e dettagliato."))
    th1.start(); time.sleep(0.2); th2.start()
    th1.join(timeout=180); th2.join(timeout=180)
    log({"test":"8_BUSY_GATE_DOPPIO","stato":"CHECK","dettaglio":f"risultati={risultati} - Se A e B sono entrambi >0 e non mischiati, Busy Gate ha funzionato. Se uno e 0 o mischiato, da guardare."})

if __name__=="__main__":
    print("="*60)
    print("TEST DI SOPRAVVIVENZA BOCCONCINI - S20 ULTRA")
    print("Se Termux viene killato, riapri e guarda sopravvivenza_report.jsonl")
    print("="*60)
    if os.path.exists(LOG_FILE):
        os.rename(LOG_FILE, LOG_FILE+".vecchio")
    test_1_ciao()
    test_2_bomba_prompt()
    test_3_maratoneta()
    test_4_spill()
    test_5_raffica()
    test_6_json_sporco()
    test_7_contesto_esploso()
    test_8_doppio_lavoro()
    print("\n="*60)
    print("FINE. Report in:", LOG_FILE)
    print("Mandami il contenuto di quel file, ti dico se e un carroarmato o no.")
    print("="*60)
