import tempfile
import bocconcini as sp

n = fail = 0
def ok(label, cond):
    global n, fail
    n += 1
    if not cond:
        fail += 1
    print("%s %s" % ("OK  " if cond else "FAIL", label))

with tempfile.TemporaryDirectory() as td:
    store = sp.Spill(td)
    piccolo = '{"percentage": 51, "plugged": "UNPLUGGED", "health": "good"}'
    grande = "# licenza MIT\n" + "import os\n" * 400
    msgs = [{"role": "system", "content": "sei MALG"},
            {"role": "user", "content": "quanta batteria ho?"},
            {"role": "tool", "content": piccolo},
            {"role": "tool", "content": grande},
            {"role": "user", "content": "quanta batteria ho?"}]
    out = sp.spill_messaggi(msgs, store, soglia_caratteri=640)
    ok("nessun messaggio cancellato", len(out) == len(msgs))
    ok("il JSON che risponde resta in linea", out[2]["content"] == piccolo)
    ok("il payload inutile e' fuori dal prompt", len(out[3]["content"]) < len(grande))
    ident = out[3].get("ramo")
    ok("ramo registrato con indirizzo", bool(ident))
    ok("recupero BYTE IDENTICI", store.get(ident) == grande)
    ok("l'indice contiene il ramo", ident in store.indice())
    primo = store.indice()
    store.put("x" * 2000, etichetta="altro")
    ok("indice append-only, prefisso stabile", store.indice().startswith(primo))
    ok("anteprima meccanica del codice", "import" in store.indice())

    ok("indice: una riga per ramo", len(store.indice().splitlines()) == 2)

# --- integrazione: il percorso VERO della libreria ---
import bocconcini as _b
_cl = _b.LlamaCppClient("http://127.0.0.1:1", n_ctx=4096, cognitive_limit=2048)
_piccolo = '{"percentage": 51, "plugged": "UNPLUGGED"}'
_grande = "# licenza MIT\n" + "import os\n" * 900
_msgs = [{"role": "system", "content": "Sei MALG, usi i tool. " * 10},
         {"role": "user", "content": "quanta batteria ho?"},
         {"role": "tool", "content": _piccolo},
         {"role": "tool", "content": _grande},
         {"role": "user", "content": "quanta batteria ho?"}]
_meta = {}
_out = _cl._reduce_messages(_msgs, 2048, None, _meta)
ok("loop: nessun messaggio cancellato", len(_out) == len(_msgs))
ok("loop: il tool che risponde e' intatto",
   any(m.get("content") == _piccolo for m in _out))
ok("loop: prompt sotto la finestra cognitiva", _cl._prompt_tokens(_out) <= 2048)
ok("loop: nessuna cancellazione per anzianita", "history_dropped" not in _meta)
ok("loop: byte identici dal percorso vero",
   _cl._store.get(_meta["rami"][0]) == _grande)

# --- A/B: il dato letto PRESTO deve sopravvivere a un payload grosso dopo ---
_ab = [{"role": "system", "content": "breve"},
       {"role": "user", "content": "Dati batteria: " + _piccolo},
       {"role": "assistant", "content": "Ricevuto."},
       {"role": "user", "content": "File: " + _grande},
       {"role": "assistant", "content": "Ricevuto."},
       {"role": "user", "content": "Quanta batteria ho?"}]
_c2 = _b.LlamaCppClient("http://127.0.0.1:1", n_ctx=4096, cognitive_limit=2048)
_o2 = _c2._reduce_messages(_ab, 2048, None, {})
ok("A/B: tutti i messaggi restano", len(_o2) == len(_ab))
ok("A/B: il dato letto presto sopravvive",
   any(_piccolo in str(m.get("content", "")) for m in _o2))

print("\n%d verifiche, %d fallite" % (n, fail))
raise SystemExit(1 if fail else 0)
