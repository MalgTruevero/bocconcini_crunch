from pathlib import Path
import ast

pm = Path("bocconcini/memory.py")
code = pm.read_text(encoding="utf-8")
lines = code.split("\n")

print("=== DIAGNOSI MEMORY.PY ===")
print("_SFOGLIA definito:", "_SFOGLIA" in code)
print("_SFOGLIA in tools_now:", "_SFOGLIA" in code.split("tools_now")[1][:80] if "tools_now" in code else False)
print("handler sfoglia_pagina:", 'if fname == "sfoglia_pagina"' in code)
print("evict disabilitato:", "while False" in code)
print("totale righe:", len(lines))

modified = False

# ============================================================
# FIX A: aggiungi handler sfoglia_pagina nel dispatch dei tool
# ============================================================
if 'if fname == "sfoglia_pagina"' not in code:
    insert_idx = None
    cerca_indent = ""
    in_cerca = False
    for i, line in enumerate(lines):
        if 'if fname == "cerca_nodo":' in line:
            in_cerca = True
            cerca_indent = line[:len(line) - len(line.lstrip())]
        elif in_cerca and line.strip() == "continue":
            insert_idx = i + 1
            break

    if insert_idx is not None:
        sp = cerca_indent
        handler = [
            sp + 'if fname == "sfoglia_pagina":',
            sp + '    off = int(args.get("offset") or 0)',
            sp + '    sub = tree.vista(session, focus, budget_tokens=max(150, budget // 4), chars_per_token=cpt, offset=off)',
            sp + '    meta.setdefault("pages_browsed", []).append(off)',
            sp + '    msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": sub["text"], "_node": ""})',
            sp + '    continue',
        ]
        lines = lines[:insert_idx] + handler + lines[insert_idx:]
        modified = True
        print("✅ Handler sfoglia_pagina aggiunto alla riga", insert_idx)
    else:
        print("❌ Impossibile trovare il punto di inserimento (cerca_nodo/continue)")

# ============================================================
# FIX B: disabilita evict per preservare la KV cache
# ============================================================
if "while False" not in code:
    for i, line in enumerate(lines):
        if "while _msg_tokens(msgs, cpt, per_msg) > budget:" in line:
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = indent + "while False:  # evict disabled: preserve server KV cache"
            modified = True
            print("✅ Evict disabilitato alla riga", i)
            break
    else:
        print("⚠️  Blocco evict non trovato (forse già disabilitato?)")

# ============================================================
# Verifica e salvataggio
# ============================================================
if modified:
    new_code = "\n".join(lines)
    try:
        ast.parse(new_code)
    except SyntaxError as e:
        print("❌ ERRORE SINTASSI, file NON salvato:", e)
        print("   Riga problematica:", e.lineno)
        if e.lineno and 0 < e.lineno <= len(lines):
            start = max(0, e.lineno - 3)
            end = min(len(lines), e.lineno + 3)
            for j in range(start, end):
                marker = ">>>" if j == e.lineno - 1 else "   "
                print("%s %4d: %s" % (marker, j + 1, lines[j]))
        raise SystemExit(1)
    pm.write_text(new_code, encoding="utf-8")
    print("✅ memory.py salvato correttamente")
else:
    print("ℹ️  Nessuna modifica necessaria")
