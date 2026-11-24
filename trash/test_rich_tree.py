"""Regression: prepara_albero_ricco must bound summaries AND keep codes visible."""
import sys, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bocconcini.memory as t
n = fail = 0
def ok(label, cond, extra=""):
    global n, fail
    n += 1
    if not cond:
        fail += 1
    print("%s %s%s" % ("OK  " if cond else "FAIL", label, "" if cond else "  <- " + str(extra)))
NEEDLES = ("ALFA-1", "OMEGA-9", "TITANO-3", "BETA-7")
line = 'Log %d: cache %d GB, clock %d GHz, key API%dX9K2M4P7Q1W8Z, "node state %d".\n'
doc = "".join(line % (i, i % 7, i % 5 + 1, i, i) for i in range(120))
for i, code in enumerate(NEEDLES):
    k = int(len(doc) * (10 + 25 * i) / 100)
    doc = doc[:k] + "\n[CRITICAL] The unlock code is %s.\n" % code + doc[k:]
with tempfile.TemporaryDirectory() as td:
    tr = t.DocTree(pathlib.Path(td))
    tr, sess = t.prepara_albero_ricco(doc, "rich", tree=tr)
    keys = tr.keys(sess)
    index = " ".join(str(v.get("summary", "")) + " " + str(v.get("label", "")) for v in keys.values())
    longest = max(len(str(v.get("summary", ""))) for v in keys.values())
    ok("every summary is bounded", longest < 400, longest)
    seen = [c for c in NEEDLES if c in index]
    ok("all 4 codes visible in the index", len(seen) == 4, sorted(set(NEEDLES) - set(seen)))
    facts = t.trova_fatti(doc, max_per_tipo=100)
    ok("document dense enough to exercise the cap", len(facts) > 100, len(facts))
    print("    chunks=%d facts=%d longest_summary=%d" % (len(keys), len(facts), longest))
    off, ids, pages = 0, [], 0
    while True:
        v = tr.vista(sess, budget_tokens=300, offset=off)
        pages += 1
        ids += [r.split(" | ")[0][5:] for r in v["text"].splitlines() if r.startswith("- id=")]
        nxt = v["next_offset"]
        if nxt is None or nxt <= off or pages > 500:
            break
        off = nxt
    ok("real rich tree: pagination completes", nxt is None and len(ids) == len(keys), (pages, len(ids), len(keys)))
print("\n%d checks, %d failed" % (n, fail))
sys.exit(1 if fail else 0)
