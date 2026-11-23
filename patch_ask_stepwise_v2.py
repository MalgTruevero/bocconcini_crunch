import ast
from pathlib import Path

p = Path("bocconcini/memory.py")
lines = p.read_text(encoding="utf-8").split("\n")

new_lines = []
i = 0
modified = False
while i < len(lines):
    line = lines[i]
    # Cerca la riga di inizio del prompt, ignorando l'indentazione
    if 'p = ("VERBATIM EXCERPTS' in line and not modified:
        indent = len(line) - len(line.lstrip())
        sp = " " * indent
        
        # Trova la riga di chiusura (quella che contiene '")')
        j = i
        while j < len(lines) and '")' not in lines[j]:
            j += 1
        
        # Costruisci il nuovo prompt con il contesto della domanda originale
        new_block = [
            sp + 'p = ("ORIGINAL REQUEST: " + str(question) + "\\n\\n"',
            sp + '     + "VERBATIM EXCERPTS (from the document):\\n"',
            sp + '     + "\\n".join("- " + w for w in wins) + "\\n\\n"',
            sp + '     + "Look near \'" + str(tg) + "\' for any ASSOCIATED fact, code, number, or value "',
            sp + '     + "(e.g. a control code, an ID, a status, an assignment).\\n"',
            sp + '     + "Extract ONLY that specific associated value. If there is no clear associated "',
            sp + '     + "value near the target, reply NOT FOUND.\\n"',
            sp + '     + "Answer with the value only (no preamble, no quotes).")',
        ]
        new_lines.extend(new_block)
        i = j + 1
        modified = True
    else:
        new_lines.append(line)
        i += 1

if not modified:
    print("ERRORE: blocco VERBATIM EXCERPTS non trovato")
    raise SystemExit(1)

code = "\n".join(new_lines)
try:
    ast.parse(code)
except SyntaxError as e:
    print("ERRORE SINTASSI:", e)
    raise SystemExit(1)

p.write_text(code, encoding="utf-8")
print("OK: ask_stepwise ora passa il contesto della domanda originale al sub-task")
