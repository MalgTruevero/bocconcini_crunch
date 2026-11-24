"""Riproduce la promessa del README: 4 codici nascosti in ~32k caratteri.

  python benchmark_tank.py --no-model   # solo scansione, nessun server, costo 0
  python benchmark_tank.py              # completo: scansione + UNA chiamata

Esce con 1 se la scansione perde un ago o se il modello risponde sbagliato.
"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bocconcini as b
from bocconcini import trova_fatti

NEEDLES = ("ALFA-1", "OMEGA-9", "TITANO-3", "BETA-7")
FILLER = ("Il sistema ha registrato un picco di utilizzo della CPU. I thread di "
          "esecuzione sono stati riallocati per evitare il throttling. La memoria "
          "volatile mostra una frammentazione del 12%. ")
SENT = {10: "Il codice di sblocco della batteria e' ALFA-1.",
        35: "La password del database di telemetria e' OMEGA-9.",
        60: "Il nome in codice del satellite e' TITANO-3.",
        85: "La chiave API del server di backup e' BETA-7."}

doc = FILLER * 170
for pct, s in sorted(SENT.items()):
    k = int(len(doc) * pct / 100)
    doc = doc[:k] + "\n[LOG CRITICO] " + s + "\n" + doc[k:]

t0 = time.time()
facts = trova_fatti(doc)
scan = time.time() - t0
found = [n for n in NEEDLES if any(f["valore"] == n for f in facts)]
print("documento: %d caratteri (~%d token)" % (len(doc), b.estimate_tokens(doc, "text")))
print("scansione: %d candidati in %.3fs -> %d/4 aghi" % (len(facts), scan, len(found)))
if len(found) != 4:
    print("FAIL: persi", set(NEEDLES) - set(found)); sys.exit(1)
if "--no-model" in sys.argv:
    print("PASS (solo scansione, nessun server)"); sys.exit(0)

ctx = "\n".join("%d) %s" % (i + 1, f["contesto"]) for i, f in enumerate(facts))
prompt = ("FATTI CANDIDATI:\n" + ctx + "\n\nRispondi con ESATTAMENTE 4 righe "
          "nel formato 'N. CODICE', senza spiegazioni:\n"
          "1. codice di sblocco della batteria\n2. password del database di telemetria\n"
          "3. nome in codice del satellite\n4. chiave API del server di backup")
print("prompt: ~%d token" % b.estimate_tokens(prompt, "text"))
cl = b.LlamaCppClient()
t1 = time.time()
r = cl.chat_full(prompt=prompt, max_tokens=400, temperature=0.0,
                 auto_reduce=False, continua=False)
print("modello: %.1fs\n%s" % (time.time() - t1, r.text))
hit = [n for n in NEEDLES if n in r.text]
print("accuratezza: %d/4" % len(hit))
sys.exit(0 if len(hit) == 4 else 1)
