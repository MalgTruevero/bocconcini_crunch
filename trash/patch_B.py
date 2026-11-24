from pathlib import Path
import ast

p = Path("bocconcini/memory.py")
lines = p.read_text(encoding="utf-8").split("\n")

# ============================================================
# FIX 1: Aggiungi nuovi pattern a _FATTO
# ============================================================
new_fatto_entries = [
    '("numero", re.compile(r"\\b\\d{4,}\\b")),',
    '("nome", re.compile(r"\\b[A-Z][a-z]{2,}(?:\\s+[A-Z][a-z]{2,})*\\b")),',
]

inserted_fatto = False
new_lines = []
for line in lines:
    if not inserted_fatto and '("misura", re.compile(' in line:
        indent = len(line) - len(line.lstrip())
        for entry in new_fatto_entries:
            new_lines.append(" " * indent + entry)
        inserted_fatto = True
    new_lines.append(line)

if not inserted_fatto:
    print("ERRORE: riga ('misura') non trovata in _FATTO")
    raise SystemExit(1)

lines = new_lines
print("Fix 1: nuove voci (numero, nome) aggiunte a _FATTO")

# ============================================================
# FIX 2: _cerca con ricerca fuzzy word-level
# ============================================================
target_line_idx = None
for i, line in enumerate(lines):
    if '"[no branch matches %r. Try another word.]"' in line:
        target_line_idx = i
        break

if target_line_idx is None:
    print("ERRORE: riga '[no branch matches]' non trovata in _cerca")
    raise SystemExit(1)

if_not_hits_idx = None
for i in range(target_line_idx - 1, max(target_line_idx - 5, -1), -1):
    stripped = lines[i].strip()
    if stripped == "if not hits:":
        if_not_hits_idx = i
        break
    if stripped:
        break

if if_not_hits_idx is None:
    print("ERRORE: blocco 'if not hits:' non trovato prima del return")
    raise SystemExit(1)

indent = len(lines[if_not_hits_idx]) - len(lines[if_not_hits_idx].lstrip())
indent_str = " " * indent
inner = indent_str + "    "
inner2 = indent_str + "        "
inner3 = indent_str + "            "

fuzzy_lines = [
    indent_str + "if not hits:",
    inner + "# Fuzzy fallback: spezza la query in parole e cerca ciascuna",
    inner + 'words = [w for w in re.findall(r"[a-z0-9]{3,}", q) if len(w) >= 3]',
    inner + "for w in words[:5]:",
    inner2 + "for k in order:",
    inner3 + "if len(hits) >= limit:",
    inner3 + "    break",
    inner3 + "if k in hits:",
    inner3 + "    continue",
    inner3 + "try:",
    inner3 + "    if w in tree.load(session, k).lower():",
    inner3 + "        hits.append(k)",
    inner3 + "except TreeError:",
    inner3 + "    continue",
    inner2 + "if hits:",
    inner2 + "    break",
    inner + "if not hits:",
    inner + '    return "[no branch matches %r. Try another word.]" % query, []',
]

new_lines = lines[:if_not_hits_idx] + fuzzy_lines + lines[target_line_idx + 1:]
lines = new_lines

print("Fix 2: _cerca ora fa ricerca fuzzy word-level")

# ============================================================
# Verifica sintassi e salvataggio
# ============================================================
code = "\n".join(lines)
try:
    ast.parse(code)
except SyntaxError as e:
    print("ERRORE SINTASSI:", e)
    raise SystemExit(1)

p.write_text(code, encoding="utf-8")
print("Patch B completata!")
