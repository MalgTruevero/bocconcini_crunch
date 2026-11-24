import bocconcini.memory as t
d = ""
for j in range(200):
    d += "Contatto u%d@ex.com il 2024-%02d-%02d, codice ABC-%05d. " % (j, j % 12 + 1, j % 28 + 1, j)
c = t.split_text(d, name="d.txt", kind="text", max_chars=400, max_tokens=10000, min_chars=300, overlap=0)[0]
att = set("%s:%s" % (f["tipo"], f["valore"]) for f in t.trova_fatti(d, max_per_tipo=100) if c.start <= f["pos"] < c.end)
tr, s = t.prepara_albero_ricco(d, "loss", max_chars=400)
k = tr.keys(s)
def fo(x):
    if "CHIAVE -> " not in x: return set()
    b = x.split("CHIAVE -> ", 1)[1].split(" | ", 1)[0].split(" (+", 1)[0]
    return set(v.strip() for v in b.split(",") if v.strip())
got = fo(k["sec_000"]["summary"])
for n in k:
    if n.startswith("sec_000_facts_"): got |= fo(k[n]["summary"])
print("attesi", len(att), "raccolti", len(got))
print("persi", sorted(att - got))
