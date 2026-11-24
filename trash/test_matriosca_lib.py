import json
import os
import subprocess
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

PY_TEMPLATES = [
    (
        "Descrittori",
        "class ValidatedField_{i}:\n"
        "    def __init__(self, bound={b}): self.bound = bound\n"
        "    def __get__(self, obj, cls=None): return self if obj is None else obj.__dict__.get('v_{i}', self.bound)\n"
        "    def __set__(self, obj, val):\n"
        "        if val < 0 or val > self.bound * 10: raise ValueError('out_of_range_{i}')\n"
        "        obj.__dict__['v_{i}'] = val\n"
    ),
    (
        "AST_Walker",
        "import ast\n"
        "def scan_module_{i}(src: str) -> dict:\n"
        "    tree = ast.parse(src)\n"
        "    calls = [n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]\n"
        "    return {{'chunk': {i}, 'count': len(calls), 'limit': {b}, 'sample': calls[:3]}}\n"
    ),
    (
        "Generatori_State",
        "def stream_window_{i}(items, width={b}):\n"
        "    buf = []\n"
        "    for idx, x in enumerate(items):\n"
        "        buf.append((idx, x))\n"
        "        if len(buf) >= width:\n"
        "            yield tuple(buf)\n"
        "            buf.pop(0)\n"
    ),
    (
        "Async_Worker",
        "import asyncio\n"
        "async def fetch_batch_{i}(sem, urls):\n"
        "    async with sem:\n"
        "        await asyncio.sleep(0.001 * ({b} + 1))\n"
        "        return [{{'u': u, 'shard': {i}, 'ok': True}} for u in urls]\n"
    ),
    (
        "Tokenize_Filter",
        "import io, tokenize\n"
        "def strip_tokens_{i}(code: str):\n"
        "    out = []\n"
        "    for tok in tokenize.generate_tokens(io.StringIO(code).readline):\n"
        "        if tok.type not in (tokenize.NL, tokenize.ENCODING):\n"
        "            out.append((tok.type, tok.string, {i}))\n"
        "    return out[:{b}]\n"
    ),
]


def json_noise(idx: int) -> str:
    payload = {
        "worker_id": f"termux-node-{idx:04d}",
        "shard": idx % 16,
        "metrics": {
            "ctx_window": 4096,
            "kv_cache_mb": round(128.4 + (idx * 3.7) % 512, 2),
            "thermal_zone": f"tz_{idx % 5}",
            "retries": [idx % 3, (idx + 1) % 4, (idx + 2) % 5],
        },
        "routes": [
            {"path": f"/v1/chunk/{idx}/parse", "timeout_ms": 1500 + (idx % 7) * 250, "strict": bool(idx % 2)},
            {"path": f"/v1/chunk/{idx}/index", "timeout_ms": 3000 + (idx % 5) * 400, "strict": not bool(idx % 2)},
        ],
    }
    return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"


