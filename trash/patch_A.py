from pathlib import Path
import ast

p = Path("bocconcini/client.py")
code = p.read_text(encoding="utf-8")

# ============================================================
# FIX 1: _drop_old_history non deve cancellare i tool results
# ============================================================
old_drop = '''while cost(out) > budget:
            first = next((i for i, m in enumerate(out[:-1]) if m.get("role") != "system"), None)
            if first is None:
                break'''

new_drop = '''while cost(out) > budget:
            # Skip system, tool results, and the last message (the request)
            first = next((i for i, m in enumerate(out[:-1]) 
                         if m.get("role") not in ("system", "tool")), None)
            if first is None:
                break'''

if old_drop not in code:
    print("ERRORE: blocco _drop_old_history non trovato")
    raise SystemExit(1)

code = code.replace(old_drop, new_drop)
print("✅ Fix 1: _drop_old_history ora preserva i tool results")

# ============================================================
# FIX 2: margine di sicurezza sul cognitive limit (10%)
# ============================================================
old_cog = '''cog = 0 if os.environ.get("BOCCONCINI_NO_COGNITIVE") == "1" else (self._cog_stored() or 0)
        if cog:
            meta["cognitive_limit"] = cog'''

new_cog = '''cog_raw = 0 if os.environ.get("BOCCONCINI_NO_COGNITIVE") == "1" else (self._cog_stored() or 0)
        cog = int(cog_raw * 0.90) if cog_raw else 0  # 10% safety margin
        if cog:
            meta["cognitive_limit"] = cog
            meta["cognitive_limit_raw"] = cog_raw'''

if old_cog not in code:
    print("ERRORE: blocco cognitive_limit non trovato")
    raise SystemExit(1)

code = code.replace(old_cog, new_cog)
print("✅ Fix 2: margine di sicurezza 10% sul cognitive limit")

# Verifica sintassi prima di scrivere
try:
    ast.parse(code)
except SyntaxError as e:
    print("ERRORE SINTASSI:", e)
    raise SystemExit(1)

p.write_text(code, encoding="utf-8")
print("\n🎉 Patch A completata!")
