import pathlib
p = pathlib.Path("test_step.py")
L = p.read_text(encoding="utf-8").splitlines(True)
for i, l in enumerate(L):
    if "ask_stepwise(" in l and "targets=" not in l:
        k = l.rfind("[")
        L[i] = l[:k] + "targets=" + l[k:]
p.write_text("".join(L), encoding="utf-8")
print("fixed")
