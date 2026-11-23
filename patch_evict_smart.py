from pathlib import Path
import ast

pm = Path("bocconcini/memory.py")
code = pm.read_text(encoding="utf-8")

print("=== ISPEZIONE ===")
print("_evict disabilitato:", "while False:" in code)
print("soglia budget-256 presente:", "budget - 256" in code)

modified = False

# FIX 1: riattiva il ciclo di eviction
old_loop = "while False:  # evict disabled: preserve server KV cache"
new_loop = "while _msg_tokens(msgs, cpt, per_msg) > budget:"

if old_loop in code:
    code = code.replace(old_loop, new_loop, 1)
    modified = True
    print("OK 1: ciclo _evict riattivato")
else:
    print("ATTENZIONE 1: ciclo gia' attivo o formato diverso")

# FIX 2: alza la soglia di eviction da budget-256 a budget-150
# (evict meno frequente = KV cache preservata piu' a lungo)
old_thresh = "meta[\"evicted\"] += _evict(msgs, max(200, budget - 256), cpt, ovh, question)"
new_thresh = "meta[\"evicted\"] += _evict(msgs, max(200, budget - 150), cpt, ovh, question)"

if old_thresh in code:
    code = code.replace(old_thresh, new_thresh, 1)
    modified = True
    print("OK 2: soglia eviction alzata (budget-256 -> budget-150)")
else:
    print("ATTENZIONE 2: soglia gia' modificata o formato diverso")

# Verifica sintassi prima di scrivere
if modified:
    try:
        ast.parse(code)
    except SyntaxError as e:
        print("ERRORE SINTASSI, file NON salvato:", e)
        raise SystemExit(1)
    pm.write_text(code, encoding="utf-8")
    print("memory.py salvato")
else:
    print("Nessuna modifica necessaria")
