import inspect
import bocconcini.memory as m
from bocconcini.memory import prepara_albero_ricco

doc = "\n".join([f"## Sez {i}\nTesto {i}.\n" + ("Nota: codice controllo TEST-1234.\n" if i == 25 else "") for i in range(40)])
tree, sess = prepara_albero_ricco(doc, "check_matriosca", max_chars=900)
ks = list(tree.keys(sess))
print("KEYS:", ks[:8], "TOTAL:", len(ks))

for fn_name in ("prepara_albero_ricco", "naviga", "ask_stepwise"):
    fn = getattr(m, fn_name, None)
    if fn:
        src_lines, start = inspect.getsourcelines(fn)
        print(f"=== {fn_name} ({m.__file__}:{start}) ===")
        for idx, line in enumerate(src_lines, start):
            print(f"{idx:4d}: {line}", end="")
        print()
