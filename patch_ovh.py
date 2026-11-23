import pathlib, shutil, ast, re
p = pathlib.Path("bocconcini.py")
s = p.read_text(encoding="utf-8")
assert "schema cost is an ESTIMATE" not in s, "gia' applicata"
shutil.copy(str(p), str(p) + ".bak")
m = re.search(r'^([ \t]*)tt = estimate_tokens\(json\.dumps\(tools, ensure_ascii=False\), "json"\) if tools else 0\n', s, re.M)
assert m, "ancora tt non trovata"
i = m.group(1)
new = (i + "if tools:\n" + i + "    return          # schema cost is an ESTIMATE: learning it as per-message\n" + i + "                    # overhead would count the same error twice\n" + i + "tt = 0\n")
s = s[:m.start()] + new + s[m.end():]
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("overhead no longer learned from tool calls")
