p = 'bocconcini/memory.py'
lines = open(p, encoding='utf-8').read().splitlines(True)

# Trova l'inizio del blocco try normale (dopo "if final:")
start = next(i for i, l in enumerate(lines) if 'try:' in l and i > 660 and 'cs = meta.get' in lines[i+1])

# Trova la fine (la riga con "break" dopo "except")
end = next(i for i in range(start, min(start+30, len(lines))) if 'break' in lines[i] and 'error' in lines[i-1])

new_block = [
    '                try:\n',
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
    '                    meta["stopped"] = "error: %s" % exc\n',
    '                break\n'
]

lines = lines[:start] + new_block + lines[end+1:]
open(p, 'w', encoding='utf-8').write(''.join(lines))
print('indentazione corretta')
