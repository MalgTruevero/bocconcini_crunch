import pathlib, ast
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
a = '"naviga", "calibra_navigazione"]'
assert s.count(a) == 1, "ancora __all__"
s = s.replace(a, '"naviga", "ask_stepwise", "calibra_navigazione"]', 1)
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("ask_stepwise exported")
