"""Spill senza perdita: il contenuto va su disco, nel prompt resta l'indice.

Nessun messaggio viene cancellato durante il loop. Il modello apre un ramo
per indirizzo e riottiene i byte identici. Zero dipendenze, Python 3.7+.
"""
import hashlib
import json
import os
import re


def _tipo(testo):
    s = testo.lstrip()
    if s[:1] in "{[":
        try:
            json.loads(s)
            return "json"
        except Exception:
            pass
    if re.search(r"^\s*(def |class |@|import |from )", testo, re.M):
        return "codice"
    return "testo"


def _anteprima(testo, max_righe=6):
    t = _tipo(testo)
    if t == "json":
        try:
            o = json.loads(testo)
            if isinstance(o, dict):
                return "chiavi: " + ", ".join(list(o.keys())[:12])
            return "lista di %d elementi" % len(o)
        except Exception:
            pass
    if t == "codice":
        righe = []
        for i, r in enumerate(testo.splitlines(), 1):
            if re.match(r"\s*(def |class |@)", r):
                righe.append("%d:%s" % (i, r.strip()[:60]))
            if len(righe) >= max_righe:
                break
        if righe:
            return " | ".join(righe)
    return re.sub(r"\s+", " ", testo.strip().split(". ")[0])[:100]


class Spill:
    """Contenuto su disco, indice append-only in memoria."""

    def __init__(self, cartella):
        self.cartella = str(cartella)
        os.makedirs(self.cartella, exist_ok=True)
        self._voci = []
        self._id = {}

    def put(self, contenuto, etichetta="ramo", tipo=None):
        if isinstance(contenuto, str):
            testo = contenuto
        else:
            testo = json.dumps(contenuto, ensure_ascii=False, sort_keys=True)
        dati = testo.encode("utf-8")
        digest = hashlib.sha256(dati).hexdigest()[:12]
        nome = re.sub(r"[^A-Za-z0-9_]+", "_", etichetta)[:24]
        ident = "%s-%s" % (nome, digest)
        if ident not in self._id:
            percorso = os.path.join(self.cartella, ident + ".txt")
            with open(percorso, "wb") as f:
                f.write(dati)
            self._id[ident] = percorso
            self._voci.append({"id": ident, "byte": len(dati),
                               "tipo": tipo or _tipo(testo),
                               "anteprima": _anteprima(testo)})
        return ident

    def get(self, ident):
        with open(self._id[ident], "rb") as f:
            return f.read().decode("utf-8")

    def indice(self):
        return "\n".join("[%s] %s %d byte - %s" % (v["id"], v["tipo"],
                         v["byte"], v["anteprima"]) for v in self._voci)


def spill_messaggi(msgs, store, soglia_caratteri=640, prefisso="tool"):
    """Sostituisce i contenuti oltre soglia con la loro voce d'indice.

    NON cancella messaggi. L'ultimo non si tocca mai: e' la richiesta.
    Un messaggio con ``pin: True`` resta in linea per intero, a qualunque
    dimensione: chi lo marca si prende la responsabilita' del budget.
    """
    out = []
    ultimo = len(msgs) - 1
    for i, m in enumerate(msgs):
        c = m.get("content")
        if (not isinstance(c, str) or i == ultimo or m.get("pin")
                or len(c) <= soglia_caratteri):
            out.append(m)
            continue
        ident = store.put(c, etichetta="%s%d" % (prefisso, i))
        voce = dict(m)
        voce["content"] = ('[ramo %s] %d byte su disco. Apri con leggi_ramo("%s"). %s'
                           % (ident, len(c.encode("utf-8")), ident, _anteprima(c)))
        voce["ramo"] = ident
        out.append(voce)
    return out
