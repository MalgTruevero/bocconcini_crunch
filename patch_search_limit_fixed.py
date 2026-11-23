from pathlib import Path
import ast

pm = Path("bocconcini/memory.py")
lines = pm.read_text(encoding="utf-8").split("\n")

print("=== APPLICO PATCH SEARCH LIMIT (VERSIONE CORRETTA) ===\n")

# Trova la riga con meta.setdefault("searches", []).append(q)
target_idx = None
for i, line in enumerate(lines):
    if 'meta.setdefault("searches", []).append(q)' in line:
        target_idx = i
        break

if target_idx is None:
    print("ERRORE: riga target non trovata")
    raise SystemExit(1)

# Calcola l'indentazione della riga target
indent = len(lines[target_idx]) - len(lines[target_idx].lstrip())
sp = " " * indent

print("Riga target trovata alla riga %d" % (target_idx + 1))
print("Indentazione: %d spazi" % indent)
print("Riga originale: %s" % lines[target_idx])

# Costruisci il nuovo blocco con l'indentazione corretta
new_lines = [
    lines[target_idx],  # Mantieni la riga originale
    sp + "consecutive_searches = meta.get('_consecutive_searches', 0) + 1",
    sp + "meta['_consecutive_searches'] = consecutive_searches",
    sp + "if consecutive_searches >= 2:",
    sp + "    body += ('\\n\\n[WARNING: %d searches without reading. Use leggi_nodo on a matching branch.]' % consecutive_searches)",
]

# Sostituisci la riga target con il nuovo blocco
lines = lines[:target_idx] + new_lines + lines[target_idx + 1:]
print("OK 1: blocco consecutivo aggiunto con indentazione corretta")

# Ora trova dove aggiungere il reset su leggi_nodo
# Cerca la riga "if fname not in ('', 'leggi_nodo'):"
reset_idx = None
for i, line in enumerate(lines):
    if 'if fname not in ("", "leggi_nodo"):' in line:
        reset_idx = i
        break

if reset_idx is not None:
    indent_reset = len(lines[reset_idx]) - len(lines[reset_idx].lstrip())
    sp_reset = " " * indent_reset
    
    # Inserisci il blocco di reset prima della riga trovata
    reset_lines = [
        sp_reset + 'if fname in ("leggi_nodo",):',
        sp_reset + "    meta['_consecutive_searches'] = 0  # Reset contatore ricerche consecutive",
        "",
    ]
    lines = lines[:reset_idx] + reset_lines + lines[reset_idx:]
    print("OK 2: reset contatore su leggi_nodo aggiunto")
else:
    print("ATTENZIONE: blocco reset non trovato")

# Verifica sintassi
code = "\n".join(lines)
try:
    ast.parse(code)
    print("\n✓ Sintassi valida")
except SyntaxError as e:
    print("\n✗ ERRORE SINTASSI:", e)
    raise SystemExit(1)

# Salva
pm.write_text(code, encoding="utf-8")
print("✓ File salvato: bocconcini/memory.py")