def sys_telemetry() -> str:
    mem_avail_mb = -1
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    mem_avail_mb = int(line.split()[1]) // 1024
                    break
    except Exception:
        pass

    llama_pids = []
    try:
        out = subprocess.check_output(["ps", "-A", "-o", "PID,RSS,ARGS"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if "llama" in line and "python" not in line:
                parts = line.split(None, 2)
                if len(parts) >= 2:
                    rss_mb = int(parts[1]) // 1024 if parts[1].isdigit() else -1
                    llama_pids.append(f"pid={parts[0]}(rss={rss_mb}MB)")
    except Exception:
        pass

    return f"MemAvail={mem_avail_mb}MB | llama={llama_pids or 'NOT_FOUND'}"


def build_doc(target_tokens: int) -> str:
    # Con mix Python + JSON la densita media e' ~2.8-3.0 char/token: teniamo 3.1 per non stare sotto il 10x
    target_chars = int(target_tokens * 3.1)
    parts, idx, npos = [], 0, 0
    total_chars = 0

    # Distribuisce gli aghi su tutto l'arco del documento (dal 10% al 95%)
    needle_checkpoints = [int(target_chars * p) for p in (0.10, 0.27, 0.44, 0.61, 0.78, 0.93)]

    while total_chars < target_chars:
        title, tmpl = PY_TEMPLATES[idx % len(PY_TEMPLATES)]
        py_blk = tmpl.format(i=idx, b=(idx % 11) + 2)
        js_blk = json_noise(idx)
        blk = f"## Modulo {idx}: {title}\n```python\n{py_blk}```\n{js_blk}\n"

        if npos < len(NEEDLES) and total_chars >= needle_checkpoints[npos]:
            blk += f"> SPEC_NOTE [{idx}]: {NEEDLES[npos][2]}\n"
            npos += 1

        parts.append(blk)
        total_chars += len(blk) + 1
        idx += 1

    while npos < len(NEEDLES):
        parts.append(f"## Appendice {npos}\n> SPEC_NOTE [END]: {NEEDLES[npos][2]}\n")
        npos += 1

    return "\n".join(parts)


def codes_in(txt: str) -> list[str]:
    return [c for c, _, _ in NEEDLES if c in (txt or "")]


def main():
    t0 = time.monotonic()
    busy_events = []
    unsub = subscribe_busy(lambda ev: busy_events.append((round(time.monotonic() - t0, 1), ev.get("event"), ev.get("server"))))

    print("BOOT TELEMETRY:", sys_telemetry())
    client = LlamaCppClient(BASE_URL, auto_reduce=True)
    wb = client.working_budget()
    info = get_model_info(BASE_URL)
    print("MODEL INFO:", info)
    print("WORKING BUDGET:", wb, "| INIT STATS:", client.stats())

    # 10x reale della finestra utile
    target_tokens = wb * 10
    doc = build_doc(target_tokens)
    est_tokens = len(doc) // 3
    print(f"DOC BUILT: chars={len(doc)} | target_tok={target_tokens} (10x WB) | est_tok~{est_tokens}")

    # Verifica integrita aghi nel testo grezzo
    missing_raw = [c for c, _, _ in NEEDLES if c not in doc]
    assert not missing_raw, f"Aghi mancanti nel doc grezzo: {missing_raw}"

    # FASE 1: Costruzione albero
    t_tree0 = time.monotonic()
    with lavoro_atomico(BASE_URL):
        tree, sess = prepara_albero_ricco(doc, "test_matriosca_10x", max_chars=1600)
    t_tree = round(time.monotonic() - t_tree0, 1)

    nodes = tree.get("nodes", {}) if isinstance(tree, dict) else {}
    print(f"\n[FASE 1 - TREE] time={t_tree}s | nodes={len(nodes)} | {sys_telemetry()}")
    for code, kw, _ in NEEDLES:
        in_nodes = [nid for nid, nd in nodes.items() if code in str(nd) or kw in str(nd)]
        print(f"  INDEX CHECK {code} ({kw}): node_hits={len(in_nodes)} {in_nodes[:2]}")

    # FASE 2A: Naviga su SINGOLO ago profondo (AST-6237 al 78% del doc) senza dargli 6 target insieme
    t_nav1_0 = time.monotonic()
    q_single = "Qual e' il codice controllo XXX-0000 associato a type_comments e ast.parse?"
    r_single = naviga(client, tree, sess, q_single, budget_tokens=min(1900, wb), max_hops=6)
    t_nav1 = round(time.monotonic() - t_nav1_0, 1)
    c_single = codes_in(r_single.get("text"))
    print(f"\n[FASE 2A - NAVIGA SINGLE] time={t_nav1}s | found={c_single} (atteso: ['AST-6237']) | meta={r_single.get('meta')}")
    print("  TEXT_SINGLE:", r_single.get("text"))

    # FASE 2B: Naviga CUMULATIVA su tutti e 6 gli aghi
    t_nav6_0 = time.monotonic()
    q_multi = (
        "Estrai tutti i 6 codici controllo formato XXX-0000 associati a: "
        "__buffer__, StopIteration, COMMENT, __slots__, type_comments, TaskGroup."
    )
    r_multi = naviga(client, tree, sess, q_multi, budget_tokens=min(1900, wb), max_hops=10)
    t_nav6 = round(time.monotonic() - t_nav6_0, 1)
    c_multi = codes_in(r_multi.get("text"))
    print(f"\n[FASE 2B - NAVIGA 6-NEEDLES] time={t_nav6}s | found={len(c_multi)}/6 {c_multi} | meta={r_multi.get('meta')}")
    print("  TEXT_MULTI:", r_multi.get("text"))

    # FASE 3: Stepwise mirato sui 6 target
    t_sw0 = time.monotonic()
    kws = [kw for _, kw, _ in NEEDLES]
    r_sw = ask_stepwise(
        client,
        doc,
        "Estrai il codice controllo XXX-0000 collegato alla parola chiave.",
        targets=kws,
        max_tokens=60,
        window=280,
    )
    t_sw = round(time.monotonic() - t_sw0, 1)
    f_txt = " ".join(str(x) for x in (r_sw.get("meta", {}).get("findings") or []))
    c_sw_f = codes_in(f_txt)
    c_sw_t = codes_in(r_sw.get("text"))
    print(f"\n[FASE 3 - STEPWISE] time={t_sw}s | findings={len(c_sw_f)}/6 {c_sw_f} | text={len(c_sw_t)}/6 {c_sw_t} | meta={r_sw.get('meta')}")
    print("  TEXT_STEPWISE:", r_sw.get("text"))

    print("\n=== RIEPILOGO STRESS TEST ===")
    print("END TELEMETRY:", sys_telemetry())
    print("BUSY_END:", busy_state(BASE_URL), "| BUSY_EVENTS_COUNT:", len(busy_events))
    print("CLIENT STATS:", client.stats())
    print(f"TEMPI (s): tree={t_tree} | nav_single={t_nav1} | nav_6={t_nav6} | stepwise={t_sw} | TOT={round(time.monotonic() - t0, 1)}")
    unsub()


if __name__ == "__main__":
    main()
