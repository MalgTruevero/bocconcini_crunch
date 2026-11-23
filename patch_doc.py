import pathlib, shutil, ast
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
A = '        max_per_tipo: quanti fatti estrarre per tipo (default 100 invece di 40)\n'
assert s.count(A) == 1
add = pathlib.Path("doc_add.txt").read_text(encoding="utf-8")
shutil.copy(str(p), str(p) + ".bak3")
s = s.replace(A, A + add, 1)
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("docstring updated")
