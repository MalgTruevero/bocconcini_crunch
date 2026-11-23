from bocconcini import LlamaCppClient
import time

client = LlamaCppClient()
print("=== TEST 7 - CONTESTO OLTRE 4096 ===")

# Prompt da 12000 caratteri, troppo grande per i 4096 del cervello
base = "Nel deserto non c'era cielo, solo polvere e ferro. I viaggiatori cercavano la Fiamma Rossa. "
prompt = "Racconta in italiano, in 3 righe, cosa succede in questa storia: " + base * 150
print(f"Prompt len: {len(prompt)} char")

t0 = time.time()
testo = client.chat(prompt, system="Rispondi sempre e solo in italiano.", continua=False)
print(f"Tempo: {time.time()-t0:.1f}s")
print(f"Out len: {len(testo)} char")
print(f"Testo: '{testo[:300]}'")

if len(testo) > 0:
    print("TEST 7: PASS - Ha risposto anche con contesto esploso")
else:
    print("TEST 7: FAIL - 0 caratteri, come le altre librerie")
