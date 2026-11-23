import pathlib, shutil, ast
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
assert "per_msg" not in s, "gia' applicata"
shutil.copy(str(p), str(p) + ".bak7")
a = 'def _msg_tokens(msgs: List[Dict[str, Any]], cpt: float) -> int:'
assert s.count(a) == 1
s = s.replace(a, 'def _msg_tokens(msgs: List[Dict[str, Any]], cpt: float, per_msg: float = 8.0) -> int:', 1)
a = 'return int(sum(len(str(m.get("content") or "")) for m in msgs) / cpt) + 8 * len(msgs)'
assert s.count(a) == 1
s = s.replace(a, 'return int(sum(len(str(m.get("content") or "")) for m in msgs) / cpt + per_msg * len(msgs))', 1)
a = 'def _evict(msgs: List[Dict[str, Any]], budget: int, cpt: float) -> int:'
assert s.count(a) == 1
s = s.replace(a, 'def _evict(msgs: List[Dict[str, Any]], budget: int, cpt: float, per_msg: float = 8.0) -> int:', 1)
a = 'while _msg_tokens(msgs, cpt) > budget:'
assert s.count(a) == 1
s = s.replace(a, 'while _msg_tokens(msgs, cpt, per_msg) > budget:', 1)
a = '    cpt = max(1.0, float(chars_per_token))'
assert s.count(a) == 1
s = s.replace(a, a + '\n    try:\n        ovh = float(client._hw().get("msg_overhead") or 8.0)\n    except Exception:\n        ovh = 8.0', 1)
a = '_evict(msgs, max(200, budget - 256), cpt)'
assert s.count(a) == 1
s = s.replace(a, '_evict(msgs, max(200, budget - 256), cpt, ovh)', 1)
a = '_evict(msgs, budget, cpt)'
assert s.count(a) == 1
s = s.replace(a, '_evict(msgs, budget, cpt, ovh)', 1)
a = '_msg_tokens(msgs, cpt) + int(min(cap'
assert s.count(a) == 1
s = s.replace(a, '_msg_tokens(msgs, cpt, ovh) + int(min(cap', 1)
a = 'pt = _msg_tokens(msgs, cpt) + (256 if tools_now else 0)'
assert s.count(a) == 1
s = s.replace(a, 'pt = _msg_tokens(msgs, cpt, ovh) + (256 if tools_now else 0)', 1)
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("accounting unified")
