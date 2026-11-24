from bocconcini import LlamaCppClient
import time

client = LlamaCppClient()
print("=== TEST 5 - RAFFICA 10X ===")

for i in range(1, 11):
    t0 = time.time()
    testo = client.chat(f"Domanda {i}: dimmi in 2 righe, in italiano, cos'è un carro armato?", continua=False)
    print(f"raffica {i}/10 len={len(testo)} tempo={time.time()-t0:.1f}s testo='{testo[:60]}'")
    print("---")

print("TEST 5: PASS - Raffica finita")
