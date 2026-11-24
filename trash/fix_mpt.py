p = 'bocconcini/memory.py'
s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:45], s.count(a))
    s = s.replace(a, b)
rep("max_per_tipo: int = 100", "max_per_tipo: Optional[int] = None")
rep("        max_per_tipo: quanti fatti estrarre per tipo (default 100 invece di 40)",
    "        max_per_tipo: per-type extraction cap. None (default) extracts every\n"
    "            fact; a number truncates each type globally, dropping facts that\n"
    "            appear late in the document.")
open(p, 'w', encoding='utf-8').write(s)
print('ok')
