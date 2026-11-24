import pathlib, shutil, ast, re
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
assert "alt != q" not in s, "gia' applicata"
shutil.copy(str(p), str(p) + ".bak10")
m = re.search(r'^([ \t]*)if not hits:\n[ \t]*return "\[no branch matches', s, re.M)
assert m, "ancora no-match non trovata"
i = m.group(1)
new = (i + 'if not hits:\n' + i + '    alt = re.sub(r"^[a-z]+\\s*[:\\s]\\s*", "", q).strip()\n' + i + '    if alt and alt != q:\n' + i + '        return _cerca(tree, session, alt, limit)\n')
s = s[:m.start()] + new + s[m.start():]
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("search tolerates the index prefix")
