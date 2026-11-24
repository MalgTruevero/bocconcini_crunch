p = 'bocconcini/memory.py'
s = open(p, encoding='utf-8').read()
new = open('new_tail.txt', encoding='utf-8').read()
a = '        summary_base = meta_etichetta["summary"]'
b = '    tree.save(sessione, roots)'
assert s.count(a) == 1, s.count(a)
assert s.count(b) == 1, s.count(b)
i, j = s.index(a), s.index(b)
assert i < j
open(p, 'w', encoding='utf-8').write(s[:i] + new + s[j:])
print('spliced')
