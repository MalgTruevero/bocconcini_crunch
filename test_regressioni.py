import sys, pathlib, tempfile, json
from collections import Counter
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bocconcini as b
import bocconcini_tree as t

n = fail = 0
def ok(name, cond):
    global n, fail
    n += 1
    print("OK  " if cond else "FAIL", name)
    if not cond:
        fail += 1

cl = b.LlamaCppClient(n_ctx=4096); cl.model = "test"
cl.tokenizer = type("T", (), {"_backend": 0, "_down_until": 0.0})()
r = b.ChatReply(text="x"); r.meta["prompt_tokens_real"] = 952
cl._check_truncation(1125, r)
ok("truncation: lontano dalla finestra non scatta", r.meta.get("prompt_truncated") is None)
r2 = b.ChatReply(text="x"); r2.meta["prompt_tokens_real"] = 2000
cl._check_truncation(3700, r2)
ok("truncation: vicino alla finestra scatta", r2.meta.get("prompt_truncated") is True)

cl2 = b.LlamaCppClient(n_ctx=4096); cl2.model = "test"
cl2._prompt_tokens = lambda msgs, tools_tokens=0: sum(len(str(m.get("content") or "")) for m in msgs)
msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "U" * 500}]
meta = {}
out = cl2._reduce_messages(msgs, 50, None, meta)
ok("la richiesta non viene compressa", out[-1]["content"] == "U" * 500 and bool(meta.get("reduce_skipped")))

filler = "Il sistema operativo rileva un picco di utilizzo della CPU e rialloca i thread. " * 400
aghi = {10: "Il codice di sblocco della batteria e' ALFA-1.",
        35: "La password del database di telemetria e' OMEGA-9.",
        60: "Il nome in codice del satellite e' TITANO-3.",
        85: "La chiave API del server di backup e' BETA-7."}
doc = filler
for pct, frase in sorted(aghi.items()):
    k = int(len(doc) * pct / 100)
    doc = doc[:k] + "\n" + frase + "\n" + doc[k:]
fatti = t.trova_fatti(doc)
vals = {f["valore"] for f in fatti}
ok("trova_fatti: 4 aghi", {"ALFA-1", "OMEGA-9", "TITANO-3", "BETA-7"} <= vals)
ok("trova_fatti: contesto del fatto", any(f["valore"] == "ALFA-1" and "batteria" in f["contesto"] for f in fatti))

with tempfile.TemporaryDirectory() as td:
    tr = t.DocTree(pathlib.Path(td))
    tr.save("s", [t.DocNode("cap/1", text="A"), t.DocNode("cap 1", text="B"), t.DocNode("vuoto", text="")])
    ok("albero: chiavi senza collisione", tr.load("s", "cap/1") == "A" and tr.load("s", "cap 1") == "B")
    ok("albero: ramo vuoto", tr.load("s", "vuoto") == "")
    try:
        tr.load("s", "no"); missing = False
    except t.TreeError:
        missing = True
    ok("albero: ramo mancante solleva", missing)
    tr.save("s", [t.DocNode("cap/1", text="NUOVO")])
    try:
        tr.load("s", "cap 1"); stale = False
    except t.TreeError:
        stale = True
    ok("albero: stale rimosso", stale)

with tempfile.TemporaryDirectory() as td:
    p = pathlib.Path(td) / "m.py"
    src = "# commento\nimport os\n\nCONST = 1\n\ndef f(x):\n    return x\n\nclass C:\n    def m(self):\n        return 2\n"
    p.write_text(src, encoding="utf-8")
    tutti = list(t._walk(t.albero_codice(p)))
    orig = Counter(src.splitlines())
    rico = Counter(l for nd in tutti if nd.text for l in nd.text.split("\n"))
    ok("albero_codice: lossless", sum((orig - rico).values()) == 0 and sum((rico - orig).values()) == 0)

class R:
    def __init__(self, text="", calls=None):
        self.text, self.tool_calls = text, calls or []
class Finto:
    def __init__(self):
        self.n = 0
    def chat_full(self, **kw):
        self.n += 1
        if self.n == 1:
            return R(calls=[{"id": "a", "function": {"name": "leggi_nodo", "arguments": json.dumps({"id": "indice"})}}])
        if self.n == 2:
            return R(calls=[{"id": "b", "function": {"name": "leggi_nodo", "arguments": json.dumps({"id": "caparra"})}}])
        return R("Il garante e' Aldo Bini.")

with tempfile.TemporaryDirectory() as td:
    tr = t.DocTree(pathlib.Path(td))
    tr.save("c", [t.DocNode("radice", label="Contratto", children=[
        t.DocNode("canone", label="Canone", text="450 euro. " * 20),
        t.DocNode("caparra", label="Caparra", text="900 euro. Il garante e' Aldo Bini. " * 20)])])
    out = t.naviga(Finto(), tr, "c", "Chi e' il garante?", budget_tokens=800, max_hops=2)
    ok("naviga: corregge id inventato", out["meta"].get("unknown_ids") == ["indice"] and "caparra" in out["meta"]["nodes_read"])
    ok("naviga: risposta letta", "Aldo Bini" in out["text"])

print("\n%d verifiche, %d fallite" % (n, fail))
sys.exit(1 if fail else 0)
