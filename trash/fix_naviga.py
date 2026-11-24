p = 'bocconcini/memory.py'
s = open(p, encoding='utf-8').read()

# 1. Cambia il default della firma
s = s.replace('max_tokens: int = 400,', 'max_tokens: Optional[int] = None,')

# 2. Aggiungi la risoluzione dinamica subito dopo l'inizio della funzione, 
#    prima che max_tokens venga usato nel calcolo del budget.
#    Cerchiamo la riga dove viene definito 'cpt' per inserirlo dopo.
old_cpt = '    cpt = max(1.0, float(chars_per_token))'
new_cpt = ('    cpt = max(1.0, float(chars_per_token))\n'
           '    if max_tokens is None:\n'
           '        max_tokens = matrioska_profile(client)["answer_tokens"]')

assert s.count(old_cpt) == 1, "Pattern non trovato o duplicato"
s = s.replace(old_cpt, new_cpt)

open(p, 'w', encoding='utf-8').write(s)
print('memory.py aggiornato')
