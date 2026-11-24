import pathlib, ast
p = pathlib.Path("test_batch_reads.py")
L = p.read_text(encoding="utf-8").splitlines(True)
a = "        if self.n == 1:\n"
assert L.count(a) == 1, "ancora if non unica"
i = L.index(a) + 1
assert "return R(calls=" not in L[i], "gia' riparato"
L.insert(i, pathlib.Path("batch_body.txt").read_text(encoding="utf-8"))
s = "".join(L)
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("batch test repaired")
