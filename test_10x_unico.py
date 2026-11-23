import os, time
from bocconcini import LlamaCppClient, get_model_info
from bocconcini.client import subscribe_busy, busy_state, lavoro_atomico
from bocconcini.client import SystemTemperature, _thermal_scale
from bocconcini.memory import prepara_albero_ricco, naviga, ask_stepwise

BASE_URL = "http://127.0.0.1:8082"
NEEDLES = [
    ("BFR-7491", "Python 3.12 __buffer__ memoryview o TypeError: codice controllo BFR-7491."),
    ("COR-3182", "PEP 479 StopIteration in coroutine async -> RuntimeError: codice controllo COR-3182."),
    ("TKN-8824", "tokenize COMMENT non genera INDENT/DEDENT: codice controllo TKN-8824."),
    ("SLT-5509", "__slots__ senza __dict__ -> AttributeError: codice controllo SLT-5509."),
    ("AST-6237", "ast.parse(..., type_comments=True) PEP 484/526: codice controllo AST-6237."),
    ("TSK-9415", "asyncio.TaskGroup cancella fratelli e alza ExceptionGroup: codice controllo TSK-9415."),
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
            blk += f"Nota: {NEEDLES[npos][1]}\n"
            npos += 1
        parts.append(blk)
        idx += 1
    while npos < len(NEEDLES):
        parts.append(f"## App {npos}\nNota: {NEEDLES[npos][1]}\n")
        npos += 1
    return "\n".join(parts)

def found(txt):
    return [c for c, _ in NEEDLES if c in (txt or "")]

def main():
    os.environ["BOCCONCINI_SPILL_CHARS"] = "400"
    t0_all = time.monotonic()
    unsub = subscribe_busy(lambda ev: print(f"[BUSY {ev.get('event')}] {ev.get('server')}"))
    temp = SystemTemperature()()
    scale = _thermal_scale(lambda: temp)
    client = LlamaCppClient(BASE_URL, auto_reduce=True, temperature_provider=lambda: temp)
    print("SETUP:", get_model_info(BASE_URL), client.stats(), "budget:", client.working_budget(), "temp:", temp, "scale:", scale)
    doc = build_doc(20000)
    print("DOC chars:", len(doc), "est_tok:", len(doc)//3)
    with lavoro_atomico(BASE_URL):
        tree, sess = prepara_albero_ricco(doc, "test_10x_unico", max_chars=1600)
    r1 = naviga(client, tree, sess, "Trova i 6 codici XXX-0000: buffer, StopIteration, COMMENT, slots, ast.parse, TaskGroup.", budget_tokens=min(1800, client.working_budget()), max_hops=6, max_tokens=220)
    print("1. NAVIGA:", len(found(r1.get("text"))), found(r1.get("text")), r1.get("meta"), r1.get("text"))
    r2 = ask_stepwise(client, doc, "Elenca i 6 codici.", targets=[c for c, _ in NEEDLES], max_tokens=60, window=220)
    print("2. STEPWISE:", len(found(r2.get("text"))), found(r2.get("text")), r2.get("meta"), r2.get("text"))
    try:
        r3 = client.chat_full(prompt="Riassumi in 5 punti e indica codici XXX-0000:\n\n" + doc, system="Sintetico e preciso.", max_tokens=200, auto_reduce=True)
        print("3. CHAT_FULL:", len(found(r3.text)), found(r3.text), "spill:", r3.spill_path, {k: v for k, v in r3.meta.items() if k != "raw_start"}, r3.text)
    except Exception as e:
        print("3. ERRORE:", type(e).__name__, getattr(e, "kind", ""), e)
    print("BUSY_NOW:", busy_state(BASE_URL), "TOT_S:", round(time.monotonic() - t0_all, 1))
    unsub()

if __name__ == "__main__":
    main()
