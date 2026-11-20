"""bocconcini_docs - read long documents (PDF text, books, mixed prose + code) with a small model.

Standard library only (+ the optional ``pdftotext`` binary for PDFs). Companion of ``bocconcini``.

The idea, in three rules
  * TEXT   -> summarised with Refine: old notes + new piece -> new notes (the model writes them).
  * CODE   -> NEVER summarised by the model. We keep a deterministic outline (``ast`` for Python,
              verbatim declaration lines for other languages) and the most recent pieces verbatim.
  * BUDGET -> the final prompt is built to fit a token budget: oldest verbatim code goes first,
              then oldest outlines, then the notes are cut at a sentence end. The question is never cut.

Quick start::

    from bocconcini import LlamaCppClient
    from bocconcini_docs import analyze, read_pdf_pages

    client = LlamaCppClient("http://127.0.0.1:8082")
    pages = read_pdf_pages("manual.pdf")              # needs: pkg install poppler
    reply = analyze(client, pages, "What does the install section require?")
    print(reply.text)

Italian names of the first prototype (``classifica_blocco``, ``dividi_misto``,
``estrai_logica_codice``, ``processa_misto``) are kept as thin wrappers.
"""
from __future__ import annotations

import ast
import hashlib
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from .client import ChatReply, ModelError, estimate_tokens, iter_chunks, split_text, LlamaServerTokenizer

__version__ = "1.0.0"
__all__ = ["Block", "classify_block", "split_mixed", "code_outline", "Digest", "process_document",
           "analyze", "read_pdf_pages", "classifica_blocco", "dividi_misto", "estrai_logica_codice",
           "processa_misto"]

log = logging.getLogger("bocconcini.docs")
Ask = Callable[[str], str]


@dataclass
class Block:
    kind: str                 # "text" | "code"
    text: str
    lang: str = ""            # language hint from a fence, if any
    fenced: bool = False


# ----------------------------------------------------------------------------
# Classification: code or text? Pure Python, the model is never asked.
# ----------------------------------------------------------------------------
_PY_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Assign,
             ast.AnnAssign, ast.AugAssign, ast.Return, ast.If, ast.For, ast.AsyncFor, ast.While, ast.With,
             ast.AsyncWith, ast.Try, ast.Raise, ast.Assert, ast.Delete, ast.Global, ast.Nonlocal)

_CODE_LINE = [re.compile(p) for p in (
    r"^\s*(async\s+)?(def|class)\s+\w+.*:\s*(#.*)?$",
    r"^\s*(if|elif|while|for|with|except|try|else|finally)\b[^.!?]*:\s*(#.*)?$",
    r"^\s*(import\s+[\w.]+(\s+as\s+\w+)?(\s*,\s*[\w.]+)*|from\s+[\w.]+\s+import\s+.+)\s*$",
    r"^\s*(return|raise|yield)\b[^.!?]*[(\[=]",
    r"^\s*return(\s+\S+)?\s*$",
    r"^\s*[A-Za-z_][\w.\[\]'\"]*\s*(=|\+=|-=|\*=|/=|:=)(?!=)\s*\S",
    r"^\s*[A-Za-z_][\w.]*\([^)]*\)\s*;?\s*$",
    r"^\s*@\w[\w.]*(\(.*\))?\s*$",
    r"[;{}]\s*$",
    r"^\s*#(include|define|ifdef|ifndef|endif)\b",
    r"=>|::\w|->\s*\w+\s*\{",
    r"^\s*\$\s+\S",
    r"^\s*(function|const|let|var|public|private|protected|static|fn|func|package|namespace)\s+\S+.*[({=]",
    r"^\s*</?[A-Za-z][\w-]*(\s[^>]*)?/?>\s*$",
)]
_WORD = re.compile(r"[^\W\d_]{2,}", re.U)


