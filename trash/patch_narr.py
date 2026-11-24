import pathlib, shutil, ast, re
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
assert "per_msg: float = 8.0, question" not in s, "gia applicata"
shutil.copy(str(p), str(p) + ".bak12")
a = "def _evict(msgs: List[Dict[str, Any]], budget: int, cpt: float, per_msg: float = 8.0) -> int:"
assert s.count(a) == 1, "firma evict"
b = 'def _evict(msgs: List[Dict[str, Any]], budget: int, cpt: float, per_msg: float = 8.0, question: str = "") -> int:'
s = s.replace(a, b, 1)
a = "_evict(msgs, max(200, budget - 256), cpt, ovh)"
assert s.count(a) == 1, "evict turn"
s = s.replace(a, "_evict(msgs, max(200, budget - 256), cpt, ovh, question)", 1)
a = "_evict(msgs, budget, cpt, ovh)"
assert s.count(a) == 1, "evict final"
s = s.replace(a, "_evict(msgs, budget, cpt, ovh, question)", 1)
m = re.search(r'^([ \t]*)kept = str\(msgs\[target\]\.get\("_facts"\) or ""\)\n', s, re.M)
assert m, "kept anchor"
i = m.group(1)
new = i + 'if not kept and question:\n'
new += i + '    old = str(msgs[target].get("content") or "")\n'
new += i + '    words = {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ0-9_]{3,}", question)}\n'
new += i + '    parts = re.split(r"(?<=[.!?])\\s+", old)\n'
new += i + '    kept = " ".join(seg.strip() for seg in parts if any(w in seg.lower() for w in words))[:180]\n'
s = s[:m.end()] + new + s[m.end():]
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("eviction keeps question-relevant text")
