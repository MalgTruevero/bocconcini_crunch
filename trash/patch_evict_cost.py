from pathlib import Path
import ast

p = Path("bocconcini/memory.py")
s = p.read_text(encoding="utf-8")
orig = s

repls = [
    (
        'def _evict(msgs: List[Dict[str, Any]], budget: int, cpt: float, per_msg: float = 8.0, question: str = "") -> int:',
        'def _evict(msgs: List[Dict[str, Any]], budget: int, cpt: float, per_msg: float = 8.0, question: str = "", cost=None) -> int:'
    ),
    (
        'while _msg_tokens(msgs, cpt, per_msg) > budget:',
        'while (cost(msgs) if cost is not None else _msg_tokens(msgs, cpt, per_msg)) > budget:'
    ),
    (
        'meta["evicted"] += _evict(msgs, max(200, budget - 150), cpt, ovh, question)',
        'meta["evicted"] += _evict(msgs, max(200, budget - 150), cpt, ovh, question, cost=lambda ms: client._prompt_tokens(ms, client._tools_tokens(tools_now)))'
    ),
    (
        'meta["evicted"] += _evict(msgs, budget, cpt, ovh, question)',
        'meta["evicted"] += _evict(msgs, budget, cpt, ovh, question, cost=lambda ms: client._prompt_tokens(ms, client._tools_tokens(tools_now)))'
    ),
]

for old, new in repls:
    if old not in s:
        print("MISS:", old[:80])
        raise SystemExit(1)
    s = s.replace(old, new, 1)

ast.parse(s)
p.with_name(p.name + ".bak_evict_cost").write_text(orig, encoding="utf-8")
p.write_text(s, encoding="utf-8")
print("OK: _evict ora usa il costo reale del prompt quando chiamato da naviga")
