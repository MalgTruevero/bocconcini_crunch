"""bocconcini.memory - verbatim chunks on disk, only the index in RAM.

Standard library only. Python informs (structure, labels), the model decides
(which branch to read). Nothing here calls a model or a server.
"""
from __future__ import annotations
import ast, hashlib, json, os, re, shutil, time, zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from .client import split_text, estimate_tokens
__all__ = ["DocNode", "DocTree", "TreeError", "etichetta", "naviga", "albero_codice", "trova_fatti", "prepara_albero_ricco", "matrioska_profile", "prepare_matrioska_tree", "calibra_navigazione"]
_MAX_BACKUPS = 5
_DIARY_KEEP = 500
_ZIP_ABOVE = 100


class TreeError(RuntimeError):
    """A branch could not be read. Never confused with an empty branch."""


@dataclass
class DocNode:
    id: str
    label: str = ""
    summary: str = ""
    text: str = ""
    tokens: int = 0
    children: List["DocNode"] = field(default_factory=list)


_SAFE = re.compile(r"[^A-Za-z0-9_\-]+")


def _key(node_id: str) -> str:
    """Safe for the filesystem AND collision-free: ids that sanitize alike differ in the hash."""
    raw = str(node_id or "")
    stem = _SAFE.sub("_", raw.strip())[:48] or "nodo"
    return "%s_%s" % (stem, hashlib.blake2b(raw.encode("utf-8", "replace"), digest_size=4).hexdigest())


def _walk(nodes: List[DocNode]) -> Iterator[DocNode]:
    stack = list(nodes)[::-1]
    while stack:
        n = stack.pop()
        yield n
        if n.children:
            stack.extend(n.children[::-1])


