import bocconcini
import time

print("=== TEST: IL CARRO ARMATO (10.000 Token, 4 Aghi) ===")
print("Documento: ~32.000 caratteri (~10.000 token).")
print("Limite cognitivo: 2048 token. Compressione richiesta: ~80%.")
print("4 Aghi nascosti a 10%, 35%, 60%, 85%.\n")

# 1. I 4 aghi (informazioni vitali)
ago1 = "\n[LOG CRITICO] Il codice di sblocco della batteria è ALFA-1.\n"
ago2 = "\n[LOG CRITICO] La password del database di telemetria è OMEGA-9.\n"
ago3 = "\n[LOG CRITICO] Il nome in codice del satellite è TITANO-3.\n"
ago4 = "\n[LOG CRITICO] La chiave API del server di backup è BETA-7.\n"

# 2. Rumore di fondo (testo tecnico noioso)
rumore = (
    "Il sistema ha registrato un picco di utilizzo della CPU. "
    "I thread di esecuzione sono stati riallocati per evitare il throttling. "
    "La memoria volatile mostra una frammentazione del 12%. "
    "I log del kernel indicano un accesso in lettura sul device sda1. "
    "La temperatura del core è stabile. "
) * 120

# 3. Inseriamo gli aghi nelle posizioni strategiche
n = len(rumore)
doc = (rumore[:int(n*0.10)] + ago1 + 
       rumore[int(n*0.10):int(n*0.35)] + ago2 + 
       rumore[int(n*0.35):int(n*0.60)] + ago3 + 
       rumore[int(n*0.60):int(n*0.85)] + ago4 + 
       rumore[int(n*0.85):])

# 4. Inizializziamo il client
client = bocconcini.LlamaCppClient(base_url="http://127.0.0.1:8082")

# 5. Domanda che richiede tutti e 4 i dati
domanda = """Sei un analista di sistema. Leggi il documento e trova i 4 log critici.
Estrai e riporta ESATTAMENTE questi quattro valori:
1. Il codice di sblocco della batteria
2. La password del database di telemetria
3. Il nome in codice del satellite
4. La chiave API del server di backup

Rispondi in modo conciso elencando i 4 valori trovati."""

prompt = f"Documento:\n{doc}\n\nDomanda: {domanda}"

print(f"Stima token del prompt completo: {bocconcini.estimate_tokens(prompt)}")
print("Avvio generazione (auto_reduce=True, temperature=0.0)...")
print("QUESTA E' UNA BATTAGLIA DI RESISTENZA. NON TOCCARE IL TELEFONO.\n")

start = time.time()

try:
    reply = client.chat_full(
        prompt=prompt,
        auto_reduce=True,
        temperature=0.0,
        stream=False,
        max_tokens=256
    )
    
    end = time.time()
    print(f"=== RISPOSTA RICEVUTA in {end - start:.1f} secondi ({(end-start)/60:.1f} minuti) ===")
    print(f"Testo:\n{reply.text.strip()}")
    print("-" * 40)
    
    # 6. Valutazione spietata
    testo_risposta = reply.text.upper()
    trovati = 0
    
    for nome, codice in [("1 (10%)", "ALFA-1"), ("2 (35%)", "OMEGA-9"), ("3 (60%)", "TITANO-3"), ("4 (85%)", "BETA-7")]:
        if codice in testo_risposta:
            print(f"✅ Trovato AGO {nome}: {codice}")
            trovati += 1
        else:
            print(f"❌ Perso AGO {nome}: {codice}")
            
    print(f"\n=== ACCURATEZZA: {trovati}/4 ===")
    
    if trovati == 4:
        print("🏆 CARRO ARMATO CONFERMATO: 4 aghi su 4 in 10.000 token. La fortuna non c'entra nulla.")
    elif trovati >= 2:
        print("🛡️ MOLTO ROBUSTA: Ha perso qualche dettaglio, ma ha retto un colpo devastante.")
    else:
        print("⚠️ FALLA NEL CARRO ARMATO: La compressione cieca ha distrutto troppe informazioni vitali.")

    if reply.meta.get("reduced"):
        print("⚠️ Nota: La libreria ha ridotto il contesto (_reduce_text).")

except Exception as e:
    print(f"❌ ERRORE CRITICO: {e}")
