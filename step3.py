from pathlib import Path

p = Path("bocconcini/__init__.py")
code = p.read_text(encoding="utf-8")

old_import = """from .memory import (
DocNode, DocTree, TreeError, etichetta, naviga, albero_codice,
trova_fatti, prepara_albero_ricco, calibra_navigazione,
)"""
new_import = """from .memory import (
DocNode, DocTree, TreeError, etichetta, naviga, albero_codice,
trova_fatti, prepara_albero_ricco, matrioska_profile, prepare_matrioska_tree, calibra_navigazione,
)"""

code = code.replace(old_import, new_import)

old_all = '"trova_fatti", "prepara_albero_ricco", "calibra_navigazione",'
new_all = '"trova_fatti", "prepara_albero_ricco", "matrioska_profile", "prepare_matrioska_tree", "calibra_navigazione",'

code = code.replace(old_all, new_all)

p.write_text(code, encoding="utf-8")
print("✅ Step 3 completato: __init__.py aggiornato. La libreria ora esporta le nuove funzioni!")