def _line_score(line: str) -> int:
    """+1 looks like code, -1 looks like prose, 0 unknown (blank, comment, short)."""
    s = line.rstrip()
    st = s.strip()
    if not st:
        return 0
    for rx in _CODE_LINE:
        if rx.search(s):
            return 1
    if re.match(r"^\s{4,}|^\t", s) and re.search(r"[=()\[\]{}:;]", st):
        return 1
    if re.match(r"^#{1,6}\s+\S", st) or re.match(r"^([-*+]|\d+[.)])\s+\S", st):
        return -1
    words = _WORD.findall(st)
    if len(words) >= 6 and not re.search(r"[=;{}]|\w\(", st):
        return -1
    return 0


def _python_evidence(text: str) -> bool:
    """True when ``text`` parses as Python AND contains something that is not just a bare word."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return False
    for node in tree.body:
        if isinstance(node, _PY_NODES):
            return True
        if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Call, ast.Await, ast.Yield, ast.YieldFrom)):
            if re.match(r"^\s*[\w.]+\(", text):          # 'print(x)' yes, 'Nota (1)' no
                return True
    return False


def classify_block(text: str) -> str:
    """Return "code" or "text".

    A bare word, a number or a comma list ("mele, pere") is valid Python but is prose: ast.parse
    alone is NOT enough, the tree must contain real statements.
    """
    t = (text or "").strip()
    if not t:
        return "text"
    if _python_evidence(t):
        return "code"
    lines = [ln for ln in t.splitlines() if ln.strip()]
    votes = [_line_score(ln) for ln in lines]
    code, prose = sum(1 for v in votes if v > 0), sum(1 for v in votes if v < 0)
    if code == 0:
        return "text"
    if code >= 2 and code >= prose:
        return "code"
    return "code" if code / len(lines) >= 0.4 and code > prose else "text"


# ----------------------------------------------------------------------------
# Splitting mixed text into blocks
# ----------------------------------------------------------------------------
_FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([^\s`]*)[^`]*$")


def _scan_fences(text: str) -> List[Tuple[str, str, str, bool]]:
    """Split into ("outside", "", text, True) and ("fence", lang, body, closed) parts. Line based:
    handles CRLF, ~~~ fences, longer fences and a fence that is never closed (cut chunk)."""
    out: List[Tuple[str, str, str, bool]] = []
    buf: List[str] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = _FENCE_OPEN.match(lines[i])
        if not m:
            buf.append(lines[i])
            i += 1
            continue
        if buf:
            out.append(("outside", "", "\n".join(buf), True))
            buf = []
        mark, lang = m.group(1), m.group(2)
        close = re.compile(r"^ {0,3}%s{%d,}\s*$" % (re.escape(mark[0]), len(mark)))
        j, body, closed = i + 1, [], False
        while j < len(lines):
            if close.match(lines[j]):
                closed = True
                break
            body.append(lines[j])
            j += 1
        out.append(("fence", lang, "\n".join(body), closed))
        i = j + 1
    if buf:
        out.append(("outside", "", "\n".join(buf), True))
    return out


_CONTINUES = re.compile(r"^(\s+\S|[)\]}]|(else|elif|except|finally)\b|@|def |class |async def )")


def _segment_outside(text: str) -> List[Block]:
    """Outside fences: paragraphs are classified one by one, then repaired.

    A blank line inside a Python function must not turn the rest of the function into prose:
    a paragraph that follows code and still looks indented/continuing stays code.
    """
    paras = [p for p in re.split(r"\n[ \t]*\n", text) if p.strip()]
    kinds = [classify_block(p) for p in paras]
    for i, p in enumerate(paras):
        if kinds[i] != "text" or i == 0:
            continue
        first = p.split("\n", 1)[0]
        prose = sum(1 for ln in p.splitlines() if _line_score(ln) < 0)
        if kinds[i - 1] == "code" and _CONTINUES.match(first) and prose == 0:
            kinds[i] = "code"
        elif (kinds[i - 1] == "code" and i + 1 < len(paras) and classify_block(paras[i + 1]) == "code"
              and prose == 0 and len(p.splitlines()) <= 3):
            kinds[i] = "code"
    return [Block(k, p.strip("\n")) for k, p in zip(kinds, paras)]


def split_mixed(text: str) -> List[Block]:
    """Cut text into [Block("text"|"code", ...)]. Fences are certain; the rest is classified."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    blocks: List[Block] = []
    for kind, lang, body, _closed in _scan_fences(text):
        if kind == "fence":
            if body.strip():
                blocks.append(Block("code", body.strip("\n"), lang.lower(), True))
        else:
            blocks.extend(_segment_outside(body))
    merged: List[Block] = []
    for b in blocks:                      # fewer, bigger blocks of the same kind
        if merged and merged[-1].kind == b.kind and merged[-1].lang == b.lang:
            merged[-1] = Block(b.kind, merged[-1].text + "\n\n" + b.text, b.lang, merged[-1].fenced and b.fenced)
        else:
            merged.append(b)
    return merged


