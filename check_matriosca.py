from bocconcini.memory import prepara_albero_ricco, DocTree

doc = "\n".join([f"## Sez {i}: Tema_{i%5}\nTesto sezione {i} con dettaglio tecnico.\n" + ("Nota: codice controllo TEST-1234.\n" if i == 25 else "") for i in range(60)])

tree, sess = prepara_albero_ricco(doc, "check_matriosca", max_chars=900)
print("KEYS:", list(tree.keys(sess))[:8])
print("VISTA:", str(tree.vista(sess))[:500])

# I nodi in index.json sono già dizionari plain (risultato di _plain in save)
roots = tree.index(sess).get("nodes", [])
print("PLAIN sample:", str(roots[:3])[:500])
