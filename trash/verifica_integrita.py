import bocconcini as b

doc = "Il codice di sblocco della batteria e' ALFA-1.\n" * 50
tree, sessione = b.prepara_albero_ricco(doc, "test")
keys = tree.keys(sessione)
print(f"Nodi creati: {len(keys)}\n")

for kid, meta in keys.items():
    # Estraggo le posizioni dal label
    label = meta['label']  # "Sezione 1 (pos 1457-2350)"
    start_str = label.split('(pos ')[1].split('-')[0]
    end_str = label.split('-')[1].split(')')[0]
    start = int(start_str)
    end = int(end_str)
    
    # Testo dal disco
    testo_disk = tree.load(sessione, kid)
    
    # Testo dal documento originale
    testo_doc = doc[start:end]
    
    # Verifica byte-identica
    identico = testo_disk == testo_doc
    
    print(f"{kid}:")
    print(f"  Posizione originale: {start}-{end}")
    print(f"  Lunghezza disco: {len(testo_disk)}")
    print(f"  Lunghezza doc: {len(testo_doc)}")
    print(f"  Byte-identico: {identico}")
    
    if not identico:
        print(f"  DIFFERENZA RILEVATA!")
        print(f"  Primi 100 char disco: {repr(testo_disk[:100])}")
        print(f"  Primi 100 char doc:  {repr(testo_doc[:100])}")
    print()