# ----------------------------------------------------------------------------
# Code outline: deterministic, never invented
# ----------------------------------------------------------------------------
def _unparse(node: Optional[ast.AST]) -> str:
    if node is None:
        return ""
    fn = getattr(ast, "unparse", None)
    if fn is None:
        return ""
    try:
        return fn(node)
    except Exception:
        return ""


def _signature(fn: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
    a = fn.args
    pos = list(getattr(a, "posonlyargs", [])) + list(a.args)
    defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    parts: List[str] = []
    for arg, dflt in zip(pos, defaults):
        s = arg.arg + (": " + _unparse(arg.annotation) if arg.annotation is not None else "")
        if dflt is not None:
            v = _unparse(dflt) or "..."
            s += "=" + (v if len(v) <= 20 else "...")
        parts.append(s)
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    elif a.kwonlyargs:
        parts.append("*")
    for arg, dflt in zip(a.kwonlyargs, a.kw_defaults):
        s = arg.arg + (": " + _unparse(arg.annotation) if arg.annotation is not None else "")
        if dflt is not None:
            v = _unparse(dflt) or "..."
            s += "=" + (v if len(v) <= 20 else "...")
        parts.append(s)
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    ret = _unparse(fn.returns)
    return "(%s)%s" % (", ".join(parts), " -> " + ret if ret else "")


def _calls(fn: ast.AST) -> List[str]:
    names = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                names.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                names.add(n.func.attr)
    return sorted(names)[:12]


def _doc1(node: ast.AST) -> str:
    d = ast.get_docstring(node)  # type: ignore[arg-type]
    return d.strip().splitlines()[0][:100] if d else ""


def _def_line(fn: Union[ast.FunctionDef, ast.AsyncFunctionDef], indent: str) -> str:
    end = getattr(fn, "end_lineno", fn.lineno)
    deco = " ".join("@" + (_unparse(d).split("(")[0] or "?") for d in fn.decorator_list)
    calls = _calls(fn)
    line = "%s%sdef %s%s  L%d-%d" % (indent, "async " if isinstance(fn, ast.AsyncFunctionDef) else "",
                                      fn.name, _signature(fn), fn.lineno, end)
    if deco:
        line += "  [%s]" % deco
    if calls:
        line += "  calls: " + ", ".join(calls)
    d = _doc1(fn)
    return line + ("\n%s    doc: %s" % (indent, d) if d else "")


def _py_parse_prefix(code: str) -> Tuple[Optional[ast.Module], int]:
    """Parse ``code``; if a chunk boundary cut it, drop trailing lines until it parses."""
    lines = code.split("\n")
    for drop in (0, 1, 2, 3, 5, 8, 13, 21, 34):
        if drop >= len(lines):
            break
        try:
            return ast.parse("\n".join(lines[:len(lines) - drop])), drop
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            continue
    return None, 0


def _py_outline(code: str) -> Optional[str]:
    tree, dropped = _py_parse_prefix(code)
    if tree is None:
        return None
    n = len(code.split("\n"))
    out = ["python, %d lines%s" % (n, " (last %d lines cut mid-statement, not shown)" % dropped if dropped else "")]
    imports: List[str] = []
    consts: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imports.append("%s%s" % ("." * node.level, node.module or "") + " (" + ", ".join(a.name for a in node.names[:6]) + ")")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            consts += [t.id for t in targets if isinstance(t, ast.Name)]
    if imports:
        out.append("imports: " + ", ".join(imports[:14]) + (" ..." if len(imports) > 14 else ""))
    if consts:
        out.append("module names: " + ", ".join(consts[:15]) + (" ..." if len(consts) > 15 else ""))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(_def_line(node, ""))
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(_unparse(b) for b in node.bases)
            out.append("class %s%s  L%d-%d" % (node.name, "(%s)" % bases if bases else "", node.lineno,
                                               getattr(node, "end_lineno", node.lineno)))
            d = _doc1(node)
            if d:
                out.append("    doc: " + d)
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(_def_line(sub, "  "))
    if len(out) == 1:
        out.append("no functions or classes")
    return "\n".join(out)


_GENERIC = [re.compile(p) for p in (
    r"^\s*(export\s+)?(default\s+)?(async\s+)?function\b.*",
    r"^\s*(export\s+)?(abstract\s+)?(class|interface|enum|struct|trait|impl|module|namespace)\s+\w+.*",
    r"^\s*(export\s+)?(const|let|var)\s+\w+\s*=\s*(async\s*)?(\([^)]*\)|\w+)\s*=>.*",
    r"^\s*(pub\s+)?(async\s+)?fn\s+\w+.*",
    r"^\s*func\s+(\(.*?\)\s*)?\w+\(.*",
    r"^\s*(async\s+)?def\s+\w+.*",
    r"^\s*(public|private|protected|static|final|virtual|override|inline)\b.*\(.*\).*",
    r"^\s*#include\s+.*",
    r"^\s*(import|using|require|use|package)\b.*",
    r"^\s*(?!if\b|for\b|while\b|switch\b|return\b|else\b)\w[\w\s*&:<>,]*\s+\w+\s*\([^;]*\)\s*\{?\s*$",
)]


def _generic_outline(code: str, lang: str = "") -> str:
    lines = code.split("\n")
    hits = []
    for n, ln in enumerate(lines, 1):
        if any(rx.match(ln) for rx in _GENERIC):
            hits.append("L%d: %s" % (n, ln.strip()[:140]))
    head = "%s, %d lines, declaration lines (verbatim)" % (lang or "code", len(lines))
    if not hits:
        return head + ": none recognised"
    more = "\n... %d more" % (len(hits) - 60) if len(hits) > 60 else ""
    return head + "\n" + "\n".join(hits[:60]) + more


def code_outline(code: str, lang: str = "") -> str:
    """Structure of ``code`` without any model: ast for Python, declaration lines otherwise."""
    if lang in ("", "python", "py", "python3") and (lang or classify_block(code) == "code"):
        out = _py_outline(code)
        if out is not None:
            return out
    return _generic_outline(code, lang)


# ----------------------------------------------------------------------------
# Digest: rolling notes for text, outline + recent verbatim for code
# ----------------------------------------------------------------------------
_L10N = {
    "en": {
        "refine": ("Update the notes with the new text. Keep facts, names, numbers and decisions. Do not "
                   "invent anything. At most {chars} characters. Reply with the updated notes only.\n\n"
                   "NOTES SO FAR:\n{notes}\n\nNEW TEXT:\n{piece}\n\nUPDATED NOTES:"),
        "map": ("Summarise the text below. Keep facts, names, numbers and decisions. Do not invent "
                "anything. At most {chars} characters.\n\nTEXT:\n{piece}\n\nSUMMARY:"),
        "merge": ("Merge these notes into one. Keep every fact, drop repetitions. At most {chars} "
                  "characters.\n\n{notes}\n\nMERGED NOTES:"),
        "h_notes": "[TEXT - NOTES WRITTEN BY THE MODEL]", "h_map": "[CODE - STRUCTURE EXTRACTED WITH AST, NOT SUMMARISED]",
        "h_code": "[CODE - RECENT PIECES, VERBATIM]", "h_q": "[QUESTION]",
        "none_t": "(no text)", "none_c": "(no code)", "omitted": "(%d earlier outline(s) omitted)",
    },
    "it": {
        "refine": ("Migliora gli appunti con il testo nuovo. Tieni fatti, nomi, numeri e decisioni. Non "
                   "inventare niente. Massimo {chars} caratteri. Rispondi solo con gli appunti aggiornati.\n\n"
                   "APPUNTI FINORA:\n{notes}\n\nTESTO NUOVO:\n{piece}\n\nAPPUNTI AGGIORNATI:"),
        "map": ("Riassumi il testo qui sotto. Tieni fatti, nomi, numeri e decisioni. Non inventare niente. "
                "Massimo {chars} caratteri.\n\nTESTO:\n{piece}\n\nRIASSUNTO:"),
        "merge": ("Unisci questi appunti in uno solo. Tieni ogni fatto, togli le ripetizioni. Massimo {chars} "
                  "caratteri.\n\n{notes}\n\nAPPUNTI UNITI:"),
        "h_notes": "[TESTO - APPUNTI SCRITTI DAL MODELLO]", "h_map": "[CODICE - STRUTTURA ESTRATTA CON AST, NON RIASSUNTA]",
        "h_code": "[CODICE - PEZZI RECENTI, VERBATIM]", "h_q": "[DOMANDA]",
        "none_t": "(nessun testo)", "none_c": "(nessun codice)", "omitted": "(%d outline precedenti omesse)",
    },
}


def _cut_sentence(text: str, max_chars: int) -> str:
    """Cut at a sentence/line end instead of in the middle of a fact."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    k = max(cut.rfind(". "), cut.rfind("\n"), cut.rfind("; "))
    return (cut[:k + 1] if k > max_chars * 0.5 else cut).rstrip()


class Digest:
    """Incrementally digest a long document so that a small model can answer about it.

    ``ask(prompt) -> str`` talks to the model (e.g. ``client.chat``). Code is never sent to it.
    ``mode="refine"``: one rolling set of notes. ``mode="map"``: one note per piece, merged pairwise
    when they exceed their budget (keeps early details better on very long documents).
    """
    def __init__(self, ask: Ask, *, budget_tokens: int = 2000, mode: str = "refine", lang: str = "en",
                 summary_tokens: Optional[int] = None, summary_chars: Optional[int] = None,
                 code_verbatim_tokens: Optional[int] = None, piece_tokens: Optional[int] = None, chars_per_token: Optional[float] = None) -> None:
        if mode not in ("refine", "map"):
            raise ValueError("mode must be 'refine' or 'map'")
        self.ask, self.mode = ask, mode
        self.t = _L10N.get(lang, _L10N["en"])
        self.budget = max(300, int(budget_tokens))
        self.summary_tokens = summary_tokens or int(self.budget * 0.35)
        self.cpt = max(1.0, min(8.0, float(chars_per_token or 3.2)))
        self.summary_chars = summary_chars or int(self.summary_tokens * self.cpt)
        self.code_verbatim_tokens = code_verbatim_tokens or int(self.budget * 0.40)
        self.piece_tokens = piece_tokens or max(150, self.budget - self.summary_tokens - 250)
        self.summary = ""
        self.notes: List[str] = []
        self.outlines: List[str] = []
        self._seen: set = set()
        self.recent: List[Block] = []
        self.stats: Dict[str, int] = {"text_blocks": 0, "code_blocks": 0, "model_calls": 0, "model_failures": 0,
                                      "notes_cut": 0, "pieces_lost": 0}

    # -- feeding -------------------------------------------------------------
    def feed(self, piece: str) -> None:
        for blk in split_mixed(piece):
            (self._feed_code if blk.kind == "code" else self._feed_text)(blk)

    def _ask(self, prompt: str) -> Optional[str]:
        self.stats["model_calls"] += 1
        try:
            out = (self.ask(prompt) or "").strip()
        except ModelError as exc:
            log.warning("model call failed (%s): keeping the previous notes", exc)
            self.stats["model_failures"] += 1
            return None
        return out or None

    def _feed_text(self, blk: Block) -> None:
        self.stats["text_blocks"] += 1
        for p in split_text(blk.text, "text", max_tokens=self.piece_tokens,
                            max_chars=int(self.piece_tokens * self.cpt), min_chars=100, overlap=0):
            if self.mode == "refine":
                out = self._ask(self.t["refine"].format(chars=self.summary_chars, notes=self.summary or "-",
                                                        piece=p.text))
                if out:
                    if len(out) > self.summary_chars:
                        self.stats["notes_cut"] += 1
                    self.summary = _cut_sentence(out, self.summary_chars)
                else:
                    self.stats["pieces_lost"] += 1
            else:
                per = max(200, self.summary_chars // 4)
                out = self._ask(self.t["map"].format(chars=per, piece=p.text))
                if out:
                    self.notes.append(_cut_sentence(out, per))
                    self._compact()
                else:
                    self.stats["pieces_lost"] += 1

    def _compact(self) -> None:
        while len(self.notes) > 1 and estimate_tokens("\n".join(self.notes)) > self.summary_tokens:
            half = max(2, len(self.notes) // 2)
            merged: List[str] = []
            for i in range(0, len(self.notes), 2):
                pair = self.notes[i:i + 2]
                if len(pair) == 1:
                    merged.append(pair[0])
                    continue
                per = max(200, int(self.summary_chars / max(1, half)))
                out = self._ask(self.t["merge"].format(chars=per, notes="\n---\n".join(pair)))
                if out:
                    merged.append(_cut_sentence(out, per))
                else:
                    merged.append(_cut_sentence("\n".join(pair), per))
                    self.stats["notes_cut_merge"] = self.stats.get("notes_cut_merge", 0) + 1
            if len(merged) >= len(self.notes):
                break
            self.notes = merged

    def _feed_code(self, blk: Block) -> None:
        self.stats["code_blocks"] += 1
        is_py = blk.lang in ("", "python", "py", "python3") and _python_evidence(blk.text)
        pieces = [blk.text]
        if estimate_tokens(blk.text, "python") > self.piece_tokens:
            pieces = [c.text for c in iter_chunks(blk.text, "x.py" if is_py else "x.txt",
                                                  max_tokens=self.piece_tokens,
                                                  max_chars=int(self.piece_tokens * 2.8), min_chars=100, overlap=0)]
        for body in pieces:
            key = hashlib.blake2b(body.encode("utf-8", "replace"), digest_size=8).hexdigest()
            if key in self._seen:
                continue
            self._seen.add(key)
            self.outlines.append(code_outline(body, blk.lang))
            self.recent.append(Block("code", body, blk.lang, blk.fenced))
            while len(self.recent) > 1 and sum(estimate_tokens(b.text, "python") for b in self.recent) \
                    > self.code_verbatim_tokens:
                self.recent.pop(0)                    # the outline stays, only the verbatim copy goes

    # -- reading -------------------------------------------------------------
    @property
    def text_notes(self) -> str:
        return self.summary if self.mode == "refine" else "\n".join(self.notes)

    @property
    def code_map(self) -> str:
        return "\n\n".join(self.outlines)

    def prompt(self, question: str = "", budget_tokens: Optional[int] = None) -> str:
        """Final prompt, fitted to the budget. The question is never cut."""
        budget = int(budget_tokens or self.budget)
        t = self.t
        def ntok(txt: str) -> int:
            return int(len(txt) / self.cpt) + 1

        def render(notes: str, omitted: int, outlines: List[str], recent: List[Block]) -> str:
            mp = ("\n\n".join(outlines) if outlines else t["none_c"])
            if omitted:
                mp = t["omitted"] % omitted + "\n" + mp
            code = "\n\n---\n\n".join(b.text for b in recent) if recent else t["none_c"]
            parts = [t["h_notes"], notes or t["none_t"], "", t["h_map"], mp, "", t["h_code"], code]
            if question:
                parts += ["", t["h_q"], question]
            return "\n".join(parts)

        notes, outlines, recent, omitted = self.text_notes, list(self.outlines), list(self.recent), 0
        if (self.stats.get("pieces_lost") or self.stats.get("pieces_unreliable")
                or self.stats.get("notes_cut_merge")):
            notes = (notes + "\n[WARNING: %d piece(s) of the document were lost or read from a truncated "
                     "context: that content is MISSING or UNRELIABLE. Say so if the "
                     "question needs it.]"
                     % (self.stats.get("pieces_lost", 0) + self.stats.get("pieces_unreliable", 0)
                        + self.stats.get("notes_cut_merge", 0))).strip()
        out = render(notes, omitted, outlines, recent)
        while ntok(out) > budget and len(recent) > 1:
            recent.pop(0)
            out = render(notes, omitted, outlines, recent)
        while ntok(out) > budget and len(outlines) > 1:
            outlines.pop(0)
            omitted += 1
            out = render(notes, omitted, outlines, recent)
        if ntok(out) > budget and notes:
            over = ntok(out) - budget
            notes = _cut_sentence(notes, max(200, len(notes) - int(over * self.cpt)))
            out = render(notes, omitted, outlines, recent)
        if ntok(out) > budget and recent:
            recent = []                                    # last resort: outlines still describe the code
            out = render(notes, omitted, outlines, recent)
        return out


# ----------------------------------------------------------------------------
# Whole documents, PDFs, convenience wrapper
# ----------------------------------------------------------------------------
def process_document(source: Union[str, Sequence[str]], ask: Ask, *, budget_tokens: int = 2000,
                     mode: str = "refine", lang: str = "en",
                     on_progress: Optional[Callable[[int, int], None]] = None, **options: Any) -> Digest:
    """Feed a document (one string, or a list of pages) into a Digest and return it."""
    d = Digest(ask, budget_tokens=budget_tokens, mode=mode, lang=lang, **options)
    pages = [source] if isinstance(source, str) else list(source)
    for i, page in enumerate(pages, 1):
        d.feed(page)
        if on_progress:
            try:
                on_progress(i, len(pages))
            except Exception as exc:
                log.debug("on_progress failed: %s", exc)
    return d


def analyze(client: Any, source: Union[str, Sequence[str]], question: str, *, mode: str = "refine",
            lang: str = "en", budget_tokens: Optional[int] = None,
            on_progress: Optional[Callable[[int, int], None]] = None, **chat_options: Any) -> ChatReply:
    """Digest ``source`` with ``client`` and answer ``question``. Every model call fits the window."""
    strict = bool(chat_options.pop("strict", False))
    flags = {"truncated": 0, "reduced": 0}
    budget = budget_tokens or client.working_budget()
    cpt = 3.2
    try:
        sample = (source if isinstance(source, str) else "".join(source))[:4000]
        tok = getattr(client, "tokenizer", None) or LlamaServerTokenizer(client.base_url)
        fn = getattr(tok, "try_count", None) or tok.count_exact
        n = fn(sample)
        if n and n > 0:
            cpt = max(1.0, min(8.0, len(sample) / n))
            log.info("measured %.2f chars/token on this document (default 3.2)", cpt)
    except Exception as exc:
        log.debug("chars/token measurement failed (%s): using 3.2", exc)
    sysmsg = "You are a careful note-taker. Never invent facts."

    def ask(prompt: str) -> str:
        r = client.chat_full(prompt, sysmsg, temperature=0.2, thinking=False, continua=False,
                           max_tokens=max(200, min(700, budget // 3)))
        if r.meta.get("prompt_truncated"):
            flags["truncated"] += 1
        if r.meta.get("reduced"):
            flags["reduced"] += 1
        return r.text

    d = process_document(source, ask, budget_tokens=budget, mode=mode, lang=lang,
                         on_progress=on_progress, chars_per_token=cpt)
    d.stats["pieces_unreliable"] = flags["truncated"]
    log.info("digest: %s", d.stats)
    lost = d.stats.get("pieces_lost", 0) + flags["truncated"]
    if lost:
        log.warning("digest lost %d piece(s): the document is incomplete", lost)
        if strict:
            raise ModelError("the digest lost %d piece(s): refusing to answer about "
                             "incomplete content" % lost, kind="incomplete")
    reply = client.chat_full(d.prompt(question, budget), **chat_options)
    reply.meta["digest"] = dict(d.stats)
    reply.meta["digest"].update(flags)
    return reply


def read_pdf_pages(path: str, timeout: float = 300.0) -> List[str]:
    """Text of a PDF, one string per page. Uses ``pdftotext`` (Termux: ``pkg install poppler``),
    else ``pypdf``/``PyPDF2`` if installed. Scanned PDFs need OCR: out of scope."""
    exe = shutil.which("pdftotext")
    if exe:
        res = subprocess.run([exe, "-layout", path, "-"], capture_output=True, timeout=timeout)
        if res.returncode == 0:
            raw = res.stdout.decode("utf-8", "replace")
            pages = [_clean_page(p) for p in raw.split("\f")]
            while pages and not pages[-1].strip():
                pages.pop()
            return pages
        raise RuntimeError("pdftotext failed: " + res.stderr.decode("utf-8", "replace")[:200])
    for mod in ("pypdf", "PyPDF2"):
        try:
            lib = __import__(mod)
        except ImportError:
            continue
        reader = lib.PdfReader(path)
        return [_clean_page(pg.extract_text() or "") for pg in reader.pages]
    raise RuntimeError("no PDF reader found: install poppler (Termux: pkg install poppler; "
                       "Debian/Ubuntu: apt install poppler-utils) or pip install pypdf")


def _clean_page(page: str) -> str:
    page = re.sub(r"(\w)-\n(\w)", r"\1\2", page)
    return re.sub(r"\n{3,}", "\n\n", page).strip("\n")


# ----------------------------------------------------------------------------
# Italian names of the first prototype
# ----------------------------------------------------------------------------
def classifica_blocco(blocco: str) -> str:
    return "codice" if classify_block(blocco) == "code" else "testo"


def dividi_misto(testo: str) -> List[Tuple[str, str]]:
    return [("codice" if b.kind == "code" else "testo", b.text) for b in split_mixed(testo)]


def estrai_logica_codice(codice: str) -> str:
    return code_outline(codice)


def processa_misto(testo_misto: str, chiedi_al_modello: Ask, max_riassunto: int = 800) -> Tuple[str, str, str]:
    """Same contract as the prototype: returns (riassunto_testo, logica_codice, prompt_per_malg)."""
    d = Digest(chiedi_al_modello, mode="refine", lang="it", budget_tokens=4000,
               summary_chars=max_riassunto, summary_tokens=max(60, max_riassunto // 3))
    d.feed(testo_misto)
    return d.summary, d.code_map or "(nessun codice visto)", d.prompt()
