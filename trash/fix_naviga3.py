p = 'bocconcini/memory.py'
lines = open(p, encoding='utf-8').read().splitlines(True)

# Trova le righe chiave per numero
ovh_line = next(i for i, l in enumerate(lines) if 'ovh = 8.0' in l and 'except Exception:' in lines[i-1])
meta_end = next(i for i, l in enumerate(lines) if '"budget": budget}' in l and 'answered_from_index' in l)

# 1. Inserisci cog dopo ovh (riga ovh_line + 1)
cog_code = [
    '    try:\n',
    '        cog = int(client._cognitive_limit() or 0) or None\n',
    '    except Exception:\n',
    '        cog = None\n'
]
lines = lines[:ovh_line+1] + cog_code + lines[ovh_line+1:]

# Aggiusta meta_end perché abbiamo inserito righe
meta_end += len(cog_code)

# 2. Inserisci _eff_max dopo meta (riga meta_end + 1)
eff_code = [
    '    # Effective max_tokens: from measured cognitive window, not a fixed ceiling.\n',
    '    # Per-turn cap = cog // 8 so a single step never eats the whole context.\n',
    '    def _eff_max(prompt_tokens: int, is_final: bool) -> int:\n',
    '        if max_tokens is not None:\n',
    '            return int(max_tokens)\n',
    '        ref = cog if cog else budget\n',
    '        margin = int(ovh * 2)\n',
    '        residual = ref - int(prompt_tokens) - margin\n',
    '        cap = max(200, ref // 8) if not is_final else max(200, ref // 4)\n',
    '        return max(200, min(residual, cap))\n'
]
lines = lines[:meta_end+1] + eff_code + lines[meta_end+1:]

# Trova i due blocchi da sostituire (dopo l'inserimento)
forced_start = next(i for i, l in enumerate(lines) if 'meta["evicted"] += _evict(msgs, budget, cpt, ovh, question,' in l and i > meta_end)
forced_block = next(i for i, l in enumerate(lines) if 'answer = r.text' in l and i > forced_start)

# 3. Sostituisci blocco forzato
new_forced = [
    '                        eff = _eff_max(pt, True)\n',
    '                        if cog and pt > int(cog * 0.9):\n',
    '                            meta["evicted"] += _evict(msgs, int(cog * 0.7), cpt, ovh, question,\n',
    '                                                     cost=lambda ms: client._prompt_tokens(ms, None))\n',
    '                        else:\n',
    '                            meta["evicted"] += _evict(msgs, budget, cpt, ovh, question,\n',
    '                                                     cost=lambda ms: client._prompt_tokens(ms, None))\n',
    '                        r = client.chat_full(messages=msgs, tools=None, temperature=temperature,\n',
    '                                            max_tokens=eff, continua=False)\n',
    '                        if getattr(r, "finish_reason", "") == "length":\n',
    '                            meta["truncated"] = meta.get("truncated", 0) + 1\n',
    '                        answer = r.text\n'
]
lines = lines[:forced_start] + new_forced + lines[forced_block+1:]

# Trova blocco normale
normal_start = next(i for i, l in enumerate(lines) if 'cs = meta.get("_consecutive_searches", 0)' in l and i > forced_start)
normal_end = next(i for i, l in enumerate(lines) if 'meta["stopped"] = "error: %s" % exc' in l and i > normal_start)

# 4. Sostituisci blocco normale
new_normal = [
    '                    cs = meta.get("_consecutive_searches", 0)\n',
    '                    if require_read and not meta["nodes_read"] and not final and cs >= 2:\n',
    '                        tc = {"type": "function", "function": {"name": "leggi_nodo"}}\n',
    '                    else:\n',
    '                        tc = "required" if (require_read and not meta["nodes_read"] and not final) else None\n',
    '                    eff = _eff_max(pt, final)\n',
    '                    if cog and pt > int(cog * 0.9):\n',
    '                        meta["evicted"] += _evict(msgs, int(cog * 0.7), cpt, ovh, question,\n',
    '                                                 cost=lambda ms: client._prompt_tokens(ms, tt))\n',
    '                    r = client.chat_full(messages=msgs, tools=tools_now, tool_choice=tc,\n',
    '                                        temperature=temperature, max_tokens=eff, continua=False)\n',
    '                    if getattr(r, "finish_reason", "") == "length":\n',
    '                        meta["truncated"] = meta.get("truncated", 0) + 1\n',
    '                except Exception as exc:\n',
    '                    meta["stopped"] = "error: %s" % exc\n'
]
# Trova la riga "try:" prima di cs
try_line = next(i for i in range(normal_start-1, normal_start-5, -1) if 'try:' in lines[i])
lines = lines[:try_line+1] + new_normal + lines[normal_end+1:]

open(p, 'w', encoding='utf-8').write(''.join(lines))
print('ok')
