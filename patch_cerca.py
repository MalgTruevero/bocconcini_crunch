import pathlib, shutil, ast, re
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
assert s.count("def _cerca(") == 1
assert s.count("def naviga(") == 1
new = pathlib.Path("cerca_new.txt").read_text(encoding="utf-8")
i = s.index("def _cerca(")
j = s.index("def naviga(", i)
shutil.copy(str(p), str(p) + ".bak4")
s = s[:i] + new.rstrip() + "\n\n\n" + s[j:]
s = re.sub(r'("name": "cerca_nodo",\s*\n\s*"description": )"[^"]*"', r'\1"Search ids, labels, summaries AND the verbatim text of every branch. Returns full ids. Use it when what you need is not on the visible page."', s, count=1)
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("content search enabled")
