import json, pathlib, tempfile
import bocconcini as b
info = b.get_model_info()
f = ("Il sistema ha registrato un picco di utilizzo della CPU. "
     "I thread di esecuzione sono stati riallocati per evitare il throttling. "
     "La memoria volatile mostra una frammentazione del 12%. ")
doc = f * 700
doc = f * max(1, int(700 * 10 * info["n_ctx"] / b.estimate_tokens(doc)))
with tempfile.TemporaryDirectory() as td:
    tree = b.DocTree(pathlib.Path(td))
    t, nome = b.prepara_albero_ricco(doc, "test", tree=tree)
    print("nodi totali:", len(t.keys("test")))
    v = t.vista("test", budget_tokens=2000)
    print({k: v[k] for k in ("shown","omitted","level_size","next_offset")})
    for k, val in v.items():
        s = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False, default=str)
        print("  %-14s %6d caratteri  ~%5d token" % (k, len(s), b.estimate_tokens(s)))
