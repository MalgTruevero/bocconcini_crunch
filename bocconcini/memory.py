"""bocconcini_memory - verbatim chunks on disk, only the index in RAM.

Standard library only. Python informs (structure, labels), the model decides
(which branch to read). Nothing here calls a model or a server.
"""
from __future__ import annotations
import ast, hashlib, json, os, re, shutil, time, zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from .client import split_text
__all__ = ["DocNode", "DocTree", "TreeError", "etichetta", "naviga", "albero_codice", "trova_fatti", "prepara_albero_ricco", "calibra_navigazione"]
_MAX_BACKUPS = 50
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
        "id": {"type": "string", "description": "the branch id shown in the index"}},
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


def _evict(msgs: List[Dict[str, Any]], budget: int, cpt: float, per_msg: float = 8.0, question: str = "") -> int:
    """Replace OLDER branch contents with a declared stub. Reversible: the text is
    on disk. The NEWEST branch is never removed -- the model just asked for it."""
    last_ai = max((i for i, m in enumerate(msgs) if m.get("role") == "assistant"), default=-1)
    fresh = {i for i, m in enumerate(msgs) if m.get("role") == "tool" and i > last_ai}
    removed = 0
    while _msg_tokens(msgs, cpt, per_msg) > budget:
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
            if not kept and question:
                old = str(msgs[target].get("content") or "")
                words = {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ0-9_]{3,}", question)}
                parts = re.split(r"(?<=[.!?])\s+", old)
                kept = " ".join(seg.strip() for seg in parts if any(w in seg.lower() for w in words))[:180]
            keep = (" facts found -> " + kept + ".") if kept else ""
            msgs[target]["content"] = ("[branch %s evicted from context.%s Text stays on disk; "
                                       "ask leggi_nodo for %s again]" % (nid, keep, nid))
        else:
            msgs[target]["content"] = "[esito precedente rimosso per fare spazio; usa cerca_nodo o leggi_nodo se ti serve]"
        msgs[target]["_stub"] = True
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


def _cerca(tree: "DocTree", session: str, query: str, limit: int = 8) -> Tuple[str, List[str]]:
    """Search ids, labels, summaries AND the verbatim text of every branch.
    Ids/labels alone made the tool useless: a word present in the document was
    reported as absent. Python reads the disk, the model only receives ids."""
    q = (query or "").strip().lower()
    if not q:
        return "[empty query]", []
    keys = tree.keys(session)
    order = sorted(keys)
    hits = [k for k in order if q in k.lower()
            or q in str(keys[k].get("label", "")).lower()
            or q in str(keys[k].get("summary", "")).lower()][:limit]
    for k in order:
        if len(hits) >= limit:
            break
        if k in hits:
            continue
        try:
            if q in tree.load(session, k).lower():
                hits.append(k)
        except TreeError:
            continue
    if not hits:
        alt = re.sub(r"^[a-z]+\s*[:\s]\s*", "", q).strip()
        if alt and alt != q:
            return _cerca(tree, session, alt, limit)
    if not hits:
        return "[no branch matches %r. Try another word.]" % query, []
    return ("Matching branches (call leggi_nodo with the full id):\n"
            + "\n".join("- " + k for k in hits)), hits


