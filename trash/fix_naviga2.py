p = 'bocconcini/memory.py'
s = open(p, encoding='utf-8').read()

# 1. Calcola cog dopo ovh
old_ovh = '        ovh = 8.0'
new_ovh = ('        ovh = 8.0\n'
           '    try:\n'
           '        cog = int(client._cognitive_limit() or 0) or None\n'
           '    except Exception:\n'
           '        cog = None')
assert s.count(old_ovh) == 1, "ovh pattern"
s = s.replace(old_ovh, new_ovh)

# 2. Aggiungi _eff_max dopo meta
old_meta = ('    meta: Dict[str, Any] = {"hops": 0, "nodes_read": [], "evicted": 0, "repeats": 0,\n'
            '                    "branches_cut": [], "unknown_ids": [], "forced_answer": False,\n'
            '                    "answered_from_index": False, "stopped": "", "budget": budget}')
new_meta = (old_meta + '\n'
            '    # Effective max_tokens: from measured cognitive window, not a fixed ceiling.\n'
            '    # Per-turn cap = cog // 8 so a single step never eats the whole context.\n'
            '    def _eff_max(prompt_tokens: int, is_final: bool) -> int:\n'
            '        if max_tokens is not None:\n'
            '            return int(max_tokens)\n'
            '        ref = cog if cog else budget\n'
            '        margin = int(ovh * 2)\n'
            '        residual = ref - int(prompt_tokens) - margin\n'
            '        cap = max(200, ref // 8) if not is_final else max(200, ref // 4)\n'
            '        return max(200, min(residual, cap))')
assert s.count(old_meta) == 1, "meta pattern"
s = s.replace(old_meta, new_meta)

# 3. Chiamata forzata finale
old_forced = ('                    try:\n'
              '                        meta["evicted"] += _evict(msgs, budget, cpt, ovh, question,\n'
              '                                                 cost=lambda ms: client._prompt_tokens(ms, None))\n'
              '                        r = client.chat_full(messages=msgs, tools=None, temperature=temperature,\n'
              '                                            max_tokens=max_tokens, continua=False)\n'
              '                        answer = r.text')
new_forced = ('                    try:\n'
              '                        eff = _eff_max(pt, True)\n'
              '                        if cog and pt > int(cog * 0.9):\n'
              '                            meta["evicted"] += _evict(msgs, int(cog * 0.7), cpt, ovh, question,\n'
              '                                                     cost=lambda ms: client._prompt_tokens(ms, None))\n'
              '                        else:\n'
              '                            meta["evicted"] += _evict(msgs, budget, cpt, ovh, question,\n'
              '                                                     cost=lambda ms: client._prompt_tokens(ms, None))\n'
              '                        r = client.chat_full(messages=msgs, tools=None, temperature=temperature,\n'
              '                                            max_tokens=eff, continua=False)\n'
              '                        if getattr(r, "finish_reason", "") == "length":\n'
              '                            meta["truncated"] = meta.get("truncated", 0) + 1\n'
              '                        answer = r.text')
assert s.count(old_forced) == 1, "forced pattern"
s = s.replace(old_forced, new_forced)

# 4. Chiamata normale
old_normal = ('                try:\n'
              '                    cs = meta.get("_consecutive_searches", 0)\n'
              '                    if require_read and not meta["nodes_read"] and not final and cs >= 2:\n'
              '                        tc = {"type": "function", "function": {"name": "leggi_nodo"}}\n'
              '                    else:\n'
              '                        tc = "required" if (require_read and not meta["nodes_read"] and not final) else None\n'
              '                    r = client.chat_full(messages=msgs, tools=tools_now, tool_choice=tc,\n'
              '                                        temperature=temperature, max_tokens=max_tokens, continua=False)\n'
              '                except Exception as exc:\n'
              '                    meta["stopped"] = "error: %s" % exc')
new_normal = ('                try:\n'
              '                    cs = meta.get("_consecutive_searches", 0)\n'
              '                    if require_read and not meta["nodes_read"] and not final and cs >= 2:\n'
              '                        tc = {"type": "function", "function": {"name": "leggi_nodo"}}\n'
              '                    else:\n'
              '                        tc = "required" if (require_read and not meta["nodes_read"] and not final) else None\n'
              '                    eff = _eff_max(pt, final)\n'
              '                    if cog and pt > int(cog * 0.9):\n'
              '                        meta["evicted"] += _evict(msgs, int(cog * 0.7), cpt, ovh, question,\n'
              '                                                 cost=lambda ms: client._prompt_tokens(ms, tt))\n'
              '                    r = client.chat_full(messages=msgs, tools=tools_now, tool_choice=tc,\n'
              '                                        temperature=temperature, max_tokens=eff, continua=False)\n'
              '                    if getattr(r, "finish_reason", "") == "length":\n'
              '                        meta["truncated"] = meta.get("truncated", 0) + 1\n'
              '                except Exception as exc:\n'
              '                    meta["stopped"] = "error: %s" % exc')
assert s.count(old_normal) == 1, "normal pattern"
s = s.replace(old_normal, new_normal)

open(p, 'w', encoding='utf-8').write(s)
print('ok')
