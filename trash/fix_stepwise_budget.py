from pathlib import Path
import ast

p = Path("bocconcini/memory.py")
code = p.read_text(encoding="utf-8")

old_block = """        while len(wins) < per_target:
            k = low.find(q, start)
            if k < 0:
                break
            a, b = max(0, k - window // 2), min(len(documento), k + len(q) + window // 2)
            wins.append(documento[a:b].replace("\\n", " "))
            start = k + len(q)"""

new_block = """        # Hard limit: la finestra NON DEVE MAI sforare il budget cognitivo
        hard_limit = max(window, min(int(max_tokens * 3.2 * 1.5), window * 4))
        while len(wins) < per_target:
            k = low.find(q, start)
            if k < 0:
                break
            
            # 1. Confini naturali (frase/paragrafo)
            a_nat, b_nat = k, k + len(q)
            while a_nat > 0 and documento[a_nat-1] not in ".!?\\n": a_nat -= 1
            while b_nat < len(documento) and documento[b_nat] not in ".!?\\n": b_nat += 1
            
            # 2. Se la frase naturale entra nel budget, usala intera
            if (b_nat - a_nat) <= hard_limit:
                a, b = a_nat, b_nat
            else:
                # 3. IL CONTRARIO: la frase sfora, contraila al budget centrando su q
                a = max(0, k - hard_limit // 2)
                b = min(len(documento), k + len(q) + hard_limit // 2)
                # Aggiusta i bordi per non tagliare parole a meta'
                if a > 0:
                    space = documento.find(" ", a, a + 40)
                    if space != -1 and space < a + 40: a = space + 1
                if b < len(documento):
                    space = documento.rfind(" ", max(a, b - 40), b)
                    if space != -1: b = space
                    
            wins.append(documento[a:b].replace("\\n", " "))
            start = k + len(q)"""

if old_block not in code:
    print("ERRORE: blocco originale di ask_stepwise non trovato.")
    raise SystemExit(1)

code = code.replace(old_block, new_block)

try:
    ast.parse(code)
except SyntaxError as e:
    print("ERRORE SINTASSI:", e)
    raise SystemExit(1)

p.write_text(code, encoding="utf-8")
print("✅ Fix applicato: ask_stepwise ora usa la logica 'Budget-First' (non sfora mai la taratura cognitiva).")
