import inspect
import bocconcini.memory as t
print(inspect.signature(t.trova_fatti))
d = ""
for j in range(200):
    d += "Contatto u%d@ex.com il 2024-%02d-%02d, codice ABC-%05d. " % (j, j % 12 + 1, j % 28 + 1, j)
for cap in (100, 1000):
    f = t.trova_fatti(d, max_per_tipo=cap)
    tipi = {}
    for x in f:
        tipi[x["tipo"]] = tipi.get(x["tipo"], 0) + 1
    print(cap, len(f), tipi)
