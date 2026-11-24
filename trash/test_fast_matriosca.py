import time
from bocconcini import LlamaCppClient
from bocconcini.client import lavoro_atomico
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

def build_doc(target_tokens=3000):
    target_chars = int(target_tokens * 3.2)
    parts, idx, npos = [], 0, 0
    while sum(len(p) for p in parts) < target_chars:
        t, b = SECTIONS[idx % len(SECTIONS)]
        blk = f"## Sez {idx}: {t}\n{b}\ndef fn_{idx}(x): return x + {idx % 9}\n"
        if npos < len(NEEDLES) and idx > 0 and idx % 6 == 0:
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

t0 = time.monotonic()
client = LlamaCppClient(BASE_URL, auto_reduce=True)
wb = client.working_budget()
doc = build_doc(3000)
with lavoro_atomico(BASE_URL):
    tree, sess = prepara_albero_ricco(doc, "fast_matriosca", max_chars=1200)

q_nav = "Trova e elenca tutti i codici di controllo (formato LETTERE-NUMERO) associati a: __buffer__, StopIteration, COMMENT, __slots__, type_comments, TaskGroup. Apri i nodi rilevanti per verificarli."
r1 = naviga(client, tree, sess, q_nav, budget_tokens=min(1900, wb), max_hops=10, max_tokens=450)
print("NAVIGA:", codes_in(r1.get("text")), "read:", r1.get("meta", {}).get("nodes_read"), "evicted:", r1.get("meta", {}).get("evicted"))
print("TEXT1:", r1.get("text"))

kws = [kw for _, kw, _ in NEEDLES]
r2 = ask_stepwise(client, doc, "Quale codice di controllo (es. ABC-1234) compare vicino a questa parola chiave nel testo?", targets=kws, max_tokens=80, window=400)
f_txt = " ".join(str(x) for x in (r2.get("meta", {}).get("findings") or []))
print("STEPWISE findings:", codes_in(f_txt), "| text:", codes_in(r2.get("text")), "| meta_found:", r2.get("meta", {}).get("found_count"))
print("TEXT2:", r2.get("text"))
print("ELAPSED_S:", round(time.monotonic() - t0, 1))
