code = '''
def matrioska_profile(client=None, chars_per_token=3.2):
    """Adaptive matrioska profile derived from archived cognitive/hardware data."""
    import os
    raw = 1200
    cog = None
    n_ctx = 0
    hw = {}
    source = "default"
    if client is not None:
        try:
            info = client._info()
            n_ctx = int(info.get("n_ctx") or 0)
        except Exception:
            info = {}
        try:
            hw = dict(client._hw())
        except Exception:
            hw = {}
        if os.environ.get("BOCCONCINI_NO_COGNITIVE") == "1":
            raw = int(n_ctx * 0.92) if n_ctx else 1200
            source = "n_ctx"
        else:
            try:
                cog = client._cog_stored()
            except Exception:
                cog = None
            try:
                raw = int(client.working_budget(reserve=0))
                source = "cognitive" if cog else ("n_ctx" if n_ctx else "fallback")
            except Exception:
                raw = int(n_ctx * 0.92) if n_ctx else 1200
                source = "n_ctx" if n_ctx else "fallback"
    overhead = float(hw.get("msg_overhead") or 8.0)
    overhead = max(0.0, min(64.0, overhead))
    reserve = 640 + int(overhead * 8)
    usable = max(384, int(raw) - reserve)
    index_budget = max(160, min(900, usable // 4))
    max_facts = max(3, min(12, index_budget // 120))
    row_cost = 28 + 4 * max_facts
    max_children = max(3, min(24, index_budget // max(24, row_cost)))
    leaf_tokens = max(180, min(2400, int(usable * 0.35)))
    leaf_chars = int(leaf_tokens * max(2.0, float(chars_per_token)))
    answer_tokens = max(120, min(700, usable // 4))
    if usable < 1200: max_hops = 8
    elif usable < 2200: max_hops = 7
    elif usable < 5000: max_hops = 6
    else: max_hops = 5
    max_calls = 1 if usable < 2500 else 2
    return {
        "source": source, "n_ctx": n_ctx, "cognitive_limit": cog,
        "raw_window": int(raw), "reserve": reserve, "usable_budget": usable,
        "index_budget": index_budget, "max_children": int(max_children),
        "max_facts_per_summary": int(max_facts), "leaf_max_tokens": int(leaf_tokens),
        "leaf_max_chars": leaf_chars, "answer_tokens": int(answer_tokens),
        "max_hops": int(max_hops), "max_calls": int(max_calls),
        "chars_per_token": float(chars_per_token),
    }

def prepare_matrioska_tree(document, session, tree=None, client=None,
                           max_children=None, leaf_max_chars=None,
                           leaf_max_tokens=None, max_facts_per_summary=None):
    """Build a hierarchical (matrioska) tree adapting to the model cognitive budget."""
    if tree is None:
        tree = DocTree()
    profile = matrioska_profile(client) if client is not None else {}
    if max_children is None: max_children = profile.get("max_children", 8)
    if leaf_max_chars is None: leaf_max_chars = profile.get("leaf_max_chars", 1500)
    if leaf_max_tokens is None: leaf_max_tokens = profile.get("leaf_max_tokens", 500)
    if max_facts_per_summary is None: max_facts_per_summary = profile.get("max_facts_per_summary", 6)
    chunks = split_text(document, name="document.txt", kind="text",
                        max_chars=leaf_max_chars, max_tokens=leaf_max_tokens,
                        min_chars=300, overlap=0)
    all_facts = trova_fatti(document, max_per_tipo=100)
    fact_counts = {}
    for f in all_facts:
        fact_counts[f["tipo"]] = fact_counts.get(f["tipo"], 0) + 1
    signal_rank = {t: i for i, t in enumerate(sorted(fact_counts, key=lambda t: (fact_counts[t], t)))}
    leaves = []
    for i, ch in enumerate(chunks):
        node_id = "leaf_%04d" % i
        meta = etichetta(ch.text, name="document.txt")
        chunk_facts = ["%s:%s" % (f['tipo'], f['valore']) for f in all_facts if ch.start <= f['pos'] < ch.end]
        chunk_facts.sort(key=lambda v: signal_rank.get(v.split(":", 1)[0], 99))
        summary = meta["summary"]
        if chunk_facts:
            visible = chunk_facts[:max_facts_per_summary]
            block = "KEY -> " + ", ".join(visible)
            resto = len(chunk_facts) - len(visible)
            if resto: block += " (+%d more in branch)" % resto
            summary = block + (" | " + summary if summary else "")
        leaves.append(DocNode(id=node_id, label="Section %d (chars %d-%d)" % (i, ch.start, ch.end),
                              summary=summary, text=ch.text, tokens=ch.token_count_estimate(), children=[]))
    current_level = leaves
    level_num = 0
    while len(current_level) > max_children:
        next_level = []
        for i in range(0, len(current_level), max_children):
            group = current_level[i:i + max_children]
            level_num += 1
            container_id = "cont_%d_%03d" % (level_num, i // max_children)
            first_label = group[0].label.split("(")[0].strip()
            last_label = group[-1].label.split("(")[0].strip()
            container_label = "Container (%s ... %s)" % (first_label, last_label)
            container_facts = []
            for child in group:
                if "KEY -> " in child.summary:
                    fact_block = child.summary.split("KEY -> ")[1].split(" | ")[0]
                    facts = [f.strip() for f in fact_block.split(",") if f.strip()]
                    container_facts.extend(facts)
            unique_facts = list(dict.fromkeys(container_facts))
            unique_facts.sort(key=lambda v: signal_rank.get(v.split(":", 1)[0], 99))
            container_summary = ""
            if unique_facts:
                visible = unique_facts[:max_facts_per_summary]
                block = "KEY -> " + ", ".join(visible)
                resto = len(unique_facts) - len(visible)
                if resto: block += " (+%d more in sub-branches)" % resto
                container_summary = block
            container = DocNode(id=container_id, label=container_label, summary=container_summary,
                                text="", tokens=sum(c.tokens for c in group), children=group)
            next_level.append(container)
        current_level = next_level
    tree.save(session, current_level)
    return tree, session
'''

with open("bocconcini/memory.py", "a", encoding="utf-8") as f:
    f.write("\n" + code + "\n")
print("✅ Step 1 completato: funzioni aggiunte in fondo a memory.py")
