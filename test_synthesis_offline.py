"""
Test offline del nuovo prompt di sintesi di ask_stepwise.
Mocka chat_full per simulare diversi scenari:
1. Tutti i target trovati
2. Alcuni target NOT FOUND
3. Nessun target trovato
"""
import bocconcini as b
from bocconcini import client as client_mod

class MockClient:
    def __init__(self, scenario):
        self.scenario = scenario
        self.calls = []
    
    def chat_full(self, prompt, **kwargs):
        self.calls.append(prompt)
        max_tokens = kwargs.get("max_tokens", 100)
        
        # Discovery targets
        if "List the distinct items" in prompt:
            text = "__buffer__\ntype_comments\n__alloc__"
        
        # Sub-task extraction
        elif "__buffer__" in prompt:
            if self.scenario == "all_found":
                text = "BFR-7491"
            elif self.scenario == "partial":
                text = "BFR-7491"
            else:
                text = "NOT FOUND"
        
        elif "type_comments" in prompt:
            if self.scenario in ["all_found", "partial"]:
                text = "True"
            else:
                text = "NOT FOUND"
        
        elif "__alloc__" in prompt:
            if self.scenario == "all_found":
                text = "ALLOC-2024"
            else:
                text = "NOT FOUND"
        
        # Synthesis
        elif "EXTRACTED VALUES" in prompt or "ORIGINAL REQUEST" in prompt:
            if self.scenario == "all_found":
                text = "Trovati tutti i codici: BFR-7491, True, ALLOC-2024"
            elif self.scenario == "partial":
                text = "Trovati 2 codici: BFR-7491 e True. Manca __alloc__."
            else:
                text = "INSUFFICIENT DATA"
        
        else:
            text = "Risposta generica"
        
        return client_mod.ChatReply(text=text, finish_reason="stop", tokens=len(text.split()))

# Documento di prova
doc = """
In Python 3.11 __buffer__ e' deprecato.
Nota: In Python 3.12 __buffer__ restituisce memoryview o TypeError: codice controllo BFR-7491.
Alcune funzioni accettano type_comments=True per compatibilita'.
Il metodo __alloc__ non e' documentato ma ha codice controllo ALLOC-2024.
"""

print("=== TEST SINTESI ask_stepwise ===\n")

# Scenario 1: Tutti i target trovati
print("[1] Scenario: TUTTI I TARGET TROVATI")
mock1 = MockClient("all_found")
out1 = b.ask_stepwise(mock1, doc, "Trova tutti i codici di controllo",
                      targets=["__buffer__", "type_comments", "__alloc__"],
                      max_tokens=60, window=200, per_target=1)
print("  text:", out1["text"])
print("  findings:", out1["meta"]["findings"])
print("  found_count:", out1["meta"].get("found_count"))
print("  not_found_count:", out1["meta"].get("not_found_count"))
print("  sub_calls:", out1["meta"]["sub_calls"])
print()

# Scenario 2: Alcuni target NOT FOUND
print("[2] Scenario: ALCUNI TARGET NOT FOUND")
mock2 = MockClient("partial")
out2 = b.ask_stepwise(mock2, doc, "Trova tutti i codici di controllo",
                      targets=["__buffer__", "type_comments", "__alloc__"],
                      max_tokens=60, window=200, per_target=1)
print("  text:", out2["text"])
print("  findings:", out2["meta"]["findings"])
print("  found_count:", out2["meta"].get("found_count"))
print("  not_found_count:", out2["meta"].get("not_found_count"))
print("  sub_calls:", out2["meta"]["sub_calls"])
print()

# Scenario 3: Nessun target trovato
print("[3] Scenario: NESSUN TARGET TROVATO")
mock3 = MockClient("none_found")
out3 = b.ask_stepwise(mock3, doc, "Trova tutti i codici di controllo",
                      targets=["__buffer__", "type_comments", "__alloc__"],
                      max_tokens=60, window=200, per_target=1)
print("  text:", out3["text"])
print("  findings:", out3["meta"]["findings"])
print("  synthesis_skipped:", out3["meta"].get("synthesis_skipped", False))
print("  sub_calls:", out3["meta"]["sub_calls"])
print()

# Verifica che il prompt di sintesi sia corretto
print("[4] Verifica contenuto prompt di sintesi (scenario 2)")
synthesis_prompt = mock2.calls[-1] if mock2.calls else ""
if "EXTRACTED VALUES" in synthesis_prompt:
    print("  Prompt contiene EXTRACTED VALUES: OK")
else:
    print("  Prompt NON contiene EXTRACTED VALUES")

if "NOT FOUND" not in synthesis_prompt.split("EXTRACTED VALUES")[1].split("Note:")[0] if "EXTRACTED VALUES" in synthesis_prompt else True:
    print("  NOT FOUND filtrati dal prompt: OK")
else:
    print("  ATTENZIONE: NOT FOUND ancora presenti nel prompt")

print("\n" + "=" * 50)
print("TEST COMPLETATO")
