from pathlib import Path

p = Path("bocconcini/memory.py")
code = p.read_text(encoding="utf-8")

old = '__all__ = ["DocNode", "DocTree", "TreeError", "etichetta", "naviga", "albero_codice", "trova_fatti", "prepara_albero_ricco", "calibra_navigazione"]'
new = '__all__ = ["DocNode", "DocTree", "TreeError", "etichetta", "naviga", "albero_codice", "trova_fatti", "prepara_albero_ricco", "matrioska_profile", "prepare_matrioska_tree", "calibra_navigazione"]'

if old in code:
    code = code.replace(old, new)
    p.write_text(code, encoding="utf-8")
    print("✅ Step 2 completato: __all__ aggiornato in memory.py")
elif new in code:
    print("ℹ️ Step 2 già fatto: __all__ contiene già le nuove funzioni")
else:
    print("⚠️ Attenzione: formato __all__ non riconosciuto, controllo manuale necessario")
