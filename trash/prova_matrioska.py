import pathlib, tempfile
import bocconcini as b

with tempfile.TemporaryDirectory() as td:
    tree = b.DocTree(pathlib.Path(td))
    roots = []
    for p in range(3):
        kids = [b.DocNode(id=f"p{p}_c{c}", label=f"figlio {c}",
                          summary=f"riassunto figlio {c}",
                          text=f"testo originale figlio {c} di padre {p}",
                          tokens=10) for c in range(3)]
        roots.append(b.DocNode(id=f"p{p}", label=f"padre {p}",
                               summary=f"riassunto padre {p}", text="",
                               tokens=0, children=kids))
    tree.save("s", roots)
    print("=== VISTA RADICE (deve mostrare 3 padri, non 12 figli) ===")
    print(tree.vista("s")["text"])
    print("\n=== VISTA DENTRO p0 (deve mostrare i 3 figli di p0) ===")
    print(tree.vista("s", node_id="p0")["text"])
