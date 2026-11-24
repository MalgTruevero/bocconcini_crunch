import bocconcini.memory as t
old = "\n".join("def f%d(x): return x*%d  # filler" % (i, i) for i in range(40))
old += "\ncodice controllo BFR-7491 = __buffer__"
base = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"},
        {"role": "tool", "content": old, "_node": "sec_001"}, {"role": "assistant", "content": "ok"}]
q = "dove e il codice controllo BFR-7491"
cost = lambda ms: sum(len(str(x.get("content") or "")) for x in ms) / 3.0
for b in (80, 150, 300, 2000):
    m = [dict(x) for x in base]
    n = t._evict(m, b, 3.0, 8.0, q, cost=cost)
    c = m[2]["content"]
    print(b, "removed", n, "len", len(c), "needle", "BFR-7491" in c,
          "righe_intere", c.count("def f") == c.count("# filler"))
