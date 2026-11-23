"""Regression: DocTree.vista must never stall pagination. No model, no server."""
import sys, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bocconcini_memory as t
n = fail = 0
def ok(label, cond):
    global n, fail
    n += 1
    if not cond:
        fail += 1
    print("%s %s" % ("OK  " if cond else "FAIL", label))
def walk_pages(tree, session, budget):
    off, ids, pages = 0, [], 0
    while True:
        v = tree.vista(session, budget_tokens=budget, offset=off)
        pages += 1
        ids += [r.split(" | ")[0][5:] for r in v["text"].splitlines() if r.startswith("- id=")]
        nxt = v["next_offset"]
        if nxt is None:
            return ids, pages, True
        if nxt <= off or pages > 500:
            return ids, pages, False
        off = nxt
with tempfile.TemporaryDirectory() as td:
    tr = t.DocTree(pathlib.Path(td))
    tr.save("stall", [t.DocNode("n1", label="L"*110, summary="S"*200, text="x")])
    v = tr.vista("stall", budget_tokens=60)
    row = [r for r in v["text"].splitlines() if r.startswith("- id=")][0]
    ok("oversized row is still shown", v["shown"] == 1)
    ok("oversized row does not stall", v["next_offset"] is None)
    ok("branch id is never cut", row.startswith("- id=n1 |"))
    ok("row was shortened", len(row) < 200)
    w = tr.vista("stall", budget_tokens=60, offset=999)
    ok("offset past the end: no negative count", w["omitted"] == 0 and w["shown"] == 0)
    big = [t.DocNode("s%02d" % i, label="Section %d" % i, summary="K"*1500, text="x")
           for i in range(30)]
    tr.save("big", big)
    ids, pages, done = walk_pages(tr, "big", 300)
    ok("30 oversized summaries: pagination completes", done)
    ok("30 oversized summaries: every id reachable", ids == [x.id for x in big])
    ok("30 oversized summaries: under 10 pages", pages < 10)
    plain = [t.DocNode("p%02d" % i, label="Node %d" % i, summary="numbers: 1, 2", text="t")
             for i in range(25)]
    tr.save("plain", plain)
    ids, pages, done = walk_pages(tr, "plain", 300)
    ok("healthy tree: pagination completes", done and ids == [x.id for x in plain])
    ok("healthy tree: summaries kept in full", "numbers: 1, 2" in tr.vista("plain", budget_tokens=300)["text"])
print("\n%d checks, %d failed" % (n, fail))
sys.exit(1 if fail else 0)
