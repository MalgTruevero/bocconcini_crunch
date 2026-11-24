import tempfile
from pathlib import Path
import bocconcini as b

# documento abbastanza grande da produrre piu' di 8 chunk
doc = ""
for i in range(40):
    doc += "Sezione %d. " % i
    doc += ("Contenuto generico della sezione %d con dettagli e parole varie per allungare. " % i) * 8
    doc += "\n\n"
doc += "CODICE SEGRETO ALPHA-7788 presente qui.\n"

with tempfile.TemporaryDirectory() as tmp:
    tree = b.DocTree(Path(tmp))

    # piatto (controllo)
    tree, s1 = b.prepara_albero_ricco(doc, "piatto", tree=tree, mode="flat")
    flat_roots = tree.index(s1)["nodes"]
    print("FLAT: %d radici (foglie)" % len(flat_roots))

    # matriosca
    tree, s2 = b.prepara_albero_ricco(doc, "matriosca", tree=tree, mode="matriosca", max_children=8)
    roots = tree.index(s2)["nodes"]
    print("\nMATRIOSCA: %d macro-blocchi" % len(roots))
    for r in roots:
        figli = r.get("children", [])
        print("  %s | %s | figli=%d" % (r["id"], r["label"], len(figli)))
        print("     summary: %.70s" % (r.get("summary", "") or "(nessuna)"))

    # il testo dei figli deve essere integro su disco
    if roots and roots[0].get("children"):
        fid = roots[0]["children"][0]["id"]
        testo = tree.load(s2, fid)
        print("\nTesto primo figlio (%s), primi 80 char:" % fid)
        print("  %.80s..." % testo.replace("\n", " "))

    # il macro-blocco e' un contenitore: testo proprio vuoto
    print("\nTesto del macro-blocco (deve essere vuoto): %r" % tree.load(s2, roots[0]["id"]))
