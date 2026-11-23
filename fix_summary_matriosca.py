from pathlib import Path
import ast

p = Path("bocconcini/memory.py")
content = p.read_text(encoding="utf-8")

old = "            blocco = _fatti_in_range(tutti_i_fatti, inizio, fine, signal_rank, tetto_fatti)"
new = """            blocco = _fatti_in_range(tutti_i_fatti, inizio, fine, signal_rank, tetto_fatti)
            if not blocco:
                # Fallback: eredita i summary delle foglie (termini frequenti, numeri)
                parti = [c.summary for c in gruppo if c.summary]
                if parti:
                    blocco = " | ".join(parti)
                    if len(blocco) > tetto_fatti * 2:
                        blocco = blocco[:tetto_fatti * 2 - 3] + "...\""""

if old not in content:
    print("ERRORE: riga da modificare non trovata.")
    raise SystemExit(1)

content = content.replace(old, new)

try:
    ast.parse(content)
except SyntaxError as e:
    print("ERRORE SINTASSI:", e)
    raise SystemExit(1)

p.write_text(content, encoding="utf-8")
print("✅ Fix applicato: i macro-blocchi ora ereditano i summary delle foglie.")
