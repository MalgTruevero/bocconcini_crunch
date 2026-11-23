import pathlib, shutil, ast, re
p = pathlib.Path("bocconcini_tree.py")
s = p.read_text(encoding="utf-8")
assert "_facts" not in s, "gia' applicata"
shutil.copy(str(p), str(p) + ".bak9")
m = re.search(r'^([ \t]*)msgs\[target\]\["content"\] = \("\[ramo %s rimosso[^\n]*\n[ \t]*"disco,[^\n]*\n', s, re.M)
assert m, "ancora stub non trovata"
i = m.group(1)
new = (i + 'kept = str(msgs[target].get("_facts") or "")\n'
       + i + 'keep = (" facts found -> " + kept + ".") if kept else ""\n'
       + i + 'msgs[target]["content"] = ("[branch %s evicted from context.%s Text stays on disk; "\n'
       + i + '                           "ask leggi_nodo for %s again]" % (nid, keep, nid))\n')
s = s[:m.start()] + new + s[m.end():]
m = re.search(r'^([ \t]*)nid = str\(args\.get\("id"\) or ""\)\n', s, re.M)
assert m, "ancora nid non trovata"
s = s[:m.end()] + m.group(1) + 'nf = ""\n' + s[m.end():]
m = re.search(r'^([ \t]*)body = full\n', s, re.M)
assert m, "ancora body non trovata"
s = s[:m.end()] + m.group(1) + 'nf = ", ".join("%s:%s" % (f["tipo"], f["valore"]) for f in trova_fatti(full, max_per_tipo=6))[:180]\n' + s[m.end():]
a = '"content": body, "_node": nid})'
assert s.count(a) == 1, "ancora append non trovata"
s = s.replace(a, '"content": body, "_node": nid, "_facts": nf})', 1)
ast.parse(s)
p.write_text(s, encoding="utf-8")
print("eviction keeps the facts")
