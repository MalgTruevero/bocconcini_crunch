from pathlib import Path
import ast

pm = Path("bocconcini/memory.py")
code = pm.read_text(encoding="utf-8")

# Cerca il blocco dove viene gestito cerca_nodo nel loop di naviga
# Aggiungiamo un contatore per ricerche consecutive
old_dispatch = '''if fname == "cerca_nodo":
    q = str(args.get("query") or args.get("id") or "")
    body, _h = _cerca(tree, session, q, 8)
    meta.setdefault("searches", []).append(q)
    msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": body, "_node": ""})
    continue'''

new_dispatch = '''if fname == "cerca_nodo":
    q = str(args.get("query") or args.get("id") or "")
    body, _h = _cerca(tree, session, q, 8)
    meta.setdefault("searches", []).append(q)
    
    # Traccia ricerche consecutive senza letture
    consecutive_searches = meta.get("_consecutive_searches", 0) + 1
    meta["_consecutive_searches"] = consecutive_searches
    
    # Dopo 2 ricerche consecutive, avvisa il modello di leggere un nodo
    if consecutive_searches >= 2:
        body += ("\\n\\n[WARNING: You have done %d searches without reading any node. "
                 "Use leggi_nodo on one of the matching branches above before searching again.]"
                 % consecutive_searches)
    
    msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": body, "_node": ""})
    continue'''

if old_dispatch in code:
    code = code.replace(old_dispatch, new_dispatch, 1)
    print("OK 1: limite ricerche consecutive aggiunto")
else:
    print("ATTENZIONE: blocco cerca_nodo non trovato nel formato atteso")
    # Prova formato alternativo
    if 'if fname == "cerca_nodo":' in code and '_consecutive_searches' not in code:
        print("  Cerco formato alternativo...")
        # Inserisci dopo la riga del meta searches
        old_line = 'meta.setdefault("searches", []).append(q)'
        new_line = '''meta.setdefault("searches", []).append(q)
    consecutive_searches = meta.get("_consecutive_searches", 0) + 1
    meta["_consecutive_searches"] = consecutive_searches
    if consecutive_searches >= 2:
        body += ("\\\\n\\\\n[WARNING: %d searches without reading. Use leggi_nodo on a matching branch.]" % consecutive_searches)'''
        if old_line in code:
            code = code.replace(old_line, new_line, 1)
            print("OK 1 (alternativo): limite ricerche consecutive aggiunto")
        else:
            print("ERRORE: impossibile trovare il punto di inserimento")
            raise SystemExit(1)

# Resetta il contatore quando il modello legge un nodo
old_read = '''if fname not in ("", "leggi_nodo"):'''
new_read = '''if fname in ("leggi_nodo",):
    meta["_consecutive_searches"] = 0  # Reset contatore ricerche consecutive

if fname not in ("", "leggi_nodo"):'''

if old_read in code and '_consecutive_searches' not in code.split(old_read)[0][-200:]:
    code = code.replace(old_read, new_read, 1)
    print("OK 2: reset contatore su leggi_nodo aggiunto")
else:
    print("ATTENZIONE 2: blocco leggi_nodo non trovato o gia' modificato")

try:
    ast.parse(code)
except SyntaxError as e:
    print("ERRORE SINTASSI:", e)
    raise SystemExit(1)

pm.write_text(code, encoding="utf-8")
print("Patch search_limit applicata")
