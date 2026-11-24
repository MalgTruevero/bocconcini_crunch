import json, re, tempfile
from pathlib import Path
import bocconcini as b

CPT, OVH = 3.2, 12.0
AGHI = ["ALFA-1111","BETA-2222","GAMMA-3333","DELTA-4444","EPSILON-5555","ZETA-6666"]

class R:
    def __init__(s, text="", calls=None):
        s.text, s.tool_calls, s.reasoning = text, calls or [], ""
        s.meta, s.finish_reason, s.tokens = {}, "stop", 8

class FakeClient:
    """Simula un 4B disciplinato: cerca, legge N rami, poi risponde."""
    def __init__(s, reads=3):
        s.reads_target, s.calls, s.trace = reads, 0, []
    def _hw(s): return {"msg_overhead": OVH}
    def _prompt_tokens(s, msgs, tt=0):
        t = "\n".join(str(m.get("content") or "") for m in msgs)
        return int(len(t)/CPT) + 1 + int(OVH*len(msgs)) + tt
    @staticmethod
    def _call(n, a):
        return {"id":"c_%s"%n, "type":"function",
                "function":{"name":n,"arguments":json.dumps(a)}}
    def chat_full(s, prompt=None, messages=None, tools=None, **kw):
        s.calls += 1
        if messages is None:
            return s._step(prompt or "")
        s.trace.append(s._prompt_tokens(messages))
        if tools is None:
            return R(text=s._answer(messages))
        tm = [str(m.get("content") or "") for m in messages if m.get("role")=="tool"]
        cand = []
        for t in tm:
            if "Matching branches" in t:
                cand += re.findall(r"^- (\S+) \[LEAF\]", t, re.M)
        asked = []
        for m in messages:
            if m.get("role") == "assistant":
                for c in (m.get("tool_calls") or []):
                    try:
                        a = json.loads(c["function"]["arguments"])
                        if a.get("id"): asked.append(a["id"])
                    except Exception: pass
        nread = sum(1 for m in messages if m.get("role")=="assistant"
                    for c in (m.get("tool_calls") or [])
                    if c["function"]["name"] == "leggi_nodo")
        if not cand:
            q = " ".join([w for w in re.findall(r"[a-z0-9]{4,}", s._domanda(messages).lower())
                          if w not in ("qual","quale","trova","tutti","documento","nascosto")][:3])
            return R(calls=[s._call("cerca_nodo", {"query": q or "codice"})])
        todo = [c for c in cand if c not in asked]
        if todo and nread < s.reads_target:
            return R(calls=[s._call("leggi_nodo", {"id": todo[0]})])
        return R(text=s._answer(messages))
    @staticmethod
    def _domanda(msgs):
        for m in msgs:
            if m.get("role")=="user" and "calls asked" not in str(m.get("content")):
                return str(m.get("content"))
        return ""
    @staticmethod
    def _aghi(texts):
        out = []
        for t in texts:
            for m in re.findall(r"\b[A-Z]{3,}-\d{3,4}\b", t):
                if m not in out: out.append(m)
        return out
    def _answer(s, msgs):
        f = s._aghi([str(m.get("content") or "") for m in msgs if m.get("role")=="tool"])
        return ("Codici trovati: " + ", ".join(f)) if f else "non trovato"
    def _step(s, p):
        if "VERBATIM EXCERPTS" in p:
            m = re.search(r"\b[A-Z]{3,}-\d{3,4}\b", p) or re.search(r"\b\d{4,}\b", p)
            return R(text=m.group(0) if m else "NOT FOUND")
        if "FINDINGS already extracted" in p:
            body = p.split("FINDINGS already extracted:")[1].split("Answer this request")[0]
            f = s._aghi([body])
            return R(text="Codici: " + ", ".join(f))
        return R(text="")

def build_doc():
    out = []
    for i in range(66):
        out.append("Sezione %d. " % i)
        out.append(("Contenuto generico della sezione %d con dettagli vari per allungare. " % i)*5)
        out.append("\n\n")
    for n, ago in enumerate(AGHI):
        out[3 + n*11] += "Il codice di verifica di questa sezione e' %s.\n\n" % ago
    return "".join(out)

doc = build_doc()
print("documento: %d char (~%d token), %d aghi" % (len(doc), int(len(doc)/CPT), len(AGHI)))

with tempfile.TemporaryDirectory() as tmp:
    tree = b.DocTree(Path(tmp))
    tree, ses = b.prepara_albero_ricco(doc, "e2e_off", tree=tree, max_chars=800)
    roots = tree.index(ses)["nodes"]
    print("albero: %d radici, %d nodi totali" % (len(roots), len(tree.keys(ses))))

    for reads in (1, 3, 5):
        c = FakeClient(reads=reads)
        out = b.naviga(c, tree, ses, "Qual e' il codice di verifica nascosto nel documento?",
                       budget_tokens=1900, max_hops=6, max_tokens=200)
        m = out["meta"]
        trov = [a for a in AGHI if a in out["text"]]
        print("\n--- NAVIGA (reads_target=%d) ---" % reads)
        print("  hops=%s letti=%s deferred=%s evicted=%s tagliati=%s"
              % (m.get("hops"), len(m.get("nodes_read",[])), m.get("deferred",0),
                 m.get("evicted"), len(m.get("branches_cut",[]))))
        print("  stopped:", m.get("stopped") or "(nessuno)")
        print("  prompt per turno:", c.trace)
        print("  max prompt: %d / budget 1900" % (max(c.trace) if c.trace else 0))
        print("  aghi trovati: %d/%d %s" % (len(trov), len(AGHI), trov))

    c2 = FakeClient()
    sw = b.ask_stepwise(c2, doc, "Elenca tutti i codici", targets=list(AGHI),
                        max_tokens=60, window=200)
    t2 = [a for a in AGHI if a in sw["text"]]
    print("\n--- ASK_STEPWISE ---")
    print("  sub_calls:", sw["meta"]["sub_calls"])
    print("  prompt piu' grande: %d char" % sw["meta"]["biggest_prompt_chars"])
    print("  findings:", sw["meta"]["findings"])
    print("  aghi nella risposta: %d/%d" % (len(t2), len(AGHI)))
