from pathlib import Path
import ast

pm = Path("bocconcini/memory.py")
code = pm.read_text(encoding="utf-8")

old_synthesis = '''    righe = "\\n".join("%s: %s" % (k, v) for k, v in findings)
    p = ("FINDINGS already extracted:\\n" + righe + "\\n\\nAnswer this request using only "
         + "the findings above.\\nRequest: " + question)'''

new_synthesis = '''    # Filtra i NOT FOUND e presenta solo i valori trovati
    found = [(k, v) for k, v in findings if v != "NOT FOUND" and v.strip() != ""]
    if not found:
        # Nessuno trovato: rispondi direttamente senza chiamare il modello
        return {"text": "NOT FOUND: nessun valore estratto per la richiesta.",
                "meta": {"targets": list(targets), "findings": findings,
                         "sub_calls": calls, "biggest_prompt_chars": biggest,
                         "synthesis_skipped": True}}
    
    righe = "\\n".join("%s: %s" % (k, v) for k, v in found)
    not_found_count = len(findings) - len(found)
    
    # Costruisci il prompt con contesto esplicito
    p = ("ORIGINAL REQUEST: " + str(question) + "\\n\\n"
         + "EXTRACTED VALUES:\\n" + righe + "\\n\\n")
    
    if not_found_count > 0:
        p += ("Note: " + str(not_found_count) + " target(s) had no clear associated value "
              + "in the document.\\n")
    
    p += ("Using ONLY the extracted values above, answer the original request.\\n"
          + "If the values are sufficient, provide a complete answer.\\n"
          + "If the values are insufficient, say 'INSUFFICIENT DATA' and explain what is missing.\\n"
          + "Do not invent values that are not in the extracted list.")
    
    biggest = max(biggest, len(p))
    r = client.chat_full(prompt=p, max_tokens=300, temperature=temperature, continua=False)
    
    return {"text": r.text or "", "meta": {"targets": list(targets), "findings": findings,
                                           "sub_calls": calls + 1, "biggest_prompt_chars": biggest,
                                           "found_count": len(found), "not_found_count": not_found_count}}'''

if old_synthesis not in code:
    print("ERRORE: blocco sintesi non trovato")
    raise SystemExit(1)

code = code.replace(old_synthesis, new_synthesis, 1)

try:
    ast.parse(code)
except SyntaxError as e:
    print("ERRORE SINTASSI:", e)
    raise SystemExit(1)

pm.write_text(code, encoding="utf-8")
print("OK: prompt di sintesi migliorato (filtra NOT FOUND, contesto esplicito)")
