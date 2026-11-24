"""Narrative facts must survive eviction too. No server, no model."""
import sys, json, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bocconcini_memory as t
TARGETS = ("Aldo Bini", "450 euro")
F = "Il documento descrive condizioni generali della procedura. "
class R:
    def __init__(self, text="", calls=None): self.text, self.tool_calls = text, calls or []
class M:
    n = 0
    def _hw(self): return {"msg_overhead": 12.0}
    def _prompt_tokens(self, m, tt=0): return t._msg_tokens(m, 3.2, 12.0) + tt
    def chat_full(self, **kw):
        self.n += 1
        if kw.get("tools") and self.n <= 2:
            fn = {"name": "leggi_nodo", "arguments": json.dumps({"id": "b%d" % (self.n - 1)})}
            return R(calls=[{"id": "c%d" % self.n, "function": fn}])
        seen = " ".join(str(x.get("content") or "") for x in kw["messages"])
        return R(" ".join(c for c in TARGETS if c in seen))
with tempfile.TemporaryDirectory() as td:
    tr = t.DocTree(pathlib.Path(td))
    n0 = t.DocNode("b0", text=F * 20 + "Il garante e' Aldo Bini. La caparra e' 450 euro.")
    n1 = t.DocNode("b1", text=F * 20 + "Il termine di consegna e' dodici mesi.")
    tr.save("s", [n0, n1])
    o = t.naviga(M(), tr, "s", "Chi e' il garante e quanto e' la caparra?", budget_tokens=1200, max_hops=2)
    m = o["meta"]
    print("read=%s evicted=%s stopped=%r" % (m["nodes_read"], m["evicted"], m["stopped"]))
    print("answer:", o["text"])
    hits = [c for c in TARGETS if c in o["text"]]
    print("%d/2 narrative facts survived eviction" % len(hits))
    ok = len(hits) == 2 and len(m["nodes_read"]) == 2 and m["evicted"] >= 1 and m["stopped"] == ""
    sys.exit(0 if ok else 1)
