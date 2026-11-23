"""Verifica offline: l'arricchimento dei summary rende i fatti visibili nell'indice.
Nessun modello, nessun server. Deterministico."""
import sys, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bocconcini as b
import bocconcini_memory as t

n = fail = 0
def ok(label, cond):
    global n, fail
    n += 1
    if not cond:
        fail += 1
    print("%s %s" % ("OK  " if cond else "FAIL", label))

filler = "Il sistema ha registrato un picco di utilizzo della CPU. " * 400
aghi = {"ALFA-1": "Il codice di sblocco della batteria e' ALFA-1.",
        "OMEGA-9": "La password del database di telemetria e' OMEGA-9.",
        "TITANO-3": "Il nome in codice del satellite e' TITANO-3.",
        "BETA-7": "La chiave API del server di backup e' BETA-7."}
doc = filler
for i, (codice, frase) in enumerate(aghi.items()):
    k = int(len(doc) * (10 + 25*i) / 100)
    doc = doc[:k] + "\n[LOG] " + frase + "\n" + doc[k:]

fatti = t.trova_fatti(doc)
ok("trova_fatti vede i 4 aghi", set(aghi) <= {f["valore"] for f in fatti})

chunks = b.split_text(doc, name="doc.txt", max_chars=1500)

def costruisci(arricchito):
    roots = []
    tutti = t.trova_fatti(doc) if arricchito else []
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

with tempfile.TemporaryDirectory() as td:
    tree = t.DocTree(pathlib.Path(td))
    tree.save("std", costruisci(False))
    t.prepara_albero_ricco(doc, "ricco", tree=tree)
    def indice_di(s):
        return " ".join((v.get("summary","") + " " + v.get("label",""))
                        for v in tree.keys(s).values())
    vis_std = sum(1 for c in aghi if c in indice_di("std"))
    vis_ricco = sum(1 for c in aghi if c in indice_di("ricco"))
    print("fatti visibili nell'indice: standard=%d/4  arricchito=%d/4" % (vis_std, vis_ricco))
    ok("senza arricchimento gli aghi NON sono nell'indice", vis_std == 0)
    ok("con arricchimento i 4 aghi sono nell'indice", vis_ricco == 4)

print("\n%d verifiche, %d fallite" % (n, fail))
sys.exit(1 if fail else 0)
