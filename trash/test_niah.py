import bocconcini
import time

print("=== TEST 1: NIAH (NEEDLE-IN-A-HAYSTACK) SPietato ===")
print("Documento: ~15.000 caratteri. Limite cognitivo misurato: 2048 token.")
print("La libreria DOVRÀ comprimere il contesto per sopravvivere.\n")

# Creiamo un pagliaio enorme con un ago a metà
testo_pagliaio = "Il sistema operativo Android è basato su un kernel Linux. " * 200
ago = "\n\n[IMPORTANTE] Il codice di sblocco del server MALG è DELTA-9. Non dimenticarlo.\n\n"
# Inseriamo l'ago esattamente a metà del documento
meta = len(testo_pagliaio) // 2
documento = testo_pagliaio[:meta] + ago + testo_pagliaio[meta:]

# Inizializziamo il client
client = bocconcini.LlamaCppClient(base_url="http://127.0.0.1:8082")

# Chiediamo al modello di trovare l'ago nel pagliaio
domanda = "Qual è il codice di sblocco del server MALG menzionato nel documento?"
prompt = f"Documento:\n{documento}\n\nDomanda: {domanda}\nRispondi in modo conciso."

print(f"Stima token del prompt completo: {bocconcini.estimate_tokens(prompt)}")
print("Avvio generazione (auto_reduce=True)...")
print("Il telefono potrebbe impiegare diversi minuti per comprimere e generare. NON TOCCARE.\n")

start = time.time()

try:
    # Forziamo auto_reduce=True per far lavorare la libreria
    # Usiamo temperature=0 per determinismo
    reply = client.chat_full(
        prompt=prompt,
        auto_reduce=True,
        temperature=0.0,
        stream=False
    )
    
    end = time.time()
    print(f"=== RISPOSTA RICEVUTA in {end - start:.1f} secondi ===")
    print(f"Testo: {reply.text.strip()}")
    print("-" * 40)
    
    # Valutazione
    if "DELTA-9" in reply.text.upper():
        print("✅ SUPERATO: Il modello ha trovato l'ago nel pagliaio.")
    else:
        print("❌ FALLITO: Il modello ha perso l'informazione (o ha allucinato).")
        
    if reply.meta.get("reduced"):
        print("⚠️ Nota: La libreria ha dovuto ridurre il contesto (_reduce_text) per farlo stare nei 2048 token.")

except Exception as e:
    print(f"❌ ERRORE CRITICO: {e}")
