import re
from pathlib import Path

p = Path("bocconcini/memory.py")
code = p.read_text(encoding="utf-8")

# =====================================================================
# 1. FIX _CERCA: Matrioska-Aware, tollera punteggiatura, mostra anteprime
# =====================================================================
old_cerca_sig = 'def _cerca(tree: "DocTree", session: str, query: str, limit: int = 8) -> Tuple[str, List[str]]:'
new_cerca = '''def _cerca(tree: "DocTree", session: str, query: str, limit: int = 8) -> Tuple[str, List[str]]:
    """Matrioska-aware search. Ignores punctuation/case, prioritizes leaves."""
    q = (query or "").strip().lower()
    q_norm = re.sub(r"[\\s_\\-\\.:,;]+", "", q)
    if not q:
        return "[empty query]", []
    keys = tree.keys(session)
    order = sorted(keys)
    hits = []
    # 1. Cerca in ID, Label, Summary (tutti i nodi)
    for k in order:
        if len(hits) >= limit: break
        node = keys[k]
        is_container = bool(node.get("children"))
        text_to_search = (k + " " + str(node.get("label", "")) + " " + str(node.get("summary", ""))).lower()
        text_norm = re.sub(r"[\\s_\\-\\.:,;]+", "", text_to_search)
        if q in text_to_search or (q_norm and q_norm in text_norm):
            hits.append((k, is_container, str(node.get("summary", ""))[:80]))
    # 2. Cerca nel testo verbatim (SOLO foglie, per evitare di aprire contenitori)
    for k in order:
        if len(hits) >= limit: break
        if any(h[0] == k for h in hits): continue
        node = keys[k]
        if node.get("children"): continue 
        try:
            full_text = tree.load(session, k).lower()
            full_norm = re.sub(r"[\\s_\\-\\.:,;]+", "", full_text)
            if q in full_text or (q_norm and q_norm in full_norm):
                hits.append((k, False, "Match nel testo verbatim"))
        except TreeError:
            continue
    if not hits:
        alt = re.sub(r"^[a-z]+\\s*[:\\s]\\s*", "", q).strip()
        if alt and alt != q:
            return _cerca(tree, session, alt, limit)
        return "[no branch matches %r. Try another word.]" % query, []
    lines = ["Matching branches (call leggi_nodo with the full id):"]
    ids = []
    for k, is_cont, preview in hits:
        tag = "[CONTENITORE - ha figli, evita se cerchi testo]" if is_cont else "[FOGLIA]"
        lines.append(f"- {k} {tag} | {preview}")
        ids.append(k)
    return "\\n".join(lines), ids
'''

start_idx = code.find(old_cerca_sig)
if start_idx != -1:
    next_def = code.find("\ndef ", start_idx + 10)
    if next_def == -1: next_def = len(code)
    code = code[:start_idx] + new_cerca + "\n" + code[next_def:]
    print("✅ 1. _cerca aggiornata (Matrioska-Aware + Punteggiatura)")
else:
    print("❌ _cerca non trovata")

# =====================================================================
# 2. FIX NAVIGA: I contenitori non consumano hop (navigazione free)
# =====================================================================
old_kids = '''kids = valid.get(nid, {}).get("children")
if kids:
    shown = [str(c["id"]) for c in kids]'''
new_kids = '''kids = valid.get(nid, {}).get("children")
if kids:
    shown = [str(c["id"]) for c in kids]
    meta["container_reads"] = meta.get("container_reads", 0) + 1'''
code = code.replace(old_kids, new_kids)

old_reads_turn = '''else:
    reads_turn += 1
    try:
        full = tree.load(session, nid)
        meta["nodes_read"].append(nid)'''
new_reads_turn = '''else:
    try:
        full = tree.load(session, nid)
        is_container = bool(valid.get(nid, {}).get("children"))
        if not is_container:
            reads_turn += 1
            meta["nodes_read"].append(nid)'''
code = code.replace(old_reads_turn, new_reads_turn)
print("✅ 2. naviga aggiornata (contenitori non bruciano hop)")

# =====================================================================
# 3. FIX ASK_STEPWISE: Finestra elastica (si espande a frase/paragrafo)
# =====================================================================
old_window = '''a, b = max(0, k - window // 2), min(len(documento), k + len(q) + window // 2)
wins.append(documento[a:b].replace("\\n", " "))'''
new_window = '''a, b = max(0, k - window), min(len(documento), k + len(q) + window)
# Espandi ai confini di frase/paragrafo per non tagliare il codice reale
while a > 0 and documento[a-1] not in ".!?\\n": a -= 1
while b < len(documento) and documento[b] not in ".!?\\n": b += 1
wins.append(documento[a:b].replace("\\n", " "))'''
code = code.replace(old_window, new_window)
print("✅ 3. ask_stepwise aggiornata (finestra elastica a frase)")

p.write_text(code, encoding="utf-8")
print("\n🎉 Patch applicata! La libreria ora gestisce la matrioska in modo intelligente.")
