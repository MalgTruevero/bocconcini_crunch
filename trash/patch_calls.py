import pathlib, shutil, ast, re
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
assert "max_calls" not in s, "gia' applicata"
shutil.copy(str(p), str(p) + ".bak8")
def splice(pat, tpl):
    global s
    m = re.search(pat, s, re.M)
    assert m, "ancora non trovata"
    base = m.group(1)
    rows = []
    for ln in pathlib.Path(tpl).read_text(encoding="utf-8").splitlines():
        if not ln.startswith("@"):
            rows.append(ln)
            continue
        k = len(ln) - len(ln.lstrip("@")) - 1
        rows.append(base + "    " * k + ln.lstrip("@"))
    s = s[:m.start()] + "\n".join(rows) + "\n" + s[m.end():]
a = "temperature: float = 0.2, require_read: bool = True) -> Dict[str, Any]:"
assert s.count(a) == 1
s = s.replace(a, "temperature: float = 0.2, require_read: bool = True, max_calls: int = 2) -> Dict[str, Any]:", 1)
a = "for call in r.tool_calls:"
assert s.count(a) == 1
s = s.replace(a, "for call in calls:", 1)
splice(r'^([ \t]*)msgs\.append\(\{"role": "assistant", "content": r\.text or "", "tool_calls": r\.tool_calls\}\)\n', "calls_new.txt")
splice(r'^([ \t]*)final = turn >= hops\n', "notice_new.txt")
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("calls capped at 2 per turn")
