from pathlib import Path
import ast

p = Path("bocconcini/memory.py")
code = p.read_text(encoding="utf-8")

print("=== ISPEZIONE STATO ATTUALE ===")
has_numero = '("numero", re.compile(' in code
has_nome = '("nome", re.compile(' in code
has_fuzzy = "Fuzzy fallback" in code
print("_FATTO numero:", "PRESENTE" if has_numero else "MANCANTE")
print("_FATTO nome:  ", "PRESENTE" if has_nome else "MANCANTE")
print("_cerca fuzzy: ", "PRESENTE" if has_fuzzy else "MANCANTE")

lines = code.split("\n")
modified = False

# === FIX 1: aggiungi numero/nome a _FATTO se mancanti ===
if not has_numero or not has_nome:
    entries = []
    if not has_numero:
        entries.append('("numero", re.compile(r"\\b\\d{4,}\\b")),')
    if not has_nome:
        entries.append('("nome", re.compile(r"\\b[A-Z][a-z]{2,}(?:\\s+[A-Z][a-z]{2,})*\\b")),')
    new_lines, ins = [], False
    for line in lines:
        if not ins and '("misura", re.compile(' in line:
            indent = len(line) - len(line.lstrip())
            for e in entries:
                new_lines.append(" " * indent + e)
            ins = True
        new_lines.append(line)
    if ins:
        lines, modified = new_lines, True
        print("Fix 1 applicato")
    else:
        print("ERRORE Fix 1: riga ('misura') non trovata")

# === FIX 2: fuzzy fallback in _cerca ===
if not has_fuzzy:
    target = None
    for i, line in enumerate(lines):
        if '"[no branch matches %r. Try another word.]"' in line:
            target = i
            break
    if target is None:
        print("ERRORE Fix 2: riga '[no branch matches]' non trovata")
    else:
        ret_ind = len(lines[target]) - len(lines[target].lstrip())
        ifh = None
        for i in range(target - 1, max(target - 12, -1), -1):
            s = lines[i].strip()
            ind = len(lines[i]) - len(lines[i].lstrip())
            if s == "if not hits:" and ind < ret_ind:
                ifh = i
                break
        if ifh is None:
            print("ERRORE Fix 2: 'if not hits:' non trovato. Codice attorno:")
            for i in range(max(0, target - 8), min(len(lines), target + 2)):
                print("%4d|%s" % (i, lines[i]))
        else:
            ind = len(lines[ifh]) - len(lines[ifh].lstrip())
            sp, sp1, sp2, sp3 = " "*ind, " "*(ind+4), " "*(ind+8), " "*(ind+12)
            nb = [
                sp + "if not hits:",
                sp1 + 'alt = re.sub(r"^[a-z]+\\s*[:\\s]\\s*", "", q).strip()',
                sp1 + "if alt and alt != q:",
                sp2 + "return _cerca(tree, session, alt, limit)",
                sp + "if not hits:",
                sp1 + "# Fuzzy fallback: spezza la query in parole e cerca ciascuna (solo foglie)",
                sp1 + 'words = [w for w in re.findall(r"[a-z0-9]{3,}", q) if len(w) >= 3]',
                sp1 + "for w in words[:5]:",
                sp2 + "for k in order:",
                sp3 + "if len(hits) >= limit:",
                sp3 + "    break",
                sp3 + "if any(h[0] == k for h in hits):",
                sp3 + "    continue",
                sp3 + "if keys[k].get(\"children\"):",
                sp3 + "    continue",
                sp3 + "try:",
                sp3 + "    if w in tree.load(session, k).lower():",
                sp3 + "        hits.append((k, False, \"Match fuzzy nel testo\"))",
                sp3 + "except TreeError:",
                sp3 + "    continue",
                sp2 + "if hits:",
                sp2 + "    break",
                sp + "if not hits:",
                sp1 + 'return "[no branch matches %r. Try another word.]" % query, []',
            ]
            lines = lines[:ifh] + nb + lines[target + 1:]
            modified = True
            print("Fix 2 applicato")

# === SALVATAGGIO ===
if modified:
    code = "\n".join(lines)
    try:
        ast.parse(code)
    except SyntaxError as e:
        print("ERRORE SINTASSI, file NON salvato:", e)
        raise SystemExit(1)
    p.write_text(code, encoding="utf-8")
    print("\nPatch B completata e salvata!")
else:
    print("\nNessuna modifica necessaria.")
