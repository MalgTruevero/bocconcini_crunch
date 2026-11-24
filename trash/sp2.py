p = 'bocconcini/memory.py'
lines = open(p, encoding='utf-8').read().splitlines(True)
new = open('ev.txt', encoding='utf-8').read()
assert 'parts = re.split' in lines[355], lines[355]
assert '[:180]' in lines[356], lines[356]
open(p, 'w', encoding='utf-8').write(''.join(lines[:355]) + new + ''.join(lines[357:]))
print('ok')
