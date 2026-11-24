import pathlib, ast
p = pathlib.Path("test_40k_reale.py")
L = p.read_text(encoding="utf-8").splitlines(True)
idx = [i for i, l in enumerate(L) if "risposta" in l]
assert len(idx) == 1, "ancora risposta non unica"
i = idx[0] + 1
assert "deferred" not in "".join(L), "gia' applicata"
L.insert(i, pathlib.Path("diag.txt").read_text(encoding="utf-8"))
s = "".join(L)
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("diagnostics added")
