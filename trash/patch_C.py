from pathlib import Path
import ast

# =====================================================================
# FIX 1: rami.py - non menzionare "leggi_ramo" che non esiste in chat_full
# =====================================================================
pr = Path("bocconcini/rami.py")
rcode = pr.read_text(encoding="utf-8")

old_spill = '''voce["content"] = ('[ramo %s] %d byte su disco. Apri con leggi_ramo("%s"). %s'
% (ident, len(c.encode("utf-8")), ident, _anteprima(c)))'''

new_spill = '''voce["content"] = ('[contenuto spostato su disco per risparmiare token: %d byte. Anteprima: %s]'
% (len(c.encode("utf-8")), _anteprima(c)))'''

if old_spill in rcode:
    rcode = rcode.replace(old_spill, new_spill)
    pr.write_text(rcode, encoding="utf-8")
    print("✅ Fix 1: rami.py non menziona più 'leggi_ramo'")
else:
    print("ℹ️ Fix 1: rami.py già corretto o formato diverso")

# =====================================================================
# FIX 2: memory.py - aggiungi tool sfoglia_pagina per la paginazione
# =====================================================================
pm = Path("bocconcini/memory.py")
mcode = pm.read_text(encoding="utf-8")

# 2a. Definisci il tool _SFOGLIA dopo _CERCA
sfoglia_tool = '''
_SFOGLIA = {"type": "function", "function": {
    "name": "sfoglia_pagina",
    "description": "Show the next page of branches at the current level. Use when the index says more branches are available.",
    "parameters": {"type": "object", "properties": {
        "offset": {"type": "integer", "description": "the offset value from the index message"}},
    "required": ["offset"]}}}
'''

if "_SFOGLIA" not in mcode:
    anchor_cerca = '_CERCA = {"type": "function"'
    if anchor_cerca in mcode:
        pos = mcode.find(anchor_cerca)
        end_pos = mcode.find("}\n", pos) + 2
        mcode = mcode[:end_pos] + sfoglia_tool + mcode[end_pos:]
        print("✅ Fix 2a: tool _SFOGLIA aggiunto")
    else:
        print("❌ Fix 2a: anchor _CERCA non trovato")
else:
    print("ℹ️ Fix 2a: _SFOGLIA già presente")

# 2b. Gestisci il tool sfoglia_pagina nel loop di naviga
old_tool_dispatch = '''if fname == "cerca_nodo":
    q = str(args.get("query") or args.get("id") or "")
    body, _h = _cerca(tree, session, q, 8)
    meta.setdefault("searches", []).append(q)
    msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": body, "_node": ""})
    continue'''

new_tool_dispatch = '''if fname == "cerca_nodo":
    q = str(args.get("query") or args.get("id") or "")
    body, _h = _cerca(tree, session, q, 8)
    meta.setdefault("searches", []).append(q)
    msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": body, "_node": ""})
    continue
if fname == "sfoglia_pagina":
    off = int(args.get("offset") or 0)
    sub = tree.vista(session, focus, budget_tokens=max(150, budget // 4),
                     chars_per_token=cpt, offset=off)
    meta.setdefault("pages_browsed", []).append(off)
    msgs.append({"role": "tool", "tool_call_id": call.get("id") or "",
                 "content": sub["text"], "_node": ""})
    continue'''

if old_tool_dispatch in mcode and "sfoglia_pagina" not in mcode.split(old_tool_dispatch)[0][-200:]:
    mcode = mcode.replace(old_tool_dispatch, new_tool_dispatch, 1)
    print("✅ Fix 2b: gestione sfoglia_pagina aggiunta a naviga")
else:
    print("ℹ️ Fix 2b: sfoglia_pagina già gestito o formato diverso")

# 2c. Aggiungi _SFOGLIA alla lista dei tool in naviga
old_tools = 'tools_now = None if final else [_LEGGI, _CERCA]'
new_tools = 'tools_now = None if final else [_LEGGI, _CERCA, _SFOGLIA]'

if old_tools in mcode and "_SFOGLIA" not in mcode.split(old_tools)[0][-100:]:
    mcode = mcode.replace(old_tools, new_tools, 1)
    print("✅ Fix 2c: _SFOGLIA aggiunto alla lista dei tool")
else:
    print("ℹ️ Fix 2c: _SFOGLIA già nella lista o formato diverso")

# =====================================================================
# FIX 3: memory.py - disabilita evict sui tool messages (preserva KV cache)
# =====================================================================
old_evict = '''target = None
for i, m in enumerate(msgs):
    if i not in fresh and m.get("role") == "tool" and not m.get("_stub"):
        target = i
        break'''

new_evict = '''target = None
# Disabilitato: evictare i tool messages invalida la KV cache del server.
# Ci affidiamo solo allo spill preventivo in client._spill_if_needed.
# for i, m in enumerate(msgs):
#     if i not in fresh and m.get("role") == "tool" and not m.get("_stub"):
#         target = i
#         break'''

if old_evict in mcode:
    mcode = mcode.replace(old_evict, new_evict, 1)
    print("✅ Fix 3: evict sui tool messages disabilitato (preserva KV cache)")
else:
    print("ℹ️ Fix 3: evict già disabilitato o formato diverso")

# =====================================================================
# Verifica sintassi e salvataggio
# =====================================================================
try:
    ast.parse(mcode)
except SyntaxError as e:
    print("❌ ERRORE SINTASSI in memory.py:", e)
    raise SystemExit(1)

pm.write_text(mcode, encoding="utf-8")
print("\n🎉 Patch C completata!")
