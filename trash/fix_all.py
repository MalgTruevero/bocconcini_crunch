from pathlib import Path
import sys

print("=== DIAGNOSI E FIX ===")

# --- Fix __init__.py ---
p = Path("bocconcini/__init__.py")
code = p.read_text(encoding="utf-8")

if "matrioska_profile" not in code:
    code = code.replace(
        "prepara_albero_ricco, calibra_navigazione,",
        "prepara_albero_ricco, matrioska_profile, prepare_matrioska_tree, calibra_navigazione,"
    )
    code = code.replace(
        '"prepara_albero_ricco", "calibra_navigazione",',
        '"prepara_albero_ricco", "matrioska_profile", "prepare_matrioska_tree", "calibra_navigazione",'
    )
    p.write_text(code, encoding="utf-8")
    print("[__init__.py] Fix applicato")
else:
    print("[__init__.py] Gia' a posto")

# --- Verifica memory.py ---
pm = Path("bocconcini/memory.py")
mcode = pm.read_text(encoding="utf-8")
if "def matrioska_profile" in mcode:
    print("[memory.py] matrioska_profile presente")
else:
    print("[memory.py] ERRORE: matrioska_profile MANCANTE!")

if "def prepare_matrioska_tree" in mcode:
    print("[memory.py] prepare_matrioska_tree presente")
else:
    print("[memory.py] ERRORE: prepare_matrioska_tree MANCANTE!")

# --- Test import (forza reimport pulito) ---
print("\n=== TEST IMPORT ===")
try:
    for mod in list(sys.modules.keys()):
        if 'bocconcini' in mod:
            del sys.modules[mod]

    import bocconcini as b
    ok1 = hasattr(b, 'matrioska_profile')
    ok2 = hasattr(b, 'prepare_matrioska_tree')
    print(f"b.matrioska_profile: {ok1}")
    print(f"b.prepare_matrioska_tree: {ok2}")

    if ok1 and ok2:
        print("\nTUTTO OK! Ora puoi lanciare il test del profilo adattivo.")
    else:
        print("\nERRORE: l'import non espone le funzioni.")
        print("--- Contenuto attuale di __init__.py ---")
        print(Path("bocconcini/__init__.py").read_text(encoding="utf-8"))
except Exception as e:
    print(f"Errore durante l'import: {e}")
    import traceback
    traceback.print_exc()