def naviga(client: Any, tree: "DocTree", session: str, question: str, *,
           budget_tokens: Optional[int] = None, chars_per_token: float = 3.2,
           max_hops: int = 3, max_repeats: int = 2, max_tokens: int = 400,
           temperature: float = 0.2, require_read: bool = True, max_calls: int = 1) -> Dict[str, Any]:
    """The model navigates, Python informs and enforces the budget.

    ``max_hops`` reads, then ONE final turn with no tools: the model answers with
    what it has, or says it does not know. An invented id is answered with the
    list of real ones, because a small model deduces ids instead of copying them.
    Eviction is declared and reversible: the text never leaves the disk.
    """
    budget = int(budget_tokens or 1200)
    cpt = max(1.0, float(chars_per_token))
    try:
        ovh = float(client._hw().get("msg_overhead") or 8.0)
    except Exception:
        ovh = 8.0
    cap = max(300, int(budget * cpt * 0.5))
    meta: Dict[str, Any] = {"hops": 0, "nodes_read": [], "evicted": 0, "repeats": 0,
                            "branches_cut": [], "unknown_ids": [], "forced_answer": False,
                            "answered_from_index": False, "stopped": "", "budget": budget}
    roots = tree.index(session).get("nodes") or []
    focus = None
    if len(roots) == 1 and roots[0].get("children"):
        focus = str(roots[0]["id"])        # bare container: show the useful level immediately
    shown = _level_ids(tree, session, focus)
    vista = tree.vista(session, focus, budget_tokens=max(150, budget // 4), chars_per_token=cpt)
    toks = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", question))
    named = [k for k in tree.keys(session) if k.rsplit(".", 1)[-1] in toks][:3]
    hint = ("\n\nNomi della domanda presenti nell'albero (id completi): " + ", ".join(named)) if named else ""
    msgs: List[Dict[str, Any]] = [
        {"role": "system", "content": _REGOLE + "\n\n" + vista["text"] + hint},
        {"role": "user", "content": question}]
    seen: Dict[str, int] = {}
    answer = ""
    hops = max(0, int(max_hops))
    for turn in range(hops + 1):
        if meta.get("_notice"):
            msgs.append({"role": "user", "content": meta.pop("_notice")})
        final = turn >= hops
        tools_now = None if final else [_LEGGI, _CERCA]
        meta["evicted"] += _evict(msgs, max(200, budget - 256), cpt, ovh, question)
        try:
            tt = int(len(json.dumps(tools_now, ensure_ascii=False)) / 2.5) + 1 if tools_now else 0
            pt = client._prompt_tokens(msgs, tt)
        except Exception:
            pt = _msg_tokens(msgs, cpt, ovh) + (256 if tools_now else 0)
        if pt > budget:
            meta["stopped"] = "budget: prompt ~%d > %d" % (pt, budget)
            break
        if final:
            meta["forced_answer"] = True
        try:
            tc = "required" if (require_read and not meta["nodes_read"] and not final) else None
            r = client.chat_full(messages=msgs, tools=tools_now, tool_choice=tc,
                                 temperature=temperature, max_tokens=max_tokens, continua=False)
        except Exception as exc:
            meta["stopped"] = "error: %s" % exc
            break
        if not r.tool_calls:
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
                body, _h = _cerca(tree, session, q, 8)
                meta.setdefault("searches", []).append(q)
                msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": body, "_node": ""})
                continue
            if fname not in ("", "leggi_nodo"):
                msgs.append({"role": "tool", "tool_call_id": call.get("id") or "", "content": "[strumento sconosciuto: usa leggi_nodo o cerca_nodo]", "_node": ""})
                continue
            nid = str(args.get("id") or "")
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
            elif seen.get(nid, 0) >= max_repeats:
                meta["repeats"] += 1
                body = ("[hai gia' letto il ramo %s %d volte: non te lo rimando. Usa quello che "
                        "hai, o chiedi un altro ramo.]" % (nid, seen.get(nid, 0)))
            elif reads_turn and _msg_tokens(msgs, cpt, ovh) + int(min(cap, int(valid.get(nid, {}).get("chars") or cap)) / cpt) + 8 > max(200, budget - 256):
                meta["deferred"] = meta.get("deferred", 0) + 1
                body = ("[branch %s NOT read: this turn already carries %d branch(es). "
                        "Ask for it again on the next turn.]" % (nid, reads_turn))
            else:
                reads_turn += 1
                try:
                    full = tree.load(session, nid)
                    meta["nodes_read"].append(nid)
                    seen[nid] = seen.get(nid, 0) + 1
                    body = full
                    nf = ", ".join("%s:%s" % (f["tipo"], f["valore"]) for f in trova_fatti(full, max_per_tipo=6))[:180]
                    if len(body) > cap:
                        body = full[:cap] + ("\n[ramo tagliato: %d caratteri su %d. Per il resto "
                                             "chiedi un ramo piu' specifico.]" % (cap, len(full)))
                        meta["branches_cut"].append(nid)
                    kids = valid.get(nid, {}).get("children")
                    if kids:
                        shown = [str(c["id"]) for c in kids]
                        sub = tree.vista(session, nid, budget_tokens=max(120, budget // 4),
                                         chars_per_token=cpt)
                        body += ("\n\n[questo ramo e' un contenitore: chiama leggi_nodo con UNO "
                                 "di questi id]\n" + sub["text"])
                    elif not full.strip():
                        body = "[il ramo %s non contiene testo]" % nid
                except TreeError as exc:
                    body = "[ramo non leggibile: %s]" % exc
                    meta.setdefault("unreadable", []).append(nid)
            msgs.append({"role": "tool", "tool_call_id": call.get("id") or "",
                         "content": body, "_node": nid, "_facts": nf})
    if answer and not meta["nodes_read"]:
        meta["answered_from_index"] = True
    if not answer and not meta["stopped"]:
        meta["stopped"] = "no_answer"
    meta["evicted"] += _evict(msgs, budget, cpt, ovh, question)
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
    spans = sorted((_span(n), n) for n in body if isinstance(n, _DEFNODES))
    covered: set = set()
    for (a, b), _n in spans:
        covered.update(range(a, b + 1))
    own = "\n".join(lines[i - 1] for i in range(lo, hi + 1) if i not in covered)
    kids = [_nodo(lines, a, b, getattr(n, "body", []), ident + "." + n.name,
                  _sig(n), n, count) for (a, b), n in spans]
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
        lines = src.splitlines()
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
    ("codice", re.compile(r"\b[A-Z][A-Z0-9]{2,}[-_][A-Z0-9]{1,8}\b")),
    ("sigla", re.compile(r"\b[A-Z]{3,}\d{1,6}\b")),
    ("misura", re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:terawatt|gigawatt|megawatt|kilowatt|watt|TB|GB|MB|GHz|MHz|volt|ampere)\b", re.I)),
    ("chiave", re.compile(r"\b[A-Za-z0-9_\-]{16,}\b")),
    ("virgolette", re.compile(r'"([^"\n]{3,60})"')),
)


def trova_fatti(testo: str, max_per_tipo: int = 40, contesto: int = 90) -> List[Dict[str, Any]]:
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
            if n >= max_per_tipo:
                break
    out.sort(key=lambda d: d["pos"])
    return out


def prepara_albero_ricco(documento: str, sessione: str, tree: Optional["DocTree"] = None, 
                          max_chars: int = 1500, max_per_tipo: int = 100, tetto_fatti: int = 180) -> Tuple["DocTree", str]:
    """Costruisce un albero con summary arricchiti dai fatti deterministici.
    
    Chunka il documento, estrae tutti i fatti con trova_fatti(), e per ogni chunk
    inserisce nel summary i fatti che cadono in quel range. Questo rende i fatti
    visibili nell'indice senza dover aprire i rami.
    
    Args:
        documento: testo completo da indicizzare
        sessione: nome della sessione per DocTree
        tree: DocTree esistente (se None, usa ~/.cache/bocconcini/workspace)
        max_chars: dimensione massima dei chunk
        max_per_tipo: quanti fatti estrarre per tipo (default 100 invece di 40)
        tetto_fatti: max characters of the fact block in each summary (default 180).
            Facts are ordered by GLOBAL RARITY of their type: a type with 4 hits in
            the document is signal, one with 100 hits is noise, so rare types are
            rendered first. What does not fit is counted and declared, never dropped
            in silence; the verbatim text of every branch stays on disk.
    
    Returns:
        (tree, sessione) - il tree con l'albero salvato
    
    Example:
        >>> import bocconcini as b
        >>> import bocconcini_memory as t
        >>> tree, session = t.prepara_albero_ricco(documento_enorme, "test")
        >>> risultato = t.naviga(client, tree, session, domanda, budget_tokens=1500)
    """
    if tree is None:
        tree = DocTree()
    
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
        if fatti_nel_chunk:
            visibili, usati = [], 0
            for f in fatti_nel_chunk:
                f = f if len(f) <= 80 else f[:77] + "..."
                if visibili and usati + len(f) + 2 > tetto_fatti:
                    break
                visibili.append(f)
                usati += len(f) + 2
            blocco = "CHIAVE -> " + ", ".join(visibili)
            resto = len(fatti_nel_chunk) - len(visibili)
            if resto:
                blocco += " (+%d altri nel ramo)" % resto
            summary_base = blocco + (" | " + summary_base if summary_base else "")
        
        roots.append(DocNode(
            id=node_id,
            label=f"Sezione {i} (pos {ch.start}-{ch.end})",
            summary=summary_base,
            text=ch.text,
            tokens=ch.token_count_estimate()
        ))
    
    # 4. Salvataggio dell'albero
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


def ask_stepwise(client, documento: str, question: str, *, targets=None,
                 max_tokens: int = 120, window: int = 200, per_target: int = 2,
                 temperature: float = 0.0) -> Dict[str, Any]:
    """One target at a time, each in a FRESH context. Python keeps the findings.

    The model never has to remember what it already did: every sub-task starts
    with an empty history and sees only the verbatim windows for ITS target.
    The answers accumulate outside the model, so nothing is ever evicted.
    """
    low = documento.lower()
    if not targets:
        r = client.chat_full(prompt=("List the distinct items to find in this request, "
                                     "one per line, no numbering, no explanation.\nRequest: "
                                     + question), max_tokens=60, temperature=0.0, continua=False)
        targets = [ln.strip(" -\t0123456789.") for ln in (r.text or "").splitlines()]
        targets = [x for x in targets if 2 < len(x) <= 40][:8]
    findings, calls, biggest = [], 0, 0
    for tg in targets:
        q = str(tg).lower().strip()
        wins, start = [], 0
        while len(wins) < per_target:
            k = low.find(q, start)
            if k < 0:
                break
            a, b = max(0, k - window // 2), min(len(documento), k + len(q) + window // 2)
            wins.append(documento[a:b].replace("\n", " "))
            start = k + len(q)
        if not wins:
            findings.append((tg, "NOT FOUND"))
            continue
        p = ("VERBATIM EXCERPTS:\n" + "\n".join("- " + w for w in wins)
             + "\n\nWhat is the value for '" + str(tg) + "'? Answer with the value only, "
             + "or NOT FOUND if it is not in the excerpts.")
        biggest = max(biggest, len(p))
        r = client.chat_full(prompt=p, max_tokens=max_tokens,
                             temperature=temperature, continua=False)
        calls += 1
        findings.append((tg, (r.text or "").strip()))
    righe = "\n".join("%s: %s" % (k, v) for k, v in findings)
    p = ("FINDINGS already extracted:\n" + righe + "\n\nAnswer this request using only "
         + "the findings above.\nRequest: " + question)
    biggest = max(biggest, len(p))
    r = client.chat_full(prompt=p, max_tokens=300, temperature=temperature, continua=False)
    return {"text": r.text or "", "meta": {"targets": list(targets), "findings": findings,
                                          "sub_calls": calls, "biggest_prompt_chars": biggest}}
