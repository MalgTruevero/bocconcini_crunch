p = 'test_matriosca_lib.py'
s = open(p, encoding='utf-8').read()

# Rimuove i tetti fissi in uscita, lasciando che la libreria calcoli il budget dinamico
s = s.replace('max_hops=6, max_tokens=120)', 'max_hops=6)')
s = s.replace('max_hops=10, max_tokens=260)', 'max_hops=10)')
s = s.replace('max_hops=10, max_tokens=60,', 'max_hops=10,')

open(p, 'w', encoding='utf-8').write(s)
print('test_matriosca_lib.py aggiornato')
