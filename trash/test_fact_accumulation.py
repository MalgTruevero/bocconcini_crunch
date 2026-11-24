"""Facts read in EARLIER turns must survive eviction. No server, no model."""
import sys, json, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bocconcini_memory as t
CODES = ("ALFA-1", "OMEGA-9", "TITANO-3", "BETA-7")
F = "Il sistema registra un picco di utilizzo della CPU. "
class R:
    def __init__(self, text="", calls=None): self.text, self.tool_calls = text, calls or []
class M:
    n = 0
    def _hw(self): return {"msg_overhead": 37.3}
    def _prompt_tokens(self, m, tt=0): return t._msg_tokens(m, 3.2, 37.3) + tt
    def chat_full(self, **kw):
        self.n += 1
        if kw.get("tools") and self.n <= 4:
            fn = {"name": "leggi_nodo", "arguments": json.dumps({"id": "b%d" % (self.n - 1)})}
            return R(calls=[{"id": "c%d" % self.n, "function": fn}])
        seen = " ".join(str(x.get("content") or "") for x in kw["messages"])
        return R(" ".join(c for c in CODES if c in seen))
with tempfile.TemporaryDirectory() as td:
    tr = t.DocTree(pathlib.Path(td))
    tr.save("s", [t.DocNode("b%d" % i, text=F * 28 + "Il codice %d e' %s." % (i, CODES[i])) for i in range(4)])
    o = t.naviga(M(), tr, "s", "Elenca i 4 codici.", budget_tokens=1600, max_hops=4)
    m = o["meta"]
    print("read=%s evicted=%s stopped=%r" % (m["nodes_read"], m["evicted"], m["stopped"]))
    print("answer:", o["text"])
    hits = [c for c in CODES if c in o["text"]]
    print("%d/4 codes survived eviction" % len(hits))
    ok = len(hits) == 4 and len(m["nodes_read"]) == 4 and m["evicted"] >= 3
    sys.exit(0 if ok else 1)
