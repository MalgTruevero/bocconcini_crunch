import bocconcini.memory as t
d = ""
for j in range(200):
    d += "Contatto u%d@ex.com il 2024-%02d-%02d, codice ABC-%05d. " % (j, j % 12 + 1, j % 28 + 1, j)
tr, s = t.prepara_albero_ricco(d, "leaves", max_chars=400)
k = tr.keys(s)
rows = tr.index(s).get("nodes") or []
print("max_children profilo", t.matrioska_profile()["max_children"])
print("righe indice", len(rows), "nodi totali", len(k))
print("foglie fatti", len([x for x in k if "_facts_" in x]))
n = k["sec_000"]
print("sec_000 ha figli", bool(n.get("children")))
print("sec_000 testo", len(tr.load(s, "sec_000")))
