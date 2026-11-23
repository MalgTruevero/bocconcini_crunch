import pathlib, shutil, ast
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
assert '== "cerca_nodo"][:4]' not in s, "gia applicata"
shutil.copy(str(p), str(p) + ".bak13")
a = 'calls = r.tool_calls[:max(1, int(max_calls))]'
assert s.count(a) == 1, "ancora calls"
b = 'calls = [c for c in r.tool_calls if str(c.get("function", {}).get("name")) == "cerca_nodo"][:4] + [c for c in r.tool_calls if str(c.get("function", {}).get("name")) != "cerca_nodo"][:max(1, int(max_calls))]'
s = s.replace(a, b, 1)
a = "max_calls: int = 2"
assert s.count(a) == 1, "ancora max_calls"
s = s.replace(a, "max_calls: int = 1", 1)
a = '"[you asked for %d branches in one turn; only %d fit. "'
assert s.count(a) == 1, "ancora notice 1"
s = s.replace(a, '"[%d calls asked, %d honoured; "', 1)
a = '"Ask for the others one at a time.]"'
assert s.count(a) == 1, "ancora notice 2"
s = s.replace(a, '"ask the rest one per turn.]"', 1)
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("searches batched, one read per turn")
