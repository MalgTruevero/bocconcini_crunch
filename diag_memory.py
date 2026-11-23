import inspect
import bocconcini.memory as m

print("FILE:", m.__file__)
src = inspect.getsource(m)
lines = src.splitlines()
print("TOTAL LINES:", len(lines))

for fn_name in ["prepara_albero_ricco", "naviga", "ask_stepwise"]:
    fn = getattr(m, fn_name, None)
    if fn:
        s = inspect.getsource(fn)
        print(f"\n=== {fn_name} (len={len(s)} chars) ===")
        print(s[:2500])
