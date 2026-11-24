import tempfile
from pathlib import Path
import bocconcini as b
from bocconcini import client as C

class Mock(C.LlamaCppClient):
    def __init__(self):
        super().__init__()
        self.n = 0
    def chat_full(self, messages=None, tools=None, **kw):
        self.n += 1
        return C.ChatReply(text="", finish_reason="tool_calls", tool_calls=[
            {"id": "c%d" % self.n, "type": "function",
             "function": {"name": "cerca_nodo", "arguments": '{"query":"codice"}'}}])

doc = "\n\n".join(
    "Sezione %d. Il codice di verifica e' %d. Riempimento vario per allungare." % (i, 1000+i)
    for i in range(40))

m = Mock()
with tempfile.TemporaryDirectory() as t:
    tree, s = b.prepara_albero_ricco(doc, "spam", tree=b.DocTree(Path(t)), max_chars=300)
    out = b.naviga(m, tree, s, "Trova i codici", budget_tokens=1900,
                   max_hops=8, max_tokens=150)
    mt = out["meta"]
    print("searches:", len(mt.get("searches", [])))
    print("evicted:", mt.get("evicted"))
    print("consecutive:", mt.get("_consecutive_searches"))
    print("hops:", mt.get("hops"))
    print("stopped:", mt.get("stopped") or "(nessuno)")
