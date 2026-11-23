import time
from bocconcini import LlamaCppClient, get_model_info
from bocconcini.client import subscribe_busy, busy_state, lavoro_atomico
from bocconcini.memory import prepara_albero_ricco, naviga, ask_stepwise

BASE_URL = "http://127.0.0.1:8082"
NEEDLES = [
    ("BFR-7491", "__buffer__", "In Python 3.12 __buffer__ restituisce memoryview o TypeError: codice controllo BFR-7491."),
    ("COR-3182", "StopIteration", "PEP 479 StopIteration in coroutine async -> RuntimeError: codice controllo COR-3182."),
    ("TKN-8824", "COMMENT", "tokenize COMMENT non genera INDENT o DEDENT: codice controllo TKN-8824."),
    ("SLT-5509", "__slots__", "__slots__ senza __dict__ -> AttributeError: codice controllo SLT-5509."),
    ("AST-6237", "type_comments", "ast.parse(..., type_comments=True) PEP 484/526: codice controllo AST-6237."),
    ("TSK-9415", "TaskGroup", "asyncio.TaskGroup cancella fratelli e solleva ExceptionGroup: codice controllo TSK-9415."),
]
SECTIONS = [
    ("Descrittori", "Descrittori __get__, __set__, __delete__ per validazione o calcolo pigro."),
    ("AST", "Analisi statica con ast.parse e ast.walk per funzioni, classi e chiamate."),
    ("Generatori", "Iteratori __iter__/__next__ e generatori con yield e stato locale."),
    ("Concorrenza", "Thread con GIL per CPU-bound e asyncio per coroutine cooperative."),
    ("Tokenize", "Modulo tokenize per token logici/fisici, rientri e stringhe."),
]

def build_doc(target_tokens=20000):
    target_chars = int(target_tokens * 3.2)
    parts, idx, npos = [], 0, 0
    while sum(len(p) for p in parts) < target_chars:
        t, b = SECTIONS[idx % len(SECTIONS)]
        blk = f"## Sez {idx}: {t}\n{b}\ndef fn_{idx}(x): return x + {idx % 9}\n"
        if npos < len(NEEDLES) and idx > 0 and idx % 18 == 0:
            blk += f"Nota: {NEEDLES[npos][2]}\n"
            npos += 1
        parts.append(blk)
        idx += 1
    while npos < len(NEEDLES):
        parts.append(f"## App {npos}\nNota: {NEEDLES[npos][2]}\n")
        npos += 1
    return "\n".join(parts)

def codes_in(txt):
    return [c for c, _, _ in NEEDLES if c in (txt or "")]

def main():
    t0 = time.monotonic()
    unsub = subscribe_busy(lambda ev: print(f"[BUSY {ev.get('event')}] {ev.get('server')}"))
    client = LlamaCppClient(BASE_URL, auto_reduce=True)
    wb = client.working_budget()
    print("INFO:", get_model_info(BASE_URL), "WB:", wb, "STATS:", client.stats())

    doc = build_doc(20000)
    print("DOC chars:", len(doc), "est_tok:", len(doc)//3)

    with lavoro_atomico(BASE_URL):
        tree, sess = prepara_albero_ricco(doc, "test_matriosca_lib", max_chars=1600)

    nodes = tree.get("nodes", {}) if isinstance(tree, dict) else {}
    print("TREE keys:", list(tree.keys()) if isinstance(tree, dict) else type(tree), "nodes:", len(nodes))
    sample_id = next(iter(nodes), None)
    if sample_id:
        print("SAMPLE NODE:", sample_id, list(nodes[sample_id].keys()) if isinstance(nodes[sample_id], dict) else type(nodes[sample_id]))

    for code, kw, _ in NEEDLES:
        hits = [nid for nid, nd in nodes.items() if kw in str(nd)]
        print(f"  AGO {code} ({kw}) -> hits={len(hits)} {hits[:3]}")

    q_nav = "Cerca e trova i codici XXX-0000 relativi a: __buffer__, StopIteration, COMMENT, __slots__, type_comments, TaskGroup."
    r1 = naviga(client, tree, sess, q_nav, budget_tokens=min(1900, wb), max_hops=8, max_tokens=220)
    c1 = codes_in(r1.get("text"))
    print("1. NAVIGA:", len(c1), c1, r1.get("meta"), "\nTEXT1:", r1.get("text"))

    kws = [kw for _, kw, _ in NEEDLES]
    r2 = ask_stepwise(client, doc, "Estrai il codice XXX-0000 collegato alla parola chiave.", targets=kws, max_tokens=60, window=240)
    f_txt = " ".join(str(x) for x in (r2.get("meta", {}).get("findings") or []))
    c2_f = codes_in(f_txt)
    c2_t = codes_in(r2.get("text"))
    print("2. STEPWISE findings:", len(c2_f), c2_f, "| text:", len(c2_t), c2_t, "| meta:", r2.get("meta"), "\nTEXT2:", r2.get("text"))

    print("BUSY_END:", busy_state(BASE_URL), "ELAPSED_S:", round(time.monotonic() - t0, 1))
    unsub()

if __name__ == "__main__":
    main()
