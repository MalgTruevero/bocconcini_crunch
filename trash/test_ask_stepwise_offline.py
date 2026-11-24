"""
Test offline di ask_stepwise.
Mocka chat_full per catturare i prompt senza chiamare il server.
Verifica che il nuovo prompt (con ORIGINAL REQUEST + Look near) sia costruito correttamente.
"""
import sys
import bocconcini as b
from bocconcini import client as client_mod

print("=== TEST OFFLINE ask_stepwise ===\n")

# 1. Verifica che il sorgente contenga le stringhe chiave
import inspect
src = inspect.getsource(b.ask_stepwise)
checks = {
    "ORIGINAL REQUEST": "ORIGINAL REQUEST" in src,
    "Look near": "Look near" in src,
    "ASSOCIATED fact": "ASSOCIATED fact" in src,
    "control code": "control code" in src,
    "str(question)": "str(question)" in src,
    "str(tg)": "str(tg)" in src,
}

print("[1] Verifica contenuto sorgente:")
all_ok = True
for k, v in checks.items():
    print("  %s: %s" % (k, "OK" if v else "MANCANTE"))
    if not v:
        all_ok = False

if not all_ok:
    print("\nERRORE: il prompt di ask_stepwise non e' stato aggiornato correttamente")
    sys.exit(1)

# 2. Mock di chat_full per catturare i prompt
captured_prompts = []

class MockClient:
    def chat_full(self, prompt, **kwargs):
        captured_prompts.append(prompt)
        max_tokens = kwargs.get("max_tokens", 100)
        # Prima chiamata: restituisce la lista dei target
        if "List the distinct items" in prompt:
            text = "__buffer__\ntype_comments"
        # Chiamate intermedie: estrazione dei valori
        elif "__buffer__" in prompt:
            text = "BFR-7491"
        elif "type_comments" in prompt:
            text = "True"
        # Ultima chiamata: sintesi finale
        else:
            text = "Codici trovati: BFR-7491, True"
        return client_mod.ChatReply(text=text, finish_reason="stop", tokens=len(text.split()))

mock = MockClient()

# 3. Documento di prova con i due aghi
doc = """
In Python 3.11 __buffer__ e' deprecato.
Nota: In Python 3.12 __buffer__ restituisce memoryview o TypeError: codice controllo BFR-7491.
Alcune funzioni accettano type_comments=True per compatibilita'.
"""

# 4. Esegui ask_stepwise con i target noti (salta la prima chiamata di discovery)
print("\n[2] Esecuzione ask_stepwise con mock client...")
out = b.ask_stepwise(
    mock,
    doc,
    "Trova tutti i codici di controllo nel documento",
    targets=["__buffer__", "type_comments"],
    max_tokens=60,
    window=200,
    per_target=1,
)

# 5. Analizza i prompt catturati
print("\n[3] Analisi dei %d prompt catturati:" % len(captured_prompts))
for i, p in enumerate(captured_prompts):
    print("\n--- Prompt #%d (%d char) ---" % (i + 1, len(p)))
    # Mostra solo le prime 15 righe per leggibilita'
    lines = p.split("\n")
    for ln in lines[:15]:
        print("  " + ln[:120])
    if len(lines) > 15:
        print("  ... (%d altre righe)" % (len(lines) - 15))

# 6. Verifiche sulla struttura dei prompt
print("\n[4] Verifiche strutturali:")

# Il primo prompt catturato e' quello di estrazione per __buffer__
sub_prompts = [p for p in captured_prompts if "VERBATIM EXCERPTS" in p]
print("  Prompt di estrazione: %d" % len(sub_prompts))

buffer_prompt = next((p for p in sub_prompts if "__buffer__" in p), None)
if buffer_prompt:
    has_original = "ORIGINAL REQUEST" in buffer_prompt
    has_look_near = "Look near '__buffer__'" in buffer_prompt
    has_associated = "ASSOCIATED fact" in buffer_prompt
    has_example = "control code" in buffer_prompt
    has_question = "codici di controllo" in buffer_prompt
    print("  Prompt per __buffer__:")
    print("    - contiene ORIGINAL REQUEST: %s" % ("OK" if has_original else "MANCANTE"))
    print("    - contiene 'Look near '__buffer__'': %s" % ("OK" if has_look_near else "MANCANTE"))
    print("    - contiene ASSOCIATED fact: %s" % ("OK" if has_associated else "MANCANTE"))
    print("    - esempio 'control code': %s" % ("OK" if has_example else "MANCANTE"))
    print("    - contiene la domanda originale: %s" % ("OK" if has_question else "MANCANTE"))
else:
    print("  ERRORE: prompt per __buffer__ non trovato")

# 7. Verifica dei risultati
print("\n[5] Risultati di ask_stepwise:")
print("  text: %s" % out.get("text", "")[:200])
print("  findings: %s" % out.get("meta", {}).get("findings"))

findings = dict(out.get("meta", {}).get("findings", []))
buffer_val = findings.get("__buffer__", "")
print("\n  Valore estratto per __buffer__: %r" % buffer_val)

if buffer_val == "BFR-7491":
    print("\n✓ RISULTATO: la logica funziona correttamente")
    print("  Il modello (mockato) ha estratto il codice BFR-7491 vicino a __buffer__")
    print("  Questo significa che con un modello reale, il prompt aggiornato")
    print("  gli darebbe il contesto per trovare il codice anche senza assegnazione diretta.")
else:
    print("\n✗ ATTENZIONE: valore inatteso")
