import pathlib, shutil, ast, re
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
assert "seen.get(nid, 0) >= max_repeats" not in s, "gia' applicata"
shutil.copy(str(p), str(p) + ".bak6")
m = re.search(r'^[ \t]*seen\[nid\] = seen\.get\(nid, 0\) \+ 1\n', s, re.M)
assert m, "incremento seen non trovato"
s = s[:m.start()] + s[m.end():]
a = "elif seen[nid] > max_repeats:"
assert s.count(a) == 1, "ancora elif seen"
s = s.replace(a, "elif seen.get(nid, 0) >= max_repeats:", 1)
m = re.search(r'^([ \t]*)meta\["nodes_read"\]\.append\(nid\)\n', s, re.M)
assert m, "nodes_read non trovato"
s = s[:m.end()] + m.group(1) + "seen[nid] = seen.get(nid, 0) + 1\n" + s[m.end():]
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("repeats now count reads, not requests")
