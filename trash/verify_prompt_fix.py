"""
Verifica che il prompt di ask_stepwise contenga le istruzioni migliorate
per chiedere fatti associati invece di "the value for".
"""
import inspect
from bocconcini import memory

src = inspect.getsource(memory.ask_stepwise)

print("=== VERIFICA PROMPT ask_stepwise ===\n")

# Cerca il blocco dove costruisce il prompt per ogni target
lines = src.split('\n')
in_prompt_block = False
prompt_lines = []

for i, line in enumerate(lines):
    if 'ORIGINAL REQUEST:' in line:
        in_prompt_block = True
        start_line = i
    if in_prompt_block:
        prompt_lines.append(line)
        if line.strip().endswith(')'):
            break

print("Prompt per sub-task:")
print("-" * 60)
for line in prompt_lines:
    print(line)
print("-" * 60)

print("\nVerifiche:")

checks = {
    "Contiene 'ORIGINAL REQUEST'": any('ORIGINAL REQUEST' in l for l in prompt_lines),
    "Contiene 'Look near'": any('Look near' in l for l in prompt_lines),
    "Contiene 'ASSOCIATED fact'": any('ASSOCIATED fact' in l for l in prompt_lines),
    "Contiene esempio 'control code'": any('control code' in l for l in prompt_lines),
    "NON contiene 'What is the value for'": not any('What is the value for' in l for l in prompt_lines),
}

all_ok = True
for check, result in checks.items():
    status = "✓" if result else "✗"
    print(f"  {status} {check}")
    if not result:
        all_ok = False

print()
if all_ok:
    print("✓ PROMPT CORRETTO: la patch è attiva")
    print("  Il modello ora cerca 'fatti associati' invece di 'the value for'")
else:
    print("✗ PROBLEMA: il prompt non è stato aggiornato correttamente")
    print("  Il modello sta ancora cercando 'the value for' invece di fatti associati")

