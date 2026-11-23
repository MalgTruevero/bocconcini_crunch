import bocconcini
import time

print("=== INIZIO CALIBRAZIONE COGNITIVA ===")
# Inizializziamo il client (usa l'URL di default o quello che usa MALG)
client = bocconcini.LlamaCppClient(base_url="http://127.0.0.1:8082")

# Mostriamo cosa ha rilevato del telefono
info = client.stats()
print(f"Modello rilevato: {info.get('n_ctx')} token nativi")

print("Avvio della sonda (needle-in-the-middle).")
print("Questo può richiedere diversi minuti. Il telefono scalderà. NON PREMERE CTRL+C.")
print("Il watchdog della libreria gestirà i timeout in autonomia.")

start = time.time()
# Questa è la chiamata magica
limite = client.calibra()
end = time.time()

print("\n=== CALIBRAZIONE TERMINATA ===")
print(f"Tempo impiegato: {(end - start) / 60:.1f} minuti")
print(f"Limite cognitivo misurato: {limite} token")

if limite == 0:
    print("⚠️ Attenzione: il test è stato INCONCLUDENTE. Il server era spento o il modello non ha passato il test.")
    print("Nessun limite è stato salvato. La libreria userà il fallback.")
else:
    print(f"✅ Successo! Il limite è stato salvato in ~/.cache/bocconcini/cognitive_limit.json")
    print(f"Da ora in poi, il client ridurrà i prompt più grandi di {limite} token.")
