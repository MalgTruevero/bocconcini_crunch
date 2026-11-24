from pathlib import Path

p = Path("bocconcini/__init__.py")
code = p.read_text(encoding="utf-8")

old = "trova_fatti, prepara_albero_ricco, calibra_navigazione,"
new = "trova_fatti, prepara_albero_ricco, matrioska_profile, prepare_matrioska_tree, calibra_navigazione,"

if old in code:
    code = code.replace(old, new)
    p.write_text(code, encoding="utf-8")
    print("OK: riga di import aggiornata")
else:
    print("La riga da sostituire non esiste (forse gia' fatta?)")

import sys
for mod in list(sys.modules.keys()):
    if 'bocconcini' in mod:
        del sys.modules[mod]

import bocconcini as b
print("b.matrioska_profile:", hasattr(b, 'matrioska_profile'))
print("b.prepare_matrioska_tree:", hasattr(b, 'prepare_matrioska_tree'))
