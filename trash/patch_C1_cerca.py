from pathlib import Path
import ast

p = Path("bocconcini/memory.py")
old = p.read_text(encoding="utf-8")
lines = old.split("\n")

start = None
end = None
for i, line in enumerate(lines):
    if line.startswith("def _cerca("):
        start = i
        break

if start is None:
    print("ERRORE: def _cerca non trovata")
    raise SystemExit(1)

for j in range(start + 1, len(lines)):
    if lines[j].startswith("def "):
        end = j
        break
if end is None:
    end = len(lines)

new_func = r'''def _cerca(tree: "DocTree", session: str, query: str, limit: int = 8) -> Tuple[str, List[str]]:
    """Matrioska-aware fuzzy search.

    Search ids, labels, summaries and verbatim leaf text. The model paraphrases:
    do not require an exact phrase. Prefer leaves over containers, because opening
    a container only burns a navigation step.
    """
    q = (query or "").strip().lower()
    if not q:
        return "[empty query]", []

    def norm(s: str) -> str:
        return re.sub(r"[\W_]+", "", (s or "").lower())

    stop = {
        "qual", "quale", "quali", "what", "which", "the", "and", "for",
        "with", "from", "this", "that", "della", "delle", "dello", "degli",
        "del", "dei", "gli", "una", "uno", "per", "con", "che", "non",
        "sono", "nel", "nella", "nelle", "negli", "alla", "allo", "agli",
    }
    syn = {
        "verification": ("verifica",),
        "verify": ("verifica",),
        "code": ("codice",),
        "secret": ("segreto",),
        "name": ("nome",),
        "number": ("numero",),
        "codice": ("code",),
        "verifica": ("verification", "verify"),
        "segreto": ("secret",),
        "nome": ("name",),
        "numero": ("number",),
    }

    raw_words = re.findall(r"[a-z0-9à-ù]{3,}", q)
    words: List[str] = []
    for w in raw_words:
        if w in stop:
            continue
        for x in (w,) + syn.get(w, ()):
            if x not in words:
                words.append(x)
    if not words and q:
        words = [q]

    nq = norm(q)
    keys = tree.keys(session)
    candidates = []

    for k in sorted(keys):
        node = keys[k]
        is_container = bool(node.get("children"))
        meta = " ".join([
            str(k),
            str(node.get("label", "")),
            str(node.get("summary", "")),
        ])
        text = ""
        if not is_container:
            try:
                text = tree.load(session, k)
            except TreeError:
                continue

        hay = meta + "\n" + text
        low = hay.lower()
        nh = norm(hay)
        score = 0
        matched: List[str] = []

        if q and q in low:
            score += 30
        if nq and len(nq) >= 3 and nq in nh:
            score += 20

        for w in words:
            c = low.count(w)
            if c:
                score += min(c, 5) * (2 if not is_container else 1)
                matched.append(w)

        if score <= 0:
            continue

        # Prefer actual text leaves over macro containers.
        if not is_container:
            score += 5

        preview = str(node.get("summary") or node.get("label") or "")
        pos = -1
        low_text = text.lower()
        for w in matched or words:
            pos = low_text.find(w)
            if pos >= 0:
                break
        if pos >= 0:
            a, b = max(0, pos - 70), min(len(text), pos + 150)
            preview = " ".join(text[a:b].split())

        candidates.append((score, 1 if is_container else 0, k, preview, is_container))

    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    picked = candidates[:max(1, int(limit))]

    if not picked:
        return "[no branch matches %r. Try another word.]" % query, []

    out = ["Matching branches (call leggi_nodo with a LEAF id when possible):"]
    ids: List[str] = []
    for score, _cflag, k, preview, is_container in picked:
        tag = "CONTAINER" if is_container else "LEAF"
        out.append("- %s [%s] score=%d | %s" % (k, tag, score, preview[:160]))
        ids.append(k)
    return "\n".join(out), ids
'''

new_lines = lines[:start] + new_func.split("\n") + [""] + lines[end:]
new = "\n".join(new_lines)

try:
    ast.parse(new)
except SyntaxError as e:
    print("ERRORE SINTASSI, file NON modificato:", e)
    raise SystemExit(1)

p.with_name(p.name + ".bak_cerca").write_text(old, encoding="utf-8")
p.write_text(new, encoding="utf-8")
print("OK: _cerca sostituita con versione fuzzy/matrioska-aware")
print("Backup:", p.with_name(p.name + ".bak_cerca"))
