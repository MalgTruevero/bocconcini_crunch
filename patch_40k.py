import pathlib, shutil, ast
p = pathlib.Path("test_40k_reale.py")
s = p.read_text(encoding="utf-8")
a = '        tree.save("test", costruisci(modo))\n'
assert s.count(a) == 1
shutil.copy(str(p), str(p) + ".bak")
b = '        if modo:\n            t.prepara_albero_ricco(doc, "test", tree=tree)\n        else:\n            tree.save("test", costruisci(False))\n'
s = s.replace(a, b, 1)
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("40k now calls the library")