class DocTree:
    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base = Path(base_dir) if base_dir else Path.home() / ".cache" / "bocconcini" / "workspace"
        self.base.mkdir(parents=True, exist_ok=True)
        self._idx_cache: Dict[str, Any] = {}

    def _dir(self, session: str) -> Path:
        return self.base / _key(session)

    def _diary(self, action: str, session: str, detail: str) -> None:
        try:
            f = self.base / "diario.json"
            rows = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
            if not isinstance(rows, list):
                rows = []
            rows.append({"at": time.time(), "action": action, "session": session, "detail": detail[:400]})
            tmp = f.with_name(f.name + ".tmp")
            tmp.write_text(json.dumps(rows[-_DIARY_KEEP:], ensure_ascii=False), encoding="utf-8")
            os.replace(str(tmp), str(f))
        except Exception:
            pass

    def _backup(self, d: Path) -> Optional[Path]:
        """Move the WHOLE previous version away; the caller puts the new one in its place."""
        if not (d / "index.json").exists():
            shutil.rmtree(d, ignore_errors=True)
            return None
        bdir = self.base / "_backup"
        bdir.mkdir(parents=True, exist_ok=True)
        stem = "%s_%d" % (d.name, int(time.time()))
        dest, i = bdir / stem, 0
        while dest.exists():
            i += 1
            dest = bdir / ("%s_%d" % (stem, i))
        shutil.move(str(d), str(dest))
        old = sorted(bdir.iterdir(), key=lambda q: q.stat().st_mtime)
        for q in old[:-_MAX_BACKUPS]:
            shutil.rmtree(q, ignore_errors=True)
        return dest

    @staticmethod
    def _plain(n: DocNode) -> Dict[str, Any]:
        d = {"id": str(n.id), "key": _key(n.id), "label": n.label,
             "summary": n.summary, "tokens": int(n.tokens or 0), "chars": len(n.text or "")}
        if n.children:
            d["children"] = [DocTree._plain(c) for c in n.children]
        return d

    def save(self, session: str, roots: List[DocNode], meta: str = "") -> Dict[str, Any]:
        nodes = list(_walk(roots))
        seen = set()
        for n in nodes:
            k = str(n.id)
            if k in seen:
                raise TreeError("duplicate node id %r: two branches would overwrite each other" % k)
            seen.add(k)
        d = self._dir(session)
        stage = d.with_name(d.name + ".new")
        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir(parents=True, exist_ok=True)
        mode = "zip" if len(nodes) > _ZIP_ABOVE else "singoli"
        try:
            if mode == "zip":
                with zipfile.ZipFile(stage / "chunks.zip", "w", compression=zipfile.ZIP_DEFLATED) as z:
                    for n in nodes:
                        z.writestr(_key(n.id) + ".txt", n.text or "")
                with zipfile.ZipFile(stage / "chunks.zip", "r") as z:
                    have = set(z.namelist())
                    for n in nodes:
                        nm = _key(n.id) + ".txt"
                        if nm not in have:
                            raise TreeError("branch %r was not written" % n.id)
                        z.read(nm)
            else:
                (stage / "chunks").mkdir(exist_ok=True)
                for n in nodes:
                    (stage / "chunks" / (_key(n.id) + ".txt")).write_text(n.text or "", encoding="utf-8")
                for n in nodes:
                    (stage / "chunks" / (_key(n.id) + ".txt")).read_text(encoding="utf-8")
            idx = {"meta": meta, "mode": mode, "nodes": [self._plain(n) for n in roots]}
            (stage / "index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
        except UnicodeError as exc:
            shutil.rmtree(stage, ignore_errors=True)
            raise TreeError("branch text contains unencodable characters (isolated surrogates?): %s" % exc) from exc
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        bk = self._backup(d)     # the old tree survives until the new one is complete and verified
        try:
            shutil.move(str(stage), str(d))
        except Exception:
            if bk is not None:
                shutil.move(str(bk), str(d))    # put the old tree back: never leave the session empty
            raise
        self._idx_cache.pop(str(d), None)
        self.index(session)
        self._diary("save", session, "%d nodi, mode %s" % (len(nodes), mode))
        return {"nodes": len(nodes), "mode": mode, "dir": str(d)}

    def index(self, session: str) -> Dict[str, Any]:
        d = self._dir(session)
        p = d / "index.json"
        if not p.exists():
            raise TreeError("no tree saved for session %r" % session)
        st = p.stat()
        sig = (st.st_mtime_ns, st.st_size)
        hit = self._idx_cache.get(str(d))
        if hit and hit[0] == sig:
            return hit[1]
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise TreeError("index unreadable for %r: %s" % (session, exc)) from exc
        self._idx_cache[str(d)] = (sig, data)
        return data

    def keys(self, session: str) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        stack = list(self.index(session).get("nodes") or [])
        while stack:
            n = stack.pop()
            out[str(n["id"])] = n
            stack.extend(n.get("children") or [])
        return out

    def load(self, session: str, node_id: str) -> str:
        """The verbatim text of a branch. Raises if it cannot be read: an empty
        branch returns "", a missing one raises. The model must never be handed
        an empty string in place of a failure."""
        info = self.keys(session).get(str(node_id))
        if info is None:
            raise TreeError("branch %r is not in the tree of session %r" % (node_id, session))
        d = self._dir(session)
        name = info["key"] + ".txt"
        try:
            if self.index(session).get("mode") == "zip":
                with zipfile.ZipFile(d / "chunks.zip", "r") as z:
                    return z.read(name).decode("utf-8", "replace")
            return (d / "chunks" / name).read_text(encoding="utf-8")
        except Exception as exc:
            raise TreeError("branch %r exists in the index but cannot be read: %s" % (node_id, exc)) from exc

    @staticmethod
    def _find(nodes: List[Dict[str, Any]], wanted: str,
              trail: List[str]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """Locate a node and return the FULL breadcrumb, ancestors included."""
        for n in nodes:
            here = trail + [str(n.get("label") or n["id"])]
            if str(n["id"]) == wanted:
                return n, here
            got, gp = DocTree._find(n.get("children") or [], wanted, here)
            if got is not None:
                return got, gp
        return None, []

    def vista(self, session: str, node_id: Optional[str] = None, budget_tokens: int = 1200,
              chars_per_token: float = 3.2, offset: int = 0) -> Dict[str, Any]:
        """ONE level of the tree, sized to fit the prompt budget. Python informs.

        Shows the children of ``node_id`` (the roots when None) with their labels.
        What does not fit is COUNTED and declared, never silently dropped, and
        ``next_offset`` lets the model ask for the following page.
        """
        roots = self.index(session).get("nodes") or []
        path: List[str] = []
        level = roots
        if node_id is not None:
            found, path = self._find(roots, str(node_id), [])
            if found is None:
                raise TreeError("branch %r is not in the tree of session %r" % (node_id, session))
            level = found.get("children") or []
        cap = max(200, int(budget_tokens * max(1.0, float(chars_per_token))))
        head = "Percorso: " + (" > ".join(path) if path else "(radice)")
        used = len(head) + 1
        rows: List[str] = []
        i = min(max(0, int(offset)), len(level))
        first = i
        ridotto = False
        while i < len(level):
            n = level[i]
            row = "- id=%s | %s" % (n["id"], n.get("label") or "")
            if n.get("summary"):
                row += " | " + n["summary"]
            row += " | %d token%s" % (int(n.get("tokens") or 0), ", ha figli" if n.get("children") else "")
            if ridotto:
                row = _riga_min(n, cap - used - 1)
                if used + len(row) + 1 > cap:
                    break
            elif used + len(row) + 1 > cap:
                if i > first:
                    break
                row = _riga_min(n, cap - used - 1)
                ridotto = True
            rows.append(row)
            used += len(row) + 1
            i += 1
        left = len(level) - i
        if left:
            rows.append("[%d rami di questo livello non mostrati: offset=%d per la pagina successiva]" % (left, i))
        return {"text": head + "\n" + "\n".join(rows), "shown": len(rows) - (1 if left else 0),
                "omitted": left, "level_size": len(level), "next_offset": i if left else None,
                "path": list(path)}


_STOP = frozenset("""anche allora altro alcuni alcune ancora appena avere circa come contro cosa
della delle dello degli dopo dove essere fatto hanno molto nulla ogni para pelo pela perche quando
quale quali quello questo questa queste questi quelli sono stato sulla sulle sullo suoi their there
these those things through thus were what when where which while will with would""".split())


def _riga_min(n, spazio):
    base = "- id=%s" % n["id"]
    tail = " | %d token%s" % (int(n.get("tokens") or 0), ", ha figli" if n.get("children") else "")
    lab = str(n.get("label") or "")[:80]
    room = spazio - len(base) - len(tail) - 20
    if room < 8 or not lab:
        return base + tail + " [indice ridotto]"
    return base + " | " + lab[:room] + tail + " [indice ridotto]"


def etichetta(text: str, name: str = "", max_len: int = 160) -> Dict[str, str]:
    """What Python can state about a branch WITHOUT inventing anything.

    Code: the top-level def/class names (ast). Prose: first line, the numbers it
    contains, and its most frequent content words. No model call, no guessing.
    """
    s = (text or "").strip()
    if not s:
        return {"label": "(vuoto)", "summary": ""}
    label = ""
    is_code = False
    if (name or "").lower().endswith((".py", ".pyi", ".pyw")):
        try:
            body = ast.parse(s).body
            names = [n.name for n in body
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            if names:
                label = "def/class: " + ", ".join(names[:8])
                is_code = True
        except SyntaxError:
            pass
    if not label:
        for ln in s.split("\n"):
            t = ln.strip().lstrip("#").strip()
            if t:
                label = t[:80]
                break
    nums = list(dict.fromkeys(re.findall(r"\b\d[\d.,/\-]{1,20}\b", s)))[:8]
    freq: Dict[str, int] = {}
    for w in re.findall(r"[A-Za-z\u00c0-\u00ff]{5,}", s.lower()):
        if w not in _STOP:
            freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    parts = []
    if nums:
        parts.append("numeri: " + ", ".join(nums))
    if top and not is_code:
        parts.append("termini: " + ", ".join(w for w, _ in top))
    return {"label": label[:80], "summary": "; ".join(parts)[:max_len]}

_LEGGI = {"type": "function", "function": {
    "name": "leggi_nodo",
    "description": ("Read one branch of the document tree. The text is on disk: only what you "
                    "ask for enters your context. Older branches may be removed to make room, "
                    "and you can read them again."),
    "parameters": {"type": "object", "properties": {
        "id": {"type": "string", "description": "the branch id shown in the index"}, "offset": {"type": "integer", "description": "character offset of the next page (0=start)"}},
        "required": ["id"]}}}

_REGOLE = (
    "Il documento e' un albero su disco, non nel tuo contesto. Qui sotto vedi UN livello. "
    "Per leggere un ramo chiama leggi_nodo(id). Il tuo contesto e' limitato: i rami letti "
    "piu' vecchi vengono rimossi e sostituiti da un avviso, ma restano su disco e puoi "
    "rileggerli. Quando puoi rispondere, rispondi senza chiamare strumenti. "
    "Non inventare il contenuto di un ramo che non hai letto. "
    "Le etichette e i numeri nell'indice sono INDIZI, non il documento: non citare un ramo "
    "come fonte se non lo hai letto con leggi_nodo. Per un fatto del documento devi prima leggere. "
    "L'indice mostra solo una pagina: se un nome non appare, usa cerca_nodo(query) per trovarlo.")


def _msg_tokens(msgs: List[Dict[str, Any]], cpt: float, per_msg: float = 8.0) -> int:
    return int(sum(len(str(m.get("content") or "")) for m in msgs) / cpt + per_msg * len(msgs))


def _evict(msgs: List[Dict[str, Any]], budget: int, cpt: float, per_msg: float = 8.0, question: str = "", cost=None) -> int:
    """Replace OLDER branch contents with a declared stub. Reversible: the text is
    on disk. The NEWEST branch is never removed -- the model just asked for it."""
    last_ai = max((i for i, m in enumerate(msgs) if m.get("role") == "assistant"), default=-1)
    fresh = {i for i, m in enumerate(msgs) if m.get("role") == "tool" and i > last_ai}
    removed = 0
    while (cost(msgs) if cost is not None else _msg_tokens(msgs, cpt, per_msg)) > budget:
        target = None
        for i, m in enumerate(msgs):
            if i not in fresh and m.get("role") == "tool" and not m.get("_stub"):
                target = i
                break
        if target is None:
            break
        nid = msgs[target].get("_node") or ""
        if nid:
            kept = str(msgs[target].get("_facts") or "")
            if question:
                old = str(msgs[target].get("content") or "")
                words = {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ0-9_]{3,}", question)}
                # Complete units only: sentence ends or line breaks, never inside
                # a sentence or a code line, where a cut splits one fact in two.
                units = [u.strip() for u in re.split(r"(?<=[.!?])\s+|\n", old) if u.strip()]
                hit = [any(w in u.lower() for w in words) for u in units]
                skeleton = ("[branch %s evicted from context. Text stays on disk; "
                            "ask leggi_nodo for %s again]" % (nid, nid))
                msgs[target]["content"] = skeleton
                base = cost(msgs) if cost is not None else _msg_tokens(msgs, cpt, per_msg)
                # Spare capacity from the measured cognitive window, not a fixed
                # ceiling: a bigger model or a faster machine keeps more context.
                room = int(max(0, budget - base) * cpt)
                used = sum(len(u) + 1 for u, h in zip(units, hit) if h)
                chosen = []
                for j, (u, h) in enumerate(zip(units, hit)):
                    if h:
                        chosen.append(j)
                    elif used + len(u) + 1 <= room:
                        chosen.append(j)
                        used += len(u) + 1
                # Question-matching units are always kept whole: dropping them
                # would be a real loss, the forced answer has no tools to recover.
                kept = " ".join(x for x in (str(msgs[target].get("_facts") or ""), " ".join(units[j] for j in chosen)) if x)
            keep = (" facts found -> " + kept + ".") if kept else ""
            msgs[target]["content"] = ("[branch %s evicted from context.%s Text stays on disk; "
                                       "ask leggi_nodo for %s again]" % (nid, keep, nid))
        else:
            msgs[target]["content"] = "[esito precedente rimosso per fare spazio; usa cerca_nodo o leggi_nodo se ti serve]"
        msgs[target]["_stub"] = True
        removed += 1
    
    # Second pass: if still over budget, compress older assistant reasoning
    while (cost(msgs) if cost is not None else _msg_tokens(msgs, cpt, per_msg)) > budget:
        # Find the last assistant message to keep it intact
        last_ai = max((i for i, m in enumerate(msgs) if m.get("role") == "assistant"), default=-1)
        target_ai = None
        for i, m in enumerate(msgs):
            if i < last_ai and m.get("role") == "assistant" and not m.get("_archived") and m.get("content"):
                target_ai = i
                break
        
        if target_ai is None:
            break  # Nothing left to compress
            
        original_content = msgs[target_ai].get("content", "")
        original_len = len(original_content)
        msgs[target_ai]["_archived_content"] = original_content
        msgs[target_ai]["content"] = f"[previous reasoning archived; {original_len} chars processed]"
        msgs[target_ai]["_archived"] = True
        removed += 1

    return removed


def _level_ids(tree: "DocTree", session: str, node_id: Optional[str] = None) -> List[str]:
    if node_id is None:
        return [str(n["id"]) for n in (tree.index(session).get("nodes") or [])]
    return [str(c["id"]) for c in (tree.keys(session).get(node_id, {}).get("children") or [])]


_CERCA = {"type": "function", "function": {
    "name": "cerca_nodo",
    "description": "Search ids, labels, summaries AND the verbatim text of every branch. Returns full ids. Use it when what you need is not on the visible page.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}

_SFOGLIA = {"type": "function", "function": {
    "name": "sfoglia_pagina",
    "description": "Show the next page of branches at the current level. Use when the index says more branches are available.",
    "parameters": {"type": "object", "properties": {
        "offset": {"type": "integer", "description": "the offset value from the index message"}},
    "required": ["offset"]}}}



_LEGGI_RAMO = {"type": "function", "function": {
    "name": "leggi_ramo",
    "description": "Read the full content of a branch that was spilled to disk. Use when you see '[content on disk: id=...]' in a message.",
    "parameters": {"type": "object", "properties": {
        "id": {"type": "string", "description": "the branch id from the placeholder message"}},
        "required": ["id"]}}}

def _cerca(tree: "DocTree", session: str, query: str, limit: int = 8) -> Tuple[str, List[str]]:
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

    raw_words = re.findall(r"[a-z0-9à-ù]{3,}", q)
    words: List[str] = []
    for w in raw_words:
        if w in stop:
            continue
        if w not in words:
            words.append(w)
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
    # Cut at the largest consecutive score drop: the boundary comes from
    # this query score distribution, not from a fixed threshold.
    _s = [c[0] for c in candidates]
    _d = [a - b for a, b in zip(_s, _s[1:])]
    if _d and max(_d) > 0:
        candidates = candidates[:_d.index(max(_d)) + 1]
    picked = candidates[:max(1, int(limit))]

    if not picked:
        return "[no branch matches %r. Try another word.]" % query, []

    out = ["%d matches, showing %d. Read a LEAF." % (len(candidates), len(picked))]
    ids: List[str] = []
    for score, _cflag, k, preview, is_container in picked:
        tag = "CONTAINER" if is_container else "LEAF"
        out.append("- %s [%s] score=%d | %s" % (k, tag, score, preview[:160]))
        ids.append(k)
    return "\n".join(out), ids



def _parse_text_tool_calls(text: str, tools_available: list) -> list:
    """Parse tool calls from text content. Models may write <tool_call> as text instead of structured calls."""
    if not text:
        return []
    
    calls = []
    # Pattern 1: <function=name>args</function>
    for tool in tools_available:
        fname = tool.get("function", {}).get("name", "")
        if not fname:
            continue
        # Match <function=leggi_nodo>{"id": "sec_1"}</function> or similar
        pattern = rf'<function={re.escape(fname)}>(.*?)</function>'
        for match in re.finditer(pattern, text, re.DOTALL | re.IGNORECASE):
            try:
                args_str = match.group(1).strip()
                if not args_str:
                    continue
                # Try to parse as JSON
                args = json.loads(args_str)
                calls.append({
                    "id": f"call_{fname}_{len(calls)}",
                    "type": "function",
                    "function": {
                        "name": fname,
                        "arguments": json.dumps(args)
                    }
                })
            except:
                continue
    return calls


def naviga(client: Any, tree: "DocTree", session: str, question: str, *,
           budget_tokens: Optional[int] = None, chars_per_token: float = 3.2,
           max_hops: Optional[int] = None, max_repeats: int = 2, max_tokens: Optional[int] = None,
           temperature: float = 0.2, require_read: bool = True, max_calls: Optional[int] = None) -> Dict[str, Any]:
    """The model navigates, Python informs and enforces the budget.

    ``max_hops`` reads, then ONE final turn with no tools: the model answers with
    what it has, or says it does not know. An invented id is answered with the
    list of real ones, because a small model deduces ids instead of copying them.
    Eviction is declared and reversible: the text never leaves the disk.
    """
    budget = int(budget_tokens or client.working_budget(reserve=0))
    cpt = max(1.0, float(chars_per_token))
    if max_tokens is None:
        max_tokens = matrioska_profile(client)["answer_tokens"]
    try:
        ovh = float(client._hw().get("msg_overhead") or 8.0)
    except Exception:
        ovh = 8.0
    try:
        cog = int(client._cog_stored() or 0) or None
    except Exception:
        cog = None
    meta: Dict[str, Any] = {"hops": 0, "nodes_read": [], "evicted": 0, "repeats": 0,
                            "branches_cut": [], "unknown_ids": [], "forced_answer": False,
                            "answered_from_index": False, "stopped": "", "budget": budget}
    # Effective max_tokens: from measured cognitive window, not a fixed ceiling.
    # Per-turn cap = cog // 8 so a single step never eats the whole context.
    def _eff_max(prompt_tokens: int, is_final: bool) -> int:
        if max_tokens is not None:
            return int(max_tokens)
        ref = cog if cog else budget
        margin = int(ovh * 2)
        residual = ref - int(prompt_tokens) - margin
        cap = max(200, ref // 8) if not is_final else max(200, ref // 4)
        return max(200, min(residual, cap))
    roots = tree.index(session).get("nodes") or []
    focus = None
    if len(roots) == 1 and roots[0].get("children"):
        focus = str(roots[0]["id"])        # bare container: show the useful level immediately
    shown = _level_ids(tree, session, focus)
    vista = tree.vista(session, focus, budget_tokens=_budget_vista(budget, cpt, _tools_tokens(client, tools_now) if "tools_now" in locals() else 0, max_tokens), chars_per_token=cpt)
    toks = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", question))
    named = [k for k in tree.keys(session) if k.rsplit(".", 1)[-1] in toks][:3]
    hint = ("\n\nNomi della domanda presenti nell'albero (id completi): " + ", ".join(named)) if named else ""
    msgs: List[Dict[str, Any]] = [
        {"role": "system", "content": _REGOLE + "\n\n" + vista["text"] + hint},
        {"role": "user", "content": question}]
    seen: Dict[str, int] = {}
    answer = ""
    if max_hops is None: max_hops = max(matrioska_profile(client)["max_hops"], _tree_depth(roots) + max_repeats + 1)
    hops = max(0, int(max_hops))
    if max_calls is None: max_calls = matrioska_profile(client)["max_calls"]
    for turn in range(hops + 1):
        if meta.get("_notice"):
            msgs.append({"role": "user", "content": meta.pop("_notice")})
        final = turn >= hops
        tools_now = None if final else [_LEGGI, _CERCA, _SFOGLIA] + ([_LEGGI_RAMO] if getattr(client, "spill", False) else [])
        tt = _tools_tokens(client, tools_now)
        meta["evicted"] += _evict(msgs, max(200, budget - max_tokens), cpt, ovh, question, cost=lambda ms: client._prompt_tokens(ms, tt))
        try:
            tt = _tools_tokens(client, tools_now)
            pt = client._prompt_tokens(msgs, tt)
        except Exception:
            pt = _msg_tokens(msgs, cpt, ovh) + (256 if tools_now else 0)
        if pt > budget:
            if meta["hops"] > 0 or meta["nodes_read"]:
                meta["stopped"] = "budget: prompt ~%d > %d (forced answer)" % (pt, budget)
                meta["forced_answer"] = True
                try:
                        eff = _eff_max(pt, True)
                        if cog and pt > int(cog * 0.9):
                            meta["evicted"] += _evict(msgs, int(cog * 0.7), cpt, ovh, question,
                                                     cost=lambda ms: client._prompt_tokens(ms, 0))
                        else:
                            meta["evicted"] += _evict(msgs, budget, cpt, ovh, question,
                                                     cost=lambda ms: client._prompt_tokens(ms, 0))
                        r = client.chat_full(messages=msgs, tools=None, temperature=temperature,
                                            max_tokens=eff, continua=False)
                        if getattr(r, "finish_reason", "") == "length":
                            meta["truncated"] = meta.get("truncated", 0) + 1
                        answer = r.text
                except Exception as exc:
                    meta["stopped"] += "; error: %s" % exc
            else:
                meta["stopped"] = "budget: prompt ~%d > %d" % (pt, budget)
            break
        cap = _read_cap(client, msgs, tt, budget, max_tokens if final else 0, max_calls, cpt); meta.setdefault("caps",[]).append(cap)
        if final:
            meta["forced_answer"] = True
        try:
            cs = meta.get("_consecutive_searches", 0)
            if require_read and not meta["nodes_read"] and not final and cs >= 2:
                tc = {"type": "function", "function": {"name": "leggi_nodo"}}
            else:
                tc = "required" if (require_read and not meta["nodes_read"] and not final) else None
            eff = _eff_max(pt, final)
            if cog and pt > int(cog * 0.9):
                meta["evicted"] += _evict(msgs, int(cog * 0.7), cpt, ovh, question,
                                         cost=lambda ms: client._prompt_tokens(ms, tt))
            r = client.chat_full(messages=msgs, tools=tools_now, tool_choice=tc,
                                temperature=temperature, max_tokens=eff, continua=False)
            if getattr(r, "finish_reason", "") == "length":
                meta["truncated"] = meta.get("truncated", 0) + 1
        except Exception as exc:
            err_kind = getattr(exc, "kind", "")
            if err_kind == "cognitive_overflow" and not meta.get("_retry_overflow"):
                meta["_retry_overflow"] = True
                # Tronchiamo l'ultima risposta dell'assistente che ha gonfiato il contesto
                for i in range(len(msgs)-1, -1, -1):
                    if msgs[i].get("role") == "assistant":
                        msgs[i]["content"] = "[RISPOSTA PRECEDENTE TRONCATA PER OVERFLOW. RISCRIVILA IN MODO ESTREMAMENTE CONCISO]"
                        break
                msgs.append({"role": "user", "content": "ERRORE CONTESTO: riscrivi la risposta in massimo 150 caratteri, rispondendo solo a: " + question})
                try:
                    # Secondo giro: payload ridotto artificialmente, gabbia di stima non serve, max_tokens forzato a valore sicuro
                    r = client.chat_full(messages=msgs, tools=None, temperature=temperature, max_tokens=150, continua=False)
                    answer = r.text
                    meta["stopped"] = "retried_short"
                except Exception as exc2:
                    meta["stopped"] = "error: %s (retry fallito)" % exc2
                break
            meta["stopped"] = "error: %s" % exc
            break
        if not r.tool_calls:
            # Check if model wrote tool calls as text instead of structured calls
            text_calls = _parse_text_tool_calls(r.text, tools_now or [])
            if text_calls:
                # Model wrote tool calls as text, execute them
                r.tool_calls = text_calls
            else:
                if require_read and not meta["nodes_read"] and not final and not meta.get("nudged"):
                    meta["nudged"] = True
                    msgs.append({"role": "user", "content": "Non hai letto nessun ramo. L'indice non e' il documento: chiama cerca_nodo o leggi_nodo prima di rispondere."})
                    continue
                answer = r.text
                break
        meta["hops"] += 1
        calls = [c for c in r.tool_calls if str(c.get("function", {}).get("name")) == "cerca_nodo"][:4] + [c for c in r.tool_calls if str(c.get("function", {}).get("name")) != "cerca_nodo"][:max(1, int(max_calls))]
        if len(r.tool_calls) > len(calls):
            meta["deferred"] = meta.get("deferred", 0) + len(r.tool_calls) - len(calls)
            meta["_notice"] = ("[%d calls asked, %d honoured; "
                               "ask the rest one per turn.]" % (len(r.tool_calls), len(calls)))
        msgs.append({"role": "assistant", "content": r.text or "", "tool_calls": calls})
        valid = tree.keys(session)
        reads_turn = 0
        for call in calls:
            try:
                args = json.loads(call.get("function", {}).get("arguments") or "{}")
            except ValueError:
                args = {}
            fname = str(call.get("function", {}).get("name") or "")
            if fname == "cerca_nodo":
                q = str(args.get("query") or args.get("id") or "")
                qn = q.strip().lower()
                cache = meta.setdefault("_search_cache", {})
                if qn in cache:
                    body = "[repeat: %s] ids: %s. Read a LEAF." % (q, cache[qn] or "none")
                    _h = []
                else:
                    body, _h = _cerca(tree, session, q, 4)
                    cache[qn] = ", ".join(_h[:4])
                meta.setdefault("searches", []).append(q)
                consecutive_searches = meta.get('_consecutive_searches', 0) + 1
                meta['_consecutive_searches'] = consecutive_searches
                msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": body, "_node": ""})
                continue
            if fname == "sfoglia_pagina":
                off = int(args.get("offset") or 0)
                sub = tree.vista(session, focus, budget_tokens=_budget_vista(budget, cpt, _tools_tokens(client, tools_now) if "tools_now" in locals() else 0, max_tokens), chars_per_token=cpt, offset=off)
                meta.setdefault("pages_browsed", []).append(off)
                msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": sub["text"], "_node": ""})
                continue
            if fname == "leggi_ramo":
                branch_id = str(args.get("id") or "")
                if not branch_id or not hasattr(client, "_store") or client._store is None:
                    msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": "[branch not available]", "_node": ""})
                    continue
                try:
                    content = client._store.get(branch_id)
                    msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": content, "_node": branch_id})
                except Exception as exc:
                    msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": f"[error reading branch: {exc}]", "_node": ""})
                continue
            if fname in ("leggi_nodo",):
                meta['_consecutive_searches'] = 0  # Reset contatore ricerche consecutive

            if fname not in ("", "leggi_nodo"):
                msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": "[strumento sconosciuto: usa leggi_nodo o cerca_nodo]", "_node": ""})
                continue
            nid = str(args.get("id") or ""); o = max(0, int((re.findall(r"\d+", str(args.get("offset") or 0)) or ["0"])[0]))
            nf = ""
            if not nid:
                meta["empty_ids"] = meta.get("empty_ids", 0) + 1
                sug = ", ".join(named or shown) or "(nessuno)"
                msgs.append({"role": "tool", "tool_call_id": call.get("id") or "",
                             "content": "[id vuoto: chiama leggi_nodo con l'id completo di un ramo, es. %s]" % sug,
                             "_node": ""})
                continue
            if nid not in valid:
                bare = nid.rsplit(".", 1)[-1]
                cand = [k for k in valid if k.rsplit(".", 1)[-1] == bare]
                if len(cand) == 1:
                    meta.setdefault("resolved_names", []).append("%s -> %s" % (nid, cand[0]))
                    nid = cand[0]
                elif len(cand) > 1:
                    meta.setdefault("ambiguous", []).append(nid)
                    msgs.append({"role": "tool", "tool_call_id": call.get("id") or "",
                                 "content": "[nome ambiguo: usa l'id completo, uno di questi: %s]"
                                            % ", ".join(cand[:6]), "_node": nid})
                    continue
            if nid not in valid:
                meta["unknown_ids"].append(nid)
                body = ("[il ramo %r NON ESISTE. Non inventare id: copia uno di questi, che sono "
                        "quelli elencati: %s]" % (nid, ", ".join(shown) or "(nessuno)"))
            elif seen.get((nid, o), 0) >= max_repeats and any((m.get("_node"), m.get("_off", 0))==(nid, o) and not m.get("_stub") for m in msgs):
                meta["repeats"] += 1
                body = ("[hai gia' letto il ramo %s %d volte: non te lo rimando. Usa quello che "
                        "hai, o chiedi un altro ramo.]" % (nid, seen.get((nid, o), 0)))
            elif reads_turn and _msg_tokens(msgs, cpt, ovh) + int(min(cap, int(valid.get(nid, {}).get("chars") or cap)) / cpt) + 8 > max(200, budget - max_tokens):
                meta["deferred"] = meta.get("deferred", 0) + 1
                body = ("[branch %s NOT read: this turn already carries %d branch(es). "
                        "Ask for it again on the next turn.]" % (nid, reads_turn))
            else:
                reads_turn += 1
                try:
                    full = tree.load(session, nid)
                    meta["nodes_read"].append(nid)
                    seen[(nid, o)] = seen.get((nid, o), 0) + 1
                    body = full
                    nf = ", ".join("%s:%s" % (f["tipo"], f["valore"]) for f in trova_fatti(full))
                    if len(body) > cap:
                        body = full[o:o+cap] + (chr(10)+'[%d/%d chars; next leggi_nodo(id=%s, offset=%d)]' % (o+cap, len(full), nid, o+cap))
                        if o+cap >= len(full): body = full[o:] + (chr(10)+'[end of branch %s: %d chars]' % (nid, len(full)))
                        meta["branches_cut"].append(nid)
                    kids = valid.get(nid, {}).get("children")
                    if kids:
                        shown = [str(c["id"]) for c in kids]; focus = nid
                        sub = tree.vista(session, nid, budget_tokens=_budget_vista(budget, cpt, _tools_tokens(client, tools_now) if "tools_now" in locals() else 0, max_tokens),
                                         chars_per_token=cpt)
                        body += ("\n\n[questo ramo e' un contenitore: chiama leggi_nodo con UNO "
                                 "di questi id]\n" + sub["text"])
                    elif not full.strip():
                        body = "[il ramo %s non contiene testo]" % nid
                except TreeError as exc:
                    body = "[ramo non leggibile: %s]" % exc
                    meta.setdefault("unreadable", []).append(nid)
            msgs.append({"role": "tool", "tool_call_id": call.get("id") or "",
                         "content": body, "_node": nid, "_off": o, "_facts": nf})
    if answer and not meta["nodes_read"]:
        meta["answered_from_index"] = True
    if not answer and not meta["stopped"]:
        meta["stopped"] = "no_answer"
    tt = _tools_tokens(client, tools_now)
    meta["evicted"] += _evict(msgs, budget, cpt, ovh, question, cost=lambda ms: client._prompt_tokens(ms, tt))
    return {"text": answer, "meta": meta, "messages": msgs}

_DEFNODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _span(n: ast.AST) -> Tuple[int, int]:
    starts = [n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])]
    return min(starts), int(getattr(n, "end_lineno", n.lineno))


def _sig(n: ast.AST) -> str:
    if isinstance(n, ast.ClassDef):
        return "class " + n.name
    a = n.args
    names = [x.arg for x in list(getattr(a, "posonlyargs", [])) + list(a.args)]
    if a.vararg:
        names.append("*" + a.vararg.arg)
    if a.kwarg:
        names.append("**" + a.kwarg.arg)
    kw = "async def " if isinstance(n, ast.AsyncFunctionDef) else "def "
    return kw + n.name + "(" + ", ".join(names) + ")"


def _calls(n: ast.AST) -> List[str]:
    out: List[str] = []
    for x in ast.walk(n):
        if isinstance(x, ast.Call):
            f = x.func
            nm = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if nm and nm not in out:
                out.append(nm)
    return out


def _nodo(lines: List[str], lo: int, hi: int, body: List[Any], ident: str,
          label: str, ast_node: Any, count: Callable[[str], int]) -> DocNode:
    """Partition by line range: the parent keeps every line no child covers.
    Lossless by construction -- each line belongs to exactly one node."""
    # Lossless: each line in [lo, hi] lands in exactly one node.
    # Spans are computed from the actual text of children, not AST end_lineno,
    # so trailing blank lines are never silently swallowed.
    spans = sorted((_span(n), n) for n in body if isinstance(n, _DEFNODES))
    kids = [_nodo(lines, a, b, getattr(n, "body", []), ident + "." + n.name,
                  _sig(n), n, count) for (a, b), n in spans]
    # Approccio più robusto: ogni figlio occupa esattamente le righe che contiene il suo testo
    covered_real: set = set()
    for k in kids:
        if k._span_real:
            covered_real.update(k._span_real)
    own_lines = [lines[i - 1] for i in range(lo, hi + 1) if i not in covered_real]
    own = "\n".join(own_lines)
    doc = (ast.get_docstring(ast_node) or "") if ast_node is not None else ""
    parts = []
    if doc.strip():
        parts.append(doc.strip().split("\n")[0][:110])
    calls = _calls(ast_node) if ast_node is not None else []
    if calls:
        parts.append("chiama: " + ", ".join(calls))
    node = DocNode(id=ident, label=label[:110], summary="; ".join(parts)[:200],
                   text=own, tokens=count(own), children=kids)
    node._doc = doc.strip().split("\n")[0][:110] if doc.strip() else ""
    node._span_real = list(range(lo, hi + 1))
    node._raw_calls = calls
    return node


def albero_codice(path: Any, counter: Optional[Callable[[str], int]] = None) -> List[DocNode]:
    """Build a tree from Python source with ast. NOTHING is compressed: every line
    of every file lands verbatim in exactly one node. Labels are real signatures,
    summaries carry the docstring's first line and the names the node calls, so the
    model follows dependencies instead of guessing. No model call, no invention.
    """
    count = counter or (lambda t: int(len(t) / 3.2) + 1 if t else 0)
    root = Path(path)
    files = sorted(root.rglob("*.py")) if root.is_dir() else [root]
    mods: List[DocNode] = []
    for f in files:
        src = f.read_text(encoding="utf-8", errors="replace")
        lines = src.split("\n")
        try:
            mod = ast.parse(src)
        except SyntaxError as exc:
            mods.append(DocNode(id=f.stem, label="%s (NON ANALIZZABILE: %s)" % (f.name, exc),
                                text=src, tokens=count(src)))
            continue
        rel = f.stem if not root.is_dir() else ".".join(f.relative_to(root).with_suffix("").parts)
        mods.append(_nodo(lines, 1, len(lines), mod.body, rel, rel + " (" + f.name + ")", mod, count))
    roots = [DocNode(id=root.name, label="package " + root.name, children=mods)] if root.is_dir() else mods
    _filtra_chiama(roots)
    return roots

def _filtra_chiama(roots: List[DocNode]) -> None:
    """Keep only calls that are real nodes: every name listed must be reachable."""
    nodes = list(_walk(roots))
    known = {n.id.rsplit(".", 1)[-1] for n in nodes}
    for n in nodes:
        raw = getattr(n, "_raw_calls", None)
        if raw is None:
            continue
        useful = [c for c in raw if c in known]
        parts = []
        if getattr(n, "_doc", ""):
            parts.append(n._doc)
        if useful:
            shown = useful[:8]
            txt = "chiama: " + ", ".join(shown)
            if len(useful) > len(shown):
                txt += " (+%d altri)" % (len(useful) - len(shown))
            parts.append(txt)
        n.summary = "; ".join(parts)[:200]

_FATTO = (
    ("codice", re.compile(r"\b[A-Za-z0-9]{2,}(?:[-_][A-Za-z0-9]{1,8})+\b")),
    ("sigla", re.compile(r"\b[A-Z]{3,}\d{1,6}\b")),
    ("numero", re.compile(r"\b\d{4,}\b")),
    ("nome", re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b")),
    ("misura", re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:terawatt|gigawatt|megawatt|kilowatt|watt|TB|GB|MB|GHz|MHz|volt|ampere)\b", re.I)),
    ("chiave", re.compile(r"\b[A-Za-z0-9_\-]{16,}\b")),
    ("virgolette", re.compile(r'"([^"\n]{3,60})"')),
    ("label", re.compile(r"\b(?:password|pwd|segreto|secret|chiave|token|pin)\s*(?:[:=]{1,2}|(?:e|è|is)\b)\s*[\x22\x27]?([A-Za-z0-9_\-]+)", re.I)),
)


def trova_fatti(testo: str, max_per_tipo: Optional[int] = None, contesto: int = 90) -> List[Dict[str, Any]]:
    """Exhaustive deterministic scan for candidate FACTS, with their context.

    Python reads EVERY character (cheap, lossless) and hands the model a small
    candidate set to judge: nothing is compressed, nothing is dropped in silence.
    Each hit carries its position and the words around it, so a fact can be
    matched to a question -- and verified -- without reading the document.
    """
    testo = testo or ""

    out: List[Dict[str, Any]] = []
    seen: set = set()
    for tipo, rx in _FATTO:
        n = 0
        for m in rx.finditer(testo):
            v = (m.group(1) if m.groups() else m.group(0)).strip()
            if not v or (tipo, v) in seen:
                continue
            if tipo == "chiave" and not (any(c.isdigit() for c in v) and any(c.isalpha() for c in v)):
                continue                      # an API key mixes letters and digits; a long word does not
            seen.add((tipo, v))
            a, b = max(0, m.start() - contesto), min(len(testo), m.end() + 40)
            out.append({"tipo": tipo, "valore": v, "pos": m.start(),
                        "percentuale": round(100.0 * m.start() / max(1, len(testo)), 1),
                        "contesto": " ".join(testo[a:b].split())})
            n += 1
            if max_per_tipo is not None and n >= max_per_tipo: break
    out.sort(key=lambda d: d["pos"])
    return out


def _fatti_in_range(tutti_i_fatti, start, end, signal_rank, tetto_fatti):
    """Blocco 'CHIAVE -> ...' con i fatti (ordinati per rarita') in [start, end)."""
    fatti = [
        "%s:%s" % (f["tipo"], f["valore"])
        for f in tutti_i_fatti
        if start <= f["pos"] < end
    ]
    if not fatti:
        return ""
    fatti.sort(key=lambda v: signal_rank.get(v.split(":", 1)[0], 99))
    visibili, usati = [], 0
    for f in fatti:
        f = f if len(f) <= 80 else f[:77] + "..."
        if visibili and usati + len(f) + 2 > tetto_fatti:
            break
        visibili.append(f)
        usati += len(f) + 2
    blocco = "CHIAVE -> " + ", ".join(visibili)
    resto = len(fatti) - len(visibili)
    if resto:
        blocco += " (+%d altri nel ramo)" % resto
    return blocco


def prepara_albero_ricco(documento: str, sessione: str, tree: Optional["DocTree"] = None, 
                          max_chars: int = 1500, max_per_tipo: Optional[int] = None, tetto_fatti: Optional[int] = None, mode="auto", max_children=None, client=None) -> Tuple["DocTree", str]:
    """Costruisce un albero con summary arricchiti dai fatti deterministici.
    
    Chunka il documento, estrae tutti i fatti con trova_fatti(), e per ogni chunk
    inserisce nel summary i fatti che cadono in quel range. Questo rende i fatti
    visibili nell'indice senza dover aprire i rami.
    
    Args:
        documento: testo completo da indicizzare
        sessione: nome della sessione per DocTree
        tree: DocTree esistente (se None, usa ~/.cache/bocconcini/workspace)
        max_chars: dimensione massima dei chunk
        max_per_tipo: per-type extraction cap. None (default) extracts every
            fact; a number truncates each type globally, dropping facts that
            appear late in the document.
        tetto_fatti: max characters of the fact block in each summary. None
            (default) derives it from matrioska_profile(client): the fact part
            of one index row is 4 * max_facts_per_summary tokens, converted with
            the calibrated chars_per_token. An explicit value is honoured.
            Facts are ordered by GLOBAL RARITY of their type: a type with 4 hits in
            the document is signal, one with 100 hits is noise, so rare types are
            rendered first. What does not fit is counted and declared, never dropped
            in silence; the verbatim text of every branch stays on disk.
    
    Returns:
        (tree, sessione) - il tree con l'albero salvato
    
    Example:
        >>> import bocconcini as b
        >>> import bocconcini.memory as t
        >>> tree, session = t.prepara_albero_ricco(documento_enorme, "test")
        >>> risultato = t.naviga(client, tree, session, domanda, budget_tokens=1500)
    """
    if tree is None:
        tree = DocTree()
    
    # Cap derived from the measured profile, never a fixed ceiling.
    # matrioska_profile prices one index row as 28 + 4 * max_facts tokens,
    # so the fact part of a row is 4 * max_facts tokens, in calibrated chars.
    prof = matrioska_profile(client)
    cpt = max(2.0, float(prof.get('chars_per_token') or 3.2))
    if tetto_fatti is None:
        tetto = int(4 * int(prof['max_facts_per_summary']) * cpt)
    else:
        tetto = int(tetto_fatti)
    tetto = max(1, tetto)

    # 1. Chunking del documento
    chunks = split_text(documento, name="documento.txt", kind="text", 
                       max_chars=max_chars, max_tokens=10000, min_chars=300, overlap=0)
    
    # 2. Estrazione deterministica di tutti i fatti
    tutti_i_fatti = trova_fatti(documento, max_per_tipo=max_per_tipo)
    fact_counts = {}
    for f in tutti_i_fatti:
        fact_counts[f["tipo"]] = fact_counts.get(f["tipo"], 0) + 1
    signal_rank = {t: i for i, t in enumerate(sorted(fact_counts, key=lambda t: (fact_counts[t], t)))}
    
    # 3. Costruzione dei nodi con summary arricchiti
    roots = []
    for i, ch in enumerate(chunks):
        node_id = f"sec_{i:03d}"
        
        # Etichetta standard
        meta_etichetta = etichetta(ch.text, name="documento.txt")
        
        # Trova i fatti che cadono in questo chunk
        fatti_nel_chunk = [
            f"{f['tipo']}:{f['valore']}" 
            for f in tutti_i_fatti 
            if ch.start <= f['pos'] < ch.end
        ]
        
        # Arricchisci il summary
        # Rarest fact types first: 100 hits of a type is noise, 4 hits is signal.
        fatti_nel_chunk.sort(key=lambda v: signal_rank.get(v.split(":", 1)[0], 99))
        summary_base = meta_etichetta["summary"]
        extra_leaves = []
        if fatti_nel_chunk:
            # Split into blocks that each fit the derived cap: nothing is dropped,
            # every overflow block becomes its own leaf after this section.
            blocks, cur, used = [], [], 0
            for f in fatti_nel_chunk:
                f = f if len(f) <= 80 else f[:77] + "..."
                if cur and used + len(f) + 2 > tetto:
                    blocks.append(cur)
                    cur, used = [f], len(f) + 2
                else:
                    cur.append(f)
                    used += len(f) + 2
            if cur:
                blocks.append(cur)
            block = "CHIAVE -> " + ", ".join(blocks[0])
            resto = len(fatti_nel_chunk) - len(blocks[0])
            if resto:
                block += " (+%d altri nel ramo)" % resto
            summary_base = block + (" | " + summary_base if summary_base else "")
            for n, blk in enumerate(blocks[1:], start=1):
                body = "CHIAVE -> " + ", ".join(blk)
                extra_leaves.append(DocNode(
                    id="%s_facts_%d" % (node_id, n),
                    label="Facts %d of section %d (pos %d-%d)" % (n, i, ch.start, ch.end),
                    summary=body,
                    text=body,
                    tokens=max(1, int(len(body) / cpt)),
                ))

        roots.append(DocNode(
            id=node_id,
            label=f"Sezione {i} (pos {ch.start}-{ch.end})",
            summary=summary_base,
            text=ch.text,
            tokens=ch.token_count_estimate()
        ))
        roots.extend(extra_leaves)

    # 4. Salvataggio dell'albero
    # --- Matriosca: raggruppa le foglie in macro-blocchi padre->figli ---
    if max_children is None:
        max_children = int(prof.get("max_children", 8))
    max_children = max(2, int(max_children))
    if mode in ("matriosca", "auto"):
        level = 0
        while len(roots) > max_children:
            level += 1
            parents = []
            for g in range(0, len(roots), max_children):
                gruppo = roots[g:g + max_children]
                # Facts come from the children summaries, never from positional
                # chunk indices: extra fact leaves must not shift the spans.
                seen = []
                for c in gruppo:
                    if "CHIAVE -> " in (c.summary or ""):
                        blk = c.summary.split("CHIAVE -> ", 1)[1].split(" | ", 1)[0]
                        blk = blk.split(" (+", 1)[0]
                        for v in blk.split(","):
                            v = v.strip()
                            if v and v not in seen:
                                seen.append(v)
                seen.sort(key=lambda v: signal_rank.get(v.split(":", 1)[0], 99))
                block = ""
                if seen:
                    shown, used = [], 0
                    for v in seen:
                        if shown and used + len(v) + 2 > tetto:
                            break
                        shown.append(v)
                        used += len(v) + 2
                    block = "CHIAVE -> " + ", ".join(shown)
                    if len(seen) > len(shown):
                        block += " (+%d altri nel ramo)" % (len(seen) - len(shown))
                if not block:
                    parts = [c.summary for c in gruppo if c.summary]
                    if parts:
                        block = " | ".join(parts)
                        if len(block) > tetto * 2:
                            block = block[:tetto * 2 - 3] + "..."
                ordinals = [int(c.id[4:7]) for c in gruppo
                            if c.id.startswith("sec_") and c.id[4:7].isdigit()]
                if ordinals:
                    span_label = "sezioni %d-%d" % (min(ordinals), max(ordinals))
                else:
                    span_label = "%s ... %s" % (gruppo[0].label.split("(")[0].strip(),
                                        gruppo[-1].label.split("(")[0].strip())
                nid = "macro_%02d" % (g // max_children)
                if level > 1:
                    nid = "macro_l%d_%02d" % (level, g // max_children)
                parents.append(DocNode(
                    id=nid,
                    label="Macro-block %d (%s)" % (g // max_children, span_label),
                    summary=block,
                    text="",
                    tokens=sum(c.tokens for c in gruppo),
                    children=gruppo,
                ))
            roots = parents
    tree.save(sessione, roots)
    
    return tree, sessione


def calibra_navigazione(client, max_profondita=10, budget_tokens=1500,
                         session_prefix="calib_naviga") -> int:
    """Misura quanti livelli di profondita' il modello riesce a navigare prima di perdere il filo.

    Costruisce alberi lineari di profondita' crescente. L'ago (un codice) e' sempre
    nell'ultimo nodo. Per ogni profondita', naviga() deve trovarlo. Quando smette di
    trovarlo, quella e' la profondita' limite.

    Returns: la profondita' massima navigata con successo (0 = nessuna).
    """
    limite = 0
    for prof in range(1, max_profondita + 1):
        ago = "%04d" % (int.from_bytes(os.urandom(2), "big") % 9000 + 1000)
        nodo = None
        for i in range(prof - 1, -1, -1):
            if i == prof - 1:
                nodo = DocNode(id="sec_%03d" % i, label="Sezione %d" % i,
                              summary="Contiene un codice di verifica",
                              text="Il codice di verifica e' %s." % ago)
            else:
                nodo = DocNode(id="sec_%03d" % i, label="Sezione %d" % i,
                              summary="Contenitore, ha un sotto-ramo",
                              text="Questa sezione rimanda al suo sotto-ramo.",
                              children=[nodo])
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tree = DocTree(Path(td))
            session = "%s_%d" % (session_prefix, prof)
            tree.save(session, [nodo])
            out = naviga(client, tree, session,
                        "Qual e' il codice di verifica?",
                        budget_tokens=budget_tokens, max_hops=prof + 2)
            if ago in out.get("text", ""):
                limite = prof
            else:
                break
    return limite


def _ask_windows(client,wins,tg,question,max_tokens,temperature,room):
    out,calls,biggest=[],0,0
    for batch in _fit_batches(wins,room):
            p = ("ORIGINAL REQUEST: " + str(question) + "\n\n"
                            + "VERBATIM EXCERPTS (from the document):\n"
                            + "\n".join("- " + w for w in batch) + "\n\n"
                            + "Find the SPECIFIC value for '" + str(tg) + "' in the excerpts above. "
                            + "The excerpts were selected because they concern the target; wording may differ (paraphrase, identifiers, underscores). The value is typically a code, number, date, name, or status "
                            + "associated with '" + str(tg) + "'. "
                            + "Copy the exact text character by character. Do not paraphrase or invent.\n"
                            + "If you cannot find a clear value for '" + str(tg) + "', reply exactly: NOT FOUND\n"
                            + "Answer with the copied value only (no explanation, no preamble, no quotes).")

            biggest = max(biggest, len(p))
            r = client.chat_full(prompt=p, max_tokens=max_tokens,
                                 temperature=temperature, continua=False)
            calls += 1
            out.append((tg, (r.text or "").strip()))
    return out,calls,biggest


def ask_stepwise(client, documento: str, question: str, *, targets=None,
                 max_tokens: Optional[int] = None, window: Optional[int] = None, per_target: Optional[int] = None,
                 temperature: float = 0.0) -> Dict[str, Any]:
    """One target at a time, each in a FRESH context. Python keeps the findings.

    The model never has to remember what it already did: every sub-task starts
    with an empty history and sees only the verbatim windows for ITS target.
    The answers accumulate outside the model, so nothing is ever evicted.
    """
    low = documento.lower()
    if max_tokens is None:
        max_tokens = matrioska_profile(client)["answer_tokens"]
    if window is None:
        frasi = [len(f) for f in documento.split('.') if len(f) > 10]
        avg_frase = sum(frasi) // max(1, len(frasi)) if frasi else 100
        window = max(100, avg_frase * 2)
    if per_target is None:
        per_target = float('inf')
    if not targets:
        r = client.chat_full(prompt=("List the distinct items to find in this request, "
                                     "one per line, no numbering, no explanation.\nRequest: "
                                     + question), max_tokens=60, temperature=0.0, continua=False)
        targets = [ln.strip(" -\t0123456789.") for ln in (r.text or "").splitlines()]
        targets = [x for x in targets if 2 < len(x) <= 40][:8]
    findings, calls, biggest = [], 0, 0
    _p=matrioska_profile(client)
    _tl=[_LEGGI,_CERCA,_SFOGLIA]+([_LEGGI_RAMO] if getattr(client,"spill",False) else [])
    room=max(64,_p["usable_budget"]+furniture_tokens(client,_tl)-furniture_tokens(client,[])-int(max_tokens))
    rc=int(room*_p["chars_per_token"])
    for tg in targets:
        q = str(tg).lower().strip()
        wins, start = [], 0
        # Hard limit: la finestra NON DEVE MAI sforare il budget cognitivo
        hard_limit = max(window, min(int(max_tokens * 4.0 * 1.5), window * 8))
        hard_limit=max(80,min(hard_limit,rc))
        # Tetto adattivo basato sulla frequenza della parola nel testo
        freq = low.count(q)
        per_target_eff = per_target if freq <= 8 else max(3, min(per_target, int(len(documento) / max(1, freq * 100))))
        while len(wins) < per_target_eff:
            k = low.find(q, start)
            # Ricerca fuzzy: estraggo parole chiave e cerco quelle
            if k < 0:
                words = [w for w in re.findall(r"[a-z0-9à-ù]{3,}", q) if w not in {"del", "di", "il", "la", "le", "che", "per", "con", "una", "uno"}]
                if words:
                    k = low.find(words[0], start)
                    if k >= 0:
                        nearby = low[max(0, k-200):k+200]
                        if not all(w in nearby for w in words[1:]):
                            k = -1
            if k < 0:
                break
            
            # 1. Confini naturali (frase/paragrafo)
            a_nat, b_nat = k, k + len(q)
            while a_nat > 0 and documento[a_nat-1] not in ".!?\n": a_nat -= 1
            while b_nat < len(documento) and documento[b_nat] not in ".!?\n": b_nat += 1
            
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
                    
            wins.append(documento[a:b].replace("\n", " "))
            start = k + len(q)
        if not wins:
            findings.append((tg, "NOT FOUND"))
            continue
        wins = list(dict.fromkeys(wins))
        v,n,g=_ask_windows(client,wins,tg,question,max_tokens,temperature,room)
        calls+=n;biggest=max(biggest,g);findings.extend(v)

    # Filter NOT FOUND and present only found values
    found = [(k, v) for k, v in findings if v != "NOT FOUND" and v.strip() != ""]
    found=list(dict.fromkeys(found))
    if not found:
        return {"text": "NOT FOUND", "meta": {"targets": list(targets), "findings": findings,
                                               "sub_calls": calls, "biggest_prompt_chars": biggest,
                                               "found_count": 0, "not_found_count": len(targets)}}

    not_found_count = len(findings) - len(found)
    righe = "\n".join(f"- {k}: {v}" for k, v in found)

    # Build the synthesis prompt with explicit context
    p = ("ORIGINAL REQUEST: " + str(question) + "\n\n"
         + "EXTRACTED VALUES:\n" + righe + "\n\n")
    if not_found_count > 0:
        p += ("Note: " + str(not_found_count) + " target(s) had no clear associated value "
              + "in the document.\n")
    p += ("Using ONLY the extracted values above, answer the original request.\n"
          + "If the values are sufficient, provide a complete answer.\n"
          + "If the values are insufficient, say 'INSUFFICIENT DATA' and explain what is missing.\n"
          + "Do not invent values that are not in the extracted list.")
    biggest = max(biggest, len(p))
    synth_tokens = max(max_tokens or matrioska_profile(client)["answer_tokens"], len(targets) * 20 + 100)
    r = client.chat_full(prompt=p, max_tokens=synth_tokens, temperature=temperature, continua=False)
    return {"text": r.text or "", "meta": {"targets": list(targets), "findings": findings,
                                            "sub_calls": calls + 1, "biggest_prompt_chars": biggest,
                                            "found_count": len(found), "not_found_count": not_found_count}}


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
    tl = [_LEGGI, _CERCA, _SFOGLIA] + ([_LEGGI_RAMO] if getattr(client, "spill", False) else [])
    reserve = furniture_tokens(client, tl) + int(overhead * 8)
    usable = max(384, int(raw) - reserve)
    index_budget = max(160, usable // 4)
    max_facts = max(3, index_budget // 120)
    row_cost = 28 + 4 * max_facts
    max_children = max(3, index_budget // max(24, row_cost))
    leaf_tokens = max(180, int(usable * 0.35))
    leaf_chars = int(leaf_tokens * max(2.0, float(chars_per_token)))
    answer_tokens = max(120, usable // 4)
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
    max_children = max(2, int(max_children))
    chunks = split_text(document, name="document.txt", kind="text",
                        max_chars=leaf_max_chars, max_tokens=leaf_max_tokens,
                        min_chars=300, overlap=0)
    all_facts = trova_fatti(document)
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
                fact_counter = Counter(container_facts)
                unique_facts = list(fact_counter.keys())
            unique_facts.sort(key=lambda v: signal_rank.get(v.split(":", 1)[0], 99))
            container_summary = ""
            if unique_facts:
                visible = unique_facts[:max_facts_per_summary]
                visible_with_counts = [f"{v} ({fact_counter[v]}x)" if fact_counter[v] > 1 else v for v in visible]
                block = "KEY -> " + ", ".join(visible_with_counts)
                resto = len(unique_facts) - len(visible)
                if resto: block += " (+%d more in sub-branches)" % resto
                container_summary = block
            container = DocNode(id=container_id, label=container_label, summary=container_summary,
                                text="", tokens=sum(c.tokens for c in group), children=group)
            next_level.append(container)
        current_level = next_level
    tree.save(session, current_level)
    return tree, session


def _read_cap(client, msgs, tt, budget, answer, pages, cpt):
    room = int(budget) - client._prompt_tokens(msgs, tt) - max(0, int(answer))
    return max(1, int(room / max(1, int(pages)) * float(cpt)))


def _tools_tokens(client, tools):
    if not tools:
        return 0
    s = json.dumps(tools, ensure_ascii=False)
    return int(getattr(client,"_exact_content",lambda x:0)(s) or (len(s) / 2.5 + 1))


def _budget_vista(budget: int, cpt: float, tools_tokens: int, max_tokens: int) -> int:
    """Calculate vista budget from real components, not fixed fractions.
    Equation: budget - rules_tokens - tools_tokens - per_needle_cost - answer_reserve
    All values derived from measurements, not ceilings."""
    rules_chars = 651  # measured: len(_REGOLE)
    rules_tokens = max(1, int(rules_chars / cpt))
    per_needle_cost = 700  # measured: ~700 token per needle (search + leaf)
    return max(150, budget - rules_tokens - tools_tokens - per_needle_cost - max_tokens)

def _fit_batches(wins, room):
    """Pack windows into batches that fit room tokens. Nothing is dropped."""
    out, cur, used = [], [], 0
    for w in wins:
        n = estimate_tokens(w)
        if cur and used + n > room:
            out.append(cur); cur, used = [], 0
        cur.append(w); used += n
    if cur:
        out.append(cur)
    return out

def _tok_path():
    return Path(os.environ.get('BOCCONCINI_CACHE',str(Path.home()/'.cache'/'bocconcini')))/'token_costs.json'
def _tok_read():
    try: return json.loads(_tok_path().read_text('utf-8')).get('entries',{})
    except Exception: return {}
def _tok_store(k,v):
    try:
        p=_tok_path(); p.parent.mkdir(parents=True,exist_ok=True)
        d={'version':1,'entries':_tok_read()}; d['entries'][k]=int(v)
        t=p.with_suffix('.tmp'); t.write_text(json.dumps(d),'utf-8'); os.replace(t,p)
    except Exception: pass
def furniture_tokens(client,tools):
    import hashlib
    s=json.dumps(tools,ensure_ascii=False)
    try: k=client._hw_key()
    except Exception: k=''
    k+='|'+hashlib.blake2b((_REGOLE+'\x00'+s).encode('utf-8','replace'),digest_size=8).hexdigest()
    e=_tok_read().get(k)
    if e is not None: return int(e)
    try: r=client._exact_content(_REGOLE); q=client._exact_content(s)
    except Exception: r=q=None
    if r is not None and q is not None:
        _tok_store(k,int(r)+int(q)); return int(r)+int(q)
    return estimate_tokens(_REGOLE)+estimate_tokens(s,'json')

def _tree_depth(roots):
    """Maximum depth measured from the tree structure; no model calls."""
    seen=set(); stack=[(r,1) for r in roots]; best=0
    while stack:
        n,d=stack.pop(); nid=str(n.get("id",""))
        if nid in seen: continue
        seen.add(nid); best=max(best,d)
        stack.extend((c,d+1) for c in (n.get("children") or []))
    return best
