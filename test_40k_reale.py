"""Test reale: naviga() trova gli aghi? Confronta standard vs arricchito."""
import sys, pathlib, tempfile, time
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bocconcini as b
import bocconcini_memory as t

# Documento ~32k caratteri con 4 aghi nascosti
filler = ("Il sistema ha registrato un picco di utilizzo della CPU. "
          "I thread di esecuzione sono stati riallocati per evitare il throttling. "
          "La memoria volatile mostra una frammentazione del 12%. ") * 200
aghi = {"ALFA-1": "Il codice di sblocco della batteria e' ALFA-1.",
        "OMEGA-9": "La password del database di telemetria e' OMEGA-9.",
        "TITANO-3": "Il nome in codice del satellite e' TITANO-3.",
        "BETA-7": "La chiave API del server di backup e' BETA-7."}
doc = filler
for i, (codice, frase) in enumerate(sorted(aghi.items())):
    k = int(len(doc) * (10 + 25*i) / 100)
    doc = doc[:k] + "\n[LOG CRITICO] " + frase + "\n" + doc[k:]

print(f"documento: {len(doc)} caratteri (~{b.estimate_tokens(doc)} token)", flush=True)

def costruisci(arricchito):
    chunks = b.split_text(doc, name="doc.txt", max_chars=1500)
    tutti = t.trova_fatti(doc) if arricchito else []
    roots = []
    for i, ch in enumerate(chunks):
        meta = t.etichetta(ch.text, name="doc.txt")
        summary = meta["summary"]
        if arricchito:
            fnel = ["%s:%s" % (f["tipo"], f["valore"]) for f in tutti
                    if ch.start <= f["pos"] < ch.end]
            if fnel:
                summary = "CHIAVE -> " + ", ".join(fnel) + " | " + summary
        roots.append(t.DocNode(id="sec_%03d" % i, label="Sez %d" % i, summary=summary,
                               text=ch.text, tokens=ch.token_count_estimate()))
    return roots

client = b.LlamaCppClient()
domanda = "Trova i 4 codici: batteria, password, satellite, backup. Elencali."

for modo in (False, True):
    with tempfile.TemporaryDirectory() as td:
        tree = t.DocTree(pathlib.Path(td))
        if modo:
            t.prepara_albero_ricco(doc, "test", tree=tree)
        else:
            tree.save("test", costruisci(False))
        t0 = time.time()
        r = t.naviga(client, tree, "test", domanda, budget_tokens=2000, max_hops=6, require_read=True)
        dt = time.time() - t0
        trovati = sum(1 for c in aghi if c in r["text"])
        print(f"\n{'STANDARD' if not modo else 'ARRICCHITO'}: "
              f"trovati {trovati}/4 in {dt:.1f}s, "
              f"hops={r['meta']['hops']}, "
              f"rami aperti={len(r['meta']['nodes_read'])}", flush=True)
        print(f"  risposta: {r['text'][:200]}", flush=True)
        m = r["meta"]
        print("  stop=%r evicted=%s deferred=%s searches=%s unknown=%s repeats=%s"
              % (m.get("stopped"), m.get("evicted"), m.get("deferred", 0),
                 m.get("searches", []), m.get("unknown_ids", []), m.get("repeats", 0)), flush=True)

