from pathlib import Path
import ast, re

# =====================================================================
# FIX 1: rami.py - sostituisci qualsiasi riferimento a leggi_ramo
# =====================================================================
pr = Path("bocconcini/rami.py")
rcode = pr.read_text(encoding="utf-8")

if "leggi_ramo" in rcode:
    # Sostituisci la riga che contiene leggi_ramo
    lines = rcode.split("\n")
    new_lines = []
    for line in lines:
        if "leggi_ramo" in line:
            # Sostituisci con un messaggio generico senza riferimento a tool inesistenti
            line = re.sub(
                r"'?\[ramo %s\] %d byte su disco\. Apri con leggi_ramo\(\"%s\"\)\. %s'?",
                "'[contenuto spostato su disco per risparmiare token: %d byte. Anteprima: %s]' % (len(c.encode('utf-8')), _anteprima(c))",
                line
            )
            # Se la riga è ancora complessa, sostituisci direttamente
            if "leggi_ramo" in line:
                line = "voce['content'] = ('[contenuto spostato su disco: %d byte. Anteprima: %s]'\n% (len(c.encode('utf-8')), _anteprima(c)))"
        new_lines.append(line)
    rcode = "\n".join(new_lines)
    
    # Se la sostituzione sopra non ha funzionato, fai una sostituzione diretta
    if "leggi_ramo" in rcode:
        rcode = re.sub(
            r"voce\[\"content\"\]\s*=\s*\('\[ramo %s\].*?%s\)'\s*%\s*\(ident,\s*len\(c\.encode\(\"utf-8\"\)\),\s*ident,\s*_anteprima\(c\)\)",
            "voce['content'] = ('[contenuto spostato su disco: %d byte. Anteprima: %s]'\n% (len(c.encode('utf-8')), _anteprima(c)))",
            rcode,
            flags=re.DOTALL
        )
    
    if "leggi_ramo" not in rcode:
        pr.write_text(rcode, encoding="utf-8")
        print("✅ Fix 1: rami.py corretto (leggi_ramo rimosso)")
    else:
        print("⚠️ Fix 1: leggi_ramo ancora presente, richiede intervento manuale")
        for i, line in enumerate(rcode.split("\n")):
            if "leggi_ramo" in line:
                print("  riga %d: %s" % (i, line.strip()))
else:
    print("ℹ️ Fix 1: rami.py già corretto")

# =====================================================================
# FIX 2b: aggiungi gestione sfoglia_pagina nel loop di naviga
# =====================================================================
pm = Path("bocconcini/memory.py")
mcode = pm.read_text(encoding="utf-8")

if "sfoglia_pagina" not in mcode.split("def naviga")[1] if "def naviga" in mcode else True:
    # Cerca il blocco di gestione cerca_nodo e aggiungi sfoglia_pagina dopo
    pattern = r'(if fname == "cerca_nodo":.*?continue\n)'
    match = re.search(pattern, mcode, re.DOTALL)
    if match:
        insert_pos = match.end()
        sfoglia_code = '''if fname == "sfoglia_pagina":
    off = int(args.get("offset") or 0)
    sub = tree.vista(session, focus, budget_tokens=max(150, budget // 4),
                     chars_per_token=cpt, offset=off)
    meta.setdefault("pages_browsed", []).append(off)
    msgs.append({"role": "tool", "tool_call_id": call.get("id") or "",
                 "content": sub["text"], "_node": ""})
    continue
'''
        # Determina l'indentazione dalla riga precedente
        prev_line = mcode[:insert_pos].split("\n")[-2] if len(mcode[:insert_pos].split("\n")) > 1 else ""
        indent = len(prev_line) - len(prev_line.lstrip())
        sfoglia_code = "\n".join(" " * indent + line for line in sfoglia_code.split("\n"))
        mcode = mcode[:insert_pos] + "\n" + sfoglia_code + mcode[insert_pos:]
        print("✅ Fix 2b: gestione sfoglia_pagina aggiunta a naviga")
    else:
        print("⚠️ Fix 2b: blocco cerca_nodo non trovato, richiede intervento manuale")
else:
    print("ℹ️ Fix 2b: sfoglia_pagina già gestito")

# =====================================================================
# FIX 3: disabilita evict sui tool messages
# =====================================================================
if "Disabilitato: evictare i tool messages" not in mcode:
    # Cerca il blocco target = None ... for i, m in enumerate(msgs): ... target = i ... break
    pattern = r'(target = None\n\s+for i, m in enumerate\(msgs\):\n\s+if i not in fresh and m\.get\("role"\) == "tool" and not m\.get\("_stub"\):\n\s+target = i\n\s+break)'
    match = re.search(pattern, mcode)
    if match:
        original = match.group(1)
        commented = "\n".join("# " + line for line in original.split("\n"))
        comment_header = "# Disabilitato: evictare i tool messages invalida la KV cache del server.\n# Ci affidiamo solo allo spill preventivo in client._spill_if_needed.\n"
        mcode = mcode.replace(original, comment_header + commented, 1)
        print("✅ Fix 3: evict sui tool messages disabilitato")
    else:
        print("⚠️ Fix 3: blocco evict non trovato, richiede intervento manuale")
else:
    print("ℹ️ Fix 3: evict già disabilitato")

# =====================================================================
# Verifica sintassi e salvataggio
# =====================================================================
try:
    ast.parse(mcode)
except SyntaxError as e:
    print("❌ ERRORE SINTASSI in memory.py:", e)
    raise SystemExit(1)

pm.write_text(mcode, encoding="utf-8")
print("\n🎉 Patch C2 completata!")
