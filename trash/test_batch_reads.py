"""Regression: a model that asks for MANY branches in one turn must receive them.
The old eviction stubbed every branch but the newest before the model had seen
any of them, so it re-requested for ever. No server, no model: deterministic."""
import sys, json, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bocconcini_memory as t
class R:
    def __init__(self, text="", calls=None):
        self.text, self.tool_calls = text, calls or []
class Batch:
    """Asks for four branches at once, like a real 4B tool-caller does."""
    def __init__(self):
        self.n = 0
        self.msgs = None
    def chat_full(self, **kw):
        self.n += 1
        if self.n == 1:
            return R(calls=[{"id": "c%d" % i, "function": {
                "name": "leggi_nodo", "arguments": json.dumps({"id": "b%d" % i})}}
                for i in range(4)])
        self.msgs = kw.get("messages")
        return R("fatto")
n = fail = 0
def ok(label, cond, extra=""):
    global n, fail
    n += 1
    if not cond:
        fail += 1
    print("%s %s%s" % ("OK  " if cond else "FAIL", label, "" if cond else "  <- " + str(extra)))
with tempfile.TemporaryDirectory() as td:
    tr = t.DocTree(pathlib.Path(td))
    tr.save("s", [t.DocNode("b%d" % i, label="Branch %d" % i, text=("riga %d. " % i) * 170)
                  for i in range(4)])
    cl = Batch()
    out = t.naviga(cl, tr, "s", "che cosa dicono i rami?", budget_tokens=1300, max_hops=2)
    meta = out["meta"]
    ok("the model got a second turn", cl.msgs is not None, meta.get("stopped"))
    tools = [m for m in (cl.msgs or []) if m.get("role") == "tool"]
    ok("no branch was stubbed before being seen", not any(m.get("_stub") for m in tools))
    ok("the read branch arrived intact",
       any("riga 0." in str(m.get("content", "")) for m in tools))
    ok("every requested branch is accounted for",
       len(meta["nodes_read"]) + meta.get("deferred", 0) == 4,
       (meta["nodes_read"], meta.get("deferred")))
    ok("what did not fit is declared, not dropped", meta.get("deferred", 0) >= 1,
       meta.get("deferred"))
print("\n%d checks, %d failed" % (n, fail))
sys.exit(1 if fail else 0)
