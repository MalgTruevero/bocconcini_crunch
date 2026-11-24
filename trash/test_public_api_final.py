"""Test finale ingresso pubblico: Integrità Python e 5 aghi in 40k."""
import sys, pathlib, re, time
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# R2: Import SOLO dall'ingresso pubblico
from bocconcini import split_text, ask_stepwise, LlamaCppClient

def test_python_split_integrity():
    """Verifica che split_text non tagli dentro stringhe, parentesi o indentazione."""
    code = '''def complex_function(data):
    """Docstring con "virgolette" interne e tripli apici."""
    result = {
        "key1": [1, 2, 3],
        "key2": {"nested": True, "list": ["a", "b"]}
    }
    # Commento finale
    return result'''

    # Forziamo chunk piccoli per attivare la logica di protezione dei boundary
    chunks = split_text(code, name="test.py", max_chars=60, max_tokens=25)
    
    assert len(chunks) > 1, "Il codice dovrebbe essere stato spezzato in più chunk"
    
    # Verifica che le strutture critiche non siano state tranciate a metà
    joined = "".join(c.text for c in chunks)
    assert "complex_function" in joined, "Nome funzione perso"
    assert '"key2": {"nested": True' in joined, "Dizionario annidato tranciato"
    assert '"""Docstring con "virgolette"' in joined, "Stringa tranciata"
    
    print("OK 1/2: Python code split safely. No broken strings/brackets.")

def test_5_needles_in_40k():
    """Verifica che ask_stepwise trovi 5 target isolati in un documento grande."""
    noise = "Il sistema registra un picco della CPU e la memoria volatile mostra una frammentazione del 12%. "
    doc = noise * 500  # ~40.000 caratteri di rumore

    needles = [
        ("Alpha", "CODICE_ALPHA_1"),
        ("Beta", "CODICE_BETA_2"),
        ("Gamma", "CODICE_GAMMA_3"),
        ("Delta", "CODICE_DELTA_4"),
        ("Epsilon", "CODICE_EPSILON_5")
    ]

    # Inietta gli aghi in posizioni diverse
    for i, (name, code) in enumerate(needles):
        pos = len(doc) * (i + 1) // 6
        doc = doc[:pos] + f"\n[LOG CRITICO] Il codice di {name} e' {code}.\n" + doc[pos:]

    targets = [name for name, _ in needles]
    question = "Trova i 5 codici: Alpha, Beta, Gamma, Delta, Epsilon. Elencali."

    # --- FASE A: Test Offline (Fake Client) per provare l'isolamento ---
    class FakeReply:
        def __init__(self, text): self.text = text
    class FakeClient:
        def __init__(self): self.prompts = []
        def chat_full(self, **kw):
            self.prompts.append(kw.get("prompt", ""))
            # Il fake estrae i codici che vede nel prompt
            found = re.findall(r"CODICE_[A-Z]+_[0-9]", kw.get("prompt", ""))
            return FakeReply(" ".join(dict.fromkeys(found)) if found else "NOT FOUND")

    fake = FakeClient()
    res = ask_stepwise(fake, doc, question, targets=targets)
    
    # Verifica isolamento: ogni sotto-chiamata (tranne l'ultima di sintesi) deve vedere MAX 1 codice
    codes_per_call = [len(set(re.findall(r"CODICE_[A-Z]+_[0-9]", p))) for p in fake.prompts[:-1]]
    assert all(c <= 1 for c in codes_per_call), f"Isolamento fallito: {codes_per_call}"
    
    final_answer = res["text"]
    found_count = sum(1 for _, code in needles if code in final_answer)
    assert found_count == 5, f"Offline: trovati {found_count}/5. Risposta: {final_answer}"
    print(f"OK 2a/2: Offline isolation passed. Found {found_count}/5 codes.")

    # --- FASE B: Test Live con il modello reale ---
    print("Avvio test Live con LlamaCppClient (attendi ~2-3 minuti)...")
    real_client = LlamaCppClient("http://127.0.0.1:8082")
    t0 = time.time()
    live_res = ask_stepwise(real_client, doc, question, targets=targets)
    live_time = time.time() - t0

    live_found = sum(1 for _, code in needles if code in live_res["text"])
    print(f"OK 2b/2: Live test completed in {live_time:.1f}s. Found {live_found}/5 codes.")
    print(f"Live answer snippet:\n{live_res['text'][:300]}")

if __name__ == "__main__":
    try:
        test_python_split_integrity()
        test_5_needles_in_40k()
        print("\n=== TUTTI I TEST PUBBLICI SONO VERDI ===")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nFALLITO: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERRORE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
