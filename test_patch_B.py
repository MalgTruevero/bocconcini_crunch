import tempfile
from pathlib import Path
import bocconcini as b
from bocconcini.memory import _cerca, DocTree, DocNode

print("=== TEST 1: trova_fatti con numeri e nomi ===")
fatti = b.trova_fatti("Il codice e' 4821 e il signor Bianchi ha piantato un girasole.")
for f in fatti:
    print("  %s -> %s" % (f['tipo'], f['valore']))
ok_num = any(f['tipo'] == 'numero' and f['valore'] == '4821' for f in fatti)
ok_nome = any(f['tipo'] == 'nome' and f['valore'] == 'Bianchi' for f in fatti)
print("numero 4821:", "TROVATO" if ok_num else "MANCANTE")
print("nome Bianchi:", "TROVATO" if ok_nome else "MANCANTE")

print("\n=== TEST 2: _cerca fuzzy multi-parola ===")
doc = "Il codice di verifica e' 4821. Il signor Bianchi ha piantato un girasole."
with tempfile.TemporaryDirectory() as tmp:
    tree = DocTree(Path(tmp))
    tree.save("test", [DocNode(id="sec_000", label="Sezione 0", summary="", text=doc)])
    # 'codice segreto' NON e' sottostringa esatta del testo, ma 'codice' si'
    body, hits = _cerca(tree, "test", "codice segreto")
    print("Cerca 'codice segreto' ->", hits)
    ok_fuzzy = "sec_000" in hits
    print("fuzzy:", "TROVATO" if ok_fuzzy else "MANCANTE")

print("\n=== RISULTATO ===")
if ok_num and ok_nome and ok_fuzzy:
    print("TUTTI I TEST SUPERATI")
else:
    print("QUALCOSA NON VA, controlla gli output sopra")
