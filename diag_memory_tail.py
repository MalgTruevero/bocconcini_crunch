import inspect
import bocconcini.memory as m

for fn_name, start in [("naviga", 2500), ("ask_stepwise", 2200)]:
    fn = getattr(m, fn_name)
    s = inspect.getsource(fn)
    print(f"\n=== {fn_name} [{start}:] ===")
    print(s[start:])
