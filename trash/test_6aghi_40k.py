"""6 needles in 10x the model context. Proof with measured provenance."""
import json, pathlib, platform, sys, tempfile, time, urllib.request
import bocconcini as b

URL = "http://127.0.0.1:8082"
def get(p):
    try:
        return json.load(urllib.request.urlopen(URL + p, timeout=10))
    except Exception as e:
        return {"error": str(e)}

client = b.LlamaCppClient(URL)
info = b.get_model_info(URL)
ver, mods = get("/api/extra/version"), get("/v1/models")
prov = {"server": ver, "models": mods, "device": platform.platform(),
        "machine": platform.machine(), "python": platform.python_version(),
        "n_ctx": info["n_ctx"], "cognitive_limit": client.cognitive_limit, "model_info": info}
print("PROVENIENZA:", json.dumps(prov, ensure_ascii=False)[:1400], flush=True)

filler = ("Il sistema ha registrato un picco di utilizzo della CPU. "
          "I thread di esecuzione sono stati riallocati per evitare il throttling. "
          "La memoria volatile mostra una frammentazione del 12%. ")
target = 10 * info["n_ctx"]
doc = filler * 700
doc = filler * max(1, int(700 * target / b.estimate_tokens(doc)))
tok = b.estimate_tokens(doc)
aghi = {"ALFA-1": "Il codice di sblocco della batteria e' ALFA-1.",
        "OMEGA-9": "La password del database di telemetria e' OMEGA-9.",
        "TITANO-3": "Il nome in codice del satellite e' TITANO-3.",
        "BETA-7": "La chiave API del server di backup e' BETA-7.",
        "KAPPA-5": "Il codice della cassaforte di servizio e' KAPPA-5.",
        "SIGMA-2": "La firma del firmware di riserva e' SIGMA-2."}
for i, (c, f) in enumerate(sorted(aghi.items())):
    k = int(len(doc) * (8 + 15 * i) / 100)
    doc = doc[:k] + "\n[LOG CRITICO] " + f + "\n" + doc[k:]
tok = b.estimate_tokens(doc)
ratio = round(tok / info["n_ctx"], 2)
print("documento: %d caratteri, ~%d token, %sx n_ctx(%d)"
      % (len(doc), tok, ratio, info["n_ctx"]), flush=True)
q = ("Trova i 6 codici: batteria, password database, satellite, "
     "backup, cassaforte, firmware. Elencali.")
with tempfile.TemporaryDirectory() as td:
    tree = b.DocTree(pathlib.Path(td))
    b.prepara_albero_ricco(doc, "test", tree=tree)
    t0 = time.time()
    r = b.naviga(client, tree, "test", q, budget_tokens=2000,
                 max_hops=10, require_read=True)
    dt = time.time() - t0
trovati = [c for c in aghi if c in r["text"]]
print("trovati %d/6 in %.1fs, hops=%s" % (len(trovati), dt, r["meta"]["hops"]), flush=True)
print("risposta:", r["text"][:400], flush=True)
rep = dict(prov, doc_chars=len(doc), doc_tokens_est=tok, ratio_vs_n_ctx=ratio,
           needles=sorted(aghi), found=sorted(trovati), n_found=len(trovati),
           seconds=round(dt, 1), meta=r["meta"], answer=r["text"])
pathlib.Path("prova_6aghi_40k.json").write_text(
    json.dumps(rep, indent=2, ensure_ascii=False, default=str))
print("report: prova_6aghi_40k.json", flush=True)
sys.exit(0 if len(trovati) == 6 else 1)
