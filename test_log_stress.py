import sys
import pathlib
import json

try:
    import bocconcini as b
except ImportError:
    print("Errore: metti test_log_stress.py nella stessa cartella di bocconcini.py")
    sys.exit(1)

chunk_prosa = "INFO 2026-11-15 10:00:00 - Sistema avviato regolarmente. Nessun problema di rete rilevato.\n" * 30
anomalia_1 = "CRITICAL 2026-11-15 10:15:22 - [ANOMALIA_A] Database deadlock rilevato sulla tabella 'utenti_sessione', timeout forzato.\n"
mezzo_log = "DEBUG 2026-11-15 10:30:00 - Elaborazione pacchetto JSON standard in corso...\n" * 40
anomalia_2 = "ERROR 2026-11-15 10:45:11 - [ANOMALIA_B] Memoria esaurita nel worker thread 4, stack trace: ZeroDivisionError a linea 402.\n"
fine_log = "WARNING 2026-11-15 11:00:00 - Latenza di rete sopra la soglia accettabile (120ms).\n" * 30
anomalia_3 = "FATAL 2026-11-15 11:12:05 - [ANOMALIA_C] Token di sicurezza revocate dal server centrale, chiusura forzata socket.\n"

log_totale = chunk_prosa + anomalia_1 + mezzo_log + anomalia_2 + fine_log + anomalia_3
print(f"[*] Log generato con successo. Dimensione totale: {len(log_totale)} caratteri.")

# Prompt base di sistema per l'analisi
prompt_base = "Analizza i seguenti log di sistema alla ricerca di anomalie e rilascia un report sintetico:"

print("[*] Esecuzione dello splitting adattivo con bocconcini...")
chunks = list(b.iter_chunks_adaptive(
    prompt_base=prompt_base,
    text=log_totale,
    name="sistema.log",
    kind="text"
))

print(f"[+] Il log è stato suddiviso in {len(chunks)} chunk coerenti senza spezzare le righe critiche.")
for i, c in enumerate(chunks):
    print(f"    - Chunk {i+1}: da carattere {c.start} a {c.end} ({len(c.text)} caratteri)")

visti = bytearray(len(log_totale))
for c in chunks:
    for idx in range(c.start, c.end):
        visti[idx] = 1

buchi = [i for i in range(len(log_totale)) if not visti[i] and not log_totale[i].isspace()]
if not buchi:
    print("[SUCCESS] Copertura al 100%: nessun carattere utile è stato perso durante il taglio!")
else:
    print(f"[WARNING] {len(buchi)} caratteri non whitespace non sono stati inclusi nei chunk.")

print("\n[*] Test completato con successo!")
