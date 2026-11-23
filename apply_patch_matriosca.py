from pathlib import Path
import ast

p = Path("bocconcini/memory.py")
content = p.read_text(encoding="utf-8")

if "_fatti_in_range" in content:
    print("Patch gia' applicata, salto.")
    raise SystemExit(0)

# --- 1. firma: aggiungo mode, max_children, client ---
sig_old = "tetto_fatti: int = 180)"
sig_new = 'tetto_fatti: int = 180, mode="auto", max_children=None, client=None)'
n = content.count(sig_old)
if n != 1:
    print("ERRORE: firma trovata %d volte (atteso 1)" % n)
    raise SystemExit(1)
content = content.replace(sig_old, sig_new)

# --- 2. helper _fatti_in_range davanti a prepara_albero_ricco ---
helper = '''def _fatti_in_range(tutti_i_fatti, start, end, signal_rank, tetto_fatti):
    """Blocco 'CHIAVE -> ...' con i fatti (ordinati per rarita') in [start, end)."""
    fatti = [
        "%s:%s" % (f["tipo"], f["valore"])
        for f in tutti_i_fatti
        if start <= f["pos"] < end
    ]
    if not fatti:
        return ""
    fatti.sort(key=lambda v: signal_rank.get(v.split(":", 1)[0], 99))
    visibili, usati = [], 0
    for f in fatti:
        f = f if len(f) <= 80 else f[:77] + "..."
        if visibili and usati + len(f) + 2 > tetto_fatti:
            break
        visibili.append(f)
        usati += len(f) + 2
    blocco = "CHIAVE -> " + ", ".join(visibili)
    resto = len(fatti) - len(visibili)
    if resto:
        blocco += " (+%d altri nel ramo)" % resto
    return blocco'''
anchor_fn = "def prepara_albero_ricco("
if content.count(anchor_fn) != 1:
    print("ERRORE: anchor prepara_albero_ricco non unico")
    raise SystemExit(1)
content = content.replace(anchor_fn, helper + "\n\n\n" + anchor_fn)

# --- 3. raggruppamento matriosca prima di tree.save ---
grouping = '''    # --- Matriosca: raggruppa le foglie in macro-blocchi padre->figli ---
    if max_children is None:
        if client is not None:
            try:
                max_children = int(matrioska_profile(client).get("max_children", 8))
            except Exception:
                max_children = 8
        else:
            max_children = 8
    max_children = max(2, int(max_children))
    if mode in ("matriosca", "auto") and len(roots) > max_children:
        foglie = roots
        roots = []
        for g in range(0, len(foglie), max_children):
            gruppo = foglie[g:g + max_children]
            inizio = chunks[g].start
            fine = chunks[g + len(gruppo) - 1].end
            blocco = _fatti_in_range(tutti_i_fatti, inizio, fine, signal_rank, tetto_fatti)
            roots.append(DocNode(
                id="macro_%02d" % (g // max_children),
                label="Macro-blocco %d (sezioni %d-%d)" % (g // max_children, g, g + len(gruppo) - 1),
                summary=blocco,
                text="",
                tokens=sum(c.tokens for c in gruppo),
                children=gruppo,
            ))
'''
anchor_save = "    tree.save(sessione, roots)"
if content.count(anchor_save) != 1:
    print("ERRORE: anchor tree.save non unico (%d)" % content.count(anchor_save))
    raise SystemExit(1)
content = content.replace(anchor_save, grouping + anchor_save)

# --- 4. verifica sintassi prima di scrivere ---
try:
    ast.parse(content)
except SyntaxError as e:
    print("ERRORE SINTASSI, file NON modificato:", e)
    raise SystemExit(1)

p.write_text(content, encoding="utf-8")
print("OK: prepara_albero_ricco supporta mode='matriosca' (default 'auto')")
