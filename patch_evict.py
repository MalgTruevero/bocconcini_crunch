import pathlib, shutil, ast, re
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
assert "reads_turn" not in s, "gia' applicata"
shutil.copy(str(p), str(p) + ".bak5")
a = '    newest = max((i for i, m in enumerate(msgs) if m.get("role") == "tool"), default=-1)\n'
b = '    last_ai = max((i for i, m in enumerate(msgs) if m.get("role") == "assistant"), default=-1)\n    fresh = {i for i, m in enumerate(msgs) if m.get("role") == "tool" and i > last_ai}\n'
assert s.count(a) == 1, "ancora newest"
s = s.replace(a, b, 1)
a = '            if i != newest and m.get("role") == "tool" and not m.get("_stub"):\n'
b = '            if i not in fresh and m.get("role") == "tool" and not m.get("_stub"):\n'
assert s.count(a) == 1, "ancora target"
s = s.replace(a, b, 1)
m = re.search(r'^([ \t]*)valid = tree\.keys\(session\)$', s, re.M)
assert m, "valid non trovato"
s = s[:m.end()] + "\n" + m.group(1) + "reads_turn = 0" + s[m.end():]
m = re.search(r'^([ \t]*)else:\n[ \t]*try:\n[ \t]*full = tree\.load\(session, nid\)\n', s, re.M)
assert m, "blocco else/try/load non trovato"
base = m.group(1)
tpl = pathlib.Path("evict_new.txt").read_text(encoding="utf-8").splitlines()
rows = []
for ln in tpl:
    if not ln.startswith("@"):
        rows.append(ln)
        continue
    k = len(ln) - len(ln.lstrip("@")) - 1
    rows.append(base + "    " * k + ln.lstrip("@"))
s = s[:m.start()] + "\n".join(rows) + "\n" + s[m.end():]
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("batch eviction fixed")
