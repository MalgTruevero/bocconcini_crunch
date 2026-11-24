import sys
print("=== VERIFICA IMPORT ===")
try:
    import bocconcini as b
    print("import bocconcini: OK")
except Exception as e:
    print("ERRORE IMPORT:", e)
    sys.exit(1)

print("\n=== VERIFICA FUNZIONI ===")
checks = [
    ("trova_fatti", hasattr(b, 'trova_fatti')),
    ("prepara_albero_ricco", hasattr(b, 'prepara_albero_ricco')),
    ("naviga", hasattr(b, 'naviga')),
    ("DocTree", hasattr(b, 'DocTree')),
    ("DocNode", hasattr(b, 'DocNode')),
    ("LlamaCppClient", hasattr(b, 'LlamaCppClient')),
    ("matrioska_profile", hasattr(b, 'matrioska_profile')),
    ("prepare_matrioska_tree", hasattr(b, 'prepare_matrioska_tree')),
]
all_ok = True
for name, ok in checks:
    print("  %s: %s" % (name, "OK" if ok else "MANCANTE"))
    if not ok:
        all_ok = False

print("\n=== VERIFICA _SFOGLIA in memory.py ===")
from bocconcini import memory
has_sfoglia = hasattr(memory, '_SFOGLIA')
print("  _SFOGLIA definito:", "OK" if has_sfoglia else "MANCANTE")

print("\n=== TEST FUNZIONALE: trova_fatti + _cerca ===")
fatti = b.trova_fatti("Il codice e' 4821 e il signor Bianchi ha piantato un girasole.")
ok_num = any(f['tipo'] == 'numero' and f['valore'] == '4821' for f in fatti)
ok_nome = any(f['tipo'] == 'nome' and f['valore'] == 'Bianchi' for f in fatti)
print("  trova_fatti numero 4821:", "OK" if ok_num else "MANCANTE")
print("  trova_fatti nome Bianchi:", "OK" if ok_nome else "MANCANTE")

import tempfile
from pathlib import Path
from bocconcini.memory import _cerca, DocTree, DocNode

doc = "Il codice di verifica e' 4821. Il signor Bianchi ha piantato un girasole."
with tempfile.TemporaryDirectory() as tmp:
    tree = DocTree(Path(tmp))
    tree.save("test", [DocNode(id="sec_000", label="Sezione 0", summary="", text=doc)])
    body, hits = _cerca(tree, "test", "codice segreto")
    ok_fuzzy = "sec_000" in hits
    print("  _cerca fuzzy 'codice segreto':", "OK" if ok_fuzzy else "MANCANTE")

print("\n=== TEST MATRIOSKA ===")
doc2 = ""
for i in range(40):
    doc2 += "Sezione %d. " % i
    doc2 += ("Contenuto generico della sezione %d con dettagli e parole varie per allungare. " % i) * 8
    doc2 += "\n\n"
doc2 += "CODICE SEGRETO ALPHA-7788 presente qui.\n"

with tempfile.TemporaryDirectory() as tmp:
    tree = DocTree(Path(tmp))
    tree, s = b.prepara_albero_ricco(doc2, "matrioska_test", tree=tree, mode="matriosca", max_children=8)
    roots = tree.index(s)["nodes"]
    print("  Macro-blocchi creati:", len(roots))
    has_children = all(len(r.get("children", [])) > 0 for r in roots)
    print("  Tutti hanno figli:", "OK" if has_children else "MANCANTE")
    macro_empty = all(tree.load(s, r["id"]) == "" for r in roots)
    print("  Macro-blocchi vuoti (contenitori):", "OK" if macro_empty else "MANCANTE")

print("\n=== RISULTATO ===")
if all_ok and ok_num and ok_nome and ok_fuzzy and has_children and macro_empty:
    print("TUTTI I TEST SUPERATI")
else:
    print("QUALCOSA NON VA")
