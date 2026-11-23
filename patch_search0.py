import pathlib, ast
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
a = 'tools_now = None if final else ([_LEGGI] if (require_read and not meta["nodes_read"]) else [_LEGGI, _CERCA])'
assert s.count(a) == 1, "ancora tools_now"
s = s.replace(a, 'tools_now = None if final else [_LEGGI, _CERCA]', 1)
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("search available from turn 0")
