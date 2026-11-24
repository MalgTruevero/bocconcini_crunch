from pathlib import Path
import ast

pm = Path("bocconcini/memory.py")
code = pm.read_text(encoding="utf-8")

old_prompt = '''p = ("VERBATIM EXCERPTS:\\n" + "\\n".join("- " + w for w in wins)
             + "\\nWhat is the value for '" + str(tg) + "'? Answer with the value only, "
             + "or NOT FOUND if it is not in the excerpts.")'''

new_prompt = '''p = ("ORIGINAL REQUEST: " + str(question) + "\\n\\n"
             + "VERBATIM EXCERPTS (from the document):\\n"
             + "\\n".join("- " + w for w in wins) + "\\n\\n"
             + "Look near '" + str(tg) + "' for any ASSOCIATED fact, code, number, or value "
             + "(e.g. a control code, an ID, a status, an assignment).\\n"
             + "Extract ONLY that specific associated value. If there is no clear associated "
             + "value near the target, reply NOT FOUND.\\n"
             + "Answer with the value only (no preamble, no quotes).")'''

if old_prompt not in code:
    print("ERRORE: prompt attuale di ask_stepwise non trovato")
    raise SystemExit(1)

code = code.replace(old_prompt, new_prompt, 1)

try:
    ast.parse(code)
except SyntaxError as e:
    print("ERRORE SINTASSI:", e)
    raise SystemExit(1)

pm.write_text(code, encoding="utf-8")
print("OK: ask_stepwise ora passa il contesto della domanda originale al sub-task")
