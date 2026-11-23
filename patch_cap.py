from pathlib import Path
import ast

p = Path("bocconcini/memory.py")
code = p.read_text(encoding="utf-8")

old_cap = "cap = max(300, int(budget * cpt * 0.5))"
new_cap = """# Riserva il 60% del budget per le letture, il 40% per costi fissi e risposta
    # Sottrai l'overhead degli assistant tool_call (uno per turno)
    reads_budget = budget * 0.6
    per_read_budget = (reads_budget - 40 * max(1, int(max_hops))) / max(1, int(max_hops))
    cap = max(200, int(per_read_budget * cpt))"""

if old_cap not in code:
    print("ERRORE: formula cap non trovata")
    raise SystemExit(1)

code = code.replace(old_cap, new_cap, 1)

try:
    ast.parse(code)
except SyntaxError as e:
    print("ERRORE SINTASSI:", e)
    raise SystemExit(1)

p.write_text(code, encoding="utf-8")
print("✅ Patch cap applicata: ora naviga permette più letture nello stesso budget")
