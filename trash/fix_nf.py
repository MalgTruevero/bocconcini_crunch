p = 'bocconcini/memory.py'
s = open(p, encoding='utf-8').read()
a = 'for f in trova_fatti(full))[:180]'
assert s.count(a) == 1, s.count(a)
open(p, 'w', encoding='utf-8').write(s.replace(a, 'for f in trova_fatti(full))'))
print('ok')
