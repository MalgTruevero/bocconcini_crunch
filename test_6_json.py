from bocconcini import LlamaCppClient
import json, time

client = LlamaCppClient()
print("=== TEST 6 - JSON ===")

t0 = time.time()
testo = client.chat(
    "Rispondi solo con questo JSON, senza altro testo, senza spiegazioni: {\"parla\": \"Ciao, sono MALG\"}",
    system="Rispondi sempre e solo in JSON valido. Non aggiungere altro testo.",
    continua=False
)

print(f"Tempo: {time.time()-t0:.1f}s")
print(f"Testo: '{testo}'")

try:
    dati = json.loads(testo)
    print(f"JSON valido: {dati}")
    print("TEST 6: PASS - JSON pulito")
except Exception as e:
    print(f"JSON NON valido: {e}")
    print("TEST 6: FAIL - Non è JSON pulito")

