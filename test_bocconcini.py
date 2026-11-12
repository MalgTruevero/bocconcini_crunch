"""Verifica le garanzie di bocconcini. Nessun server, gira in un secondo."""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path.home() / "malg" / "libreria_bocconcini"))
import bocconcini as b

fails = []
n_check = 0
def check(nome, ok, dettaglio=""):
    global n_check
    n_check += 1
    print(("OK   " if ok else "FAIL ") + nome + ("" if ok else "  <- " + dettaglio))
    if not ok:
        fails.append(nome)

def chiusa(s):
    """True se la stringa non finisce dentro un literal JSON."""
    in_str = esc = False
    for ch in s:
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
        elif ch == '"': in_str = True
    return not in_str

prosa = ("Paragrafo con parole italiane. " * 40 + "\n\n") * 12
py = "\n".join("def f%d(x):\n    return x + %d\n" % (i, i) for i in range(150))
js = json.dumps({"voci": [{"id": i, "nome": "nome %d" % i, "tag": ["a", "b"]}
                          for i in range(150)]}, indent=1)

casi = [("prosa", prosa, "text"), ("python", py, "python"), ("json", js, "json")]
for nome, testo, kind in casi:
    for mc in (200, 700, 3000):
        ch = b.split_text(testo, nome, kind=kind, max_chars=mc, max_tokens=100000,
                          min_chars=50, overlap=0)
        grandi = [len(c) for c in ch if len(c) > mc]
        check("%s max_chars=%d" % (nome, mc), not grandi,
              "chunk da %d" % (max(grandi) if grandi else 0))
        visti = bytearray(len(testo))
        for c in ch:
            for i in range(c.start, c.end):
                visti[i] = 1
        buchi = [i for i in range(len(testo)) if not visti[i] and not testo[i].isspace()]
        check("%s copertura mc=%d" % (nome, mc), not buchi,
              "%d caratteri non whitespace persi" % len(buchi))
    ch = b.split_text(testo, nome, kind=kind, max_chars=3000, max_tokens=80,
                      min_chars=50, overlap=0)
    sfori = [b.estimate_tokens(c.text, kind) for c in ch
             if b.estimate_tokens(c.text, kind) > 80]
    check("%s limite token" % nome, not sfori, "max %d" % (max(sfori) if sfori else 0))

ch = b.split_text(py, "x.py", kind="python", max_chars=300, max_tokens=100000,
                  min_chars=50, overlap=0)
male = [i for i, c in enumerate(ch) if c.end < len(py) and py[c.end - 1] != "\n"]
check("python taglia a fine riga", not male, "chunk %s" % male[:5])

ch = b.split_text(js, "x.json", kind="json", max_chars=400, max_tokens=100000,
                  min_chars=50, overlap=0)
male = [i for i, c in enumerate(ch) if not chiusa(c.text)]
check("json taglia fuori dalle stringhe", not male, "chunk %s" % male[:5])

ch = b.split_text(prosa, "p", kind="text", max_chars=1000, max_tokens=100000,
                  min_chars=50, overlap=0, temperature_provider=lambda: 48.0)
check("scala termica a 48C", all(len(c) <= 400 for c in ch),
      "max %d" % max(len(c) for c in ch))

check("stitch toglie il duplicato", b._stitch("Il valore di temperatura supera i 45 gradi",
      "supera i 45 gradi e continua a salire") == " e continua a salire")
check("stitch ignora sovrapposizioni corte", b._stitch("abc def ghi", "ghi jkl") == "ghi jkl")
check("thinking chiuso", b.split_thinking("<think>x</think>risposta")[0] == "risposta")
check("thinking aperto = troncato", b.split_thinking("<think>sto pensando") == ("", "sto pensando", True))
check("tool call nel testo", b.parse_tool_calls_from_text(
    '{"name":"f","arguments":{}}', ["f"])[0] != [])
check("esempio JSON in prosa non eseguito", b.parse_tool_calls_from_text(
    'usa {"name":"f","arguments":{}} cosi', ["f"])[0] == [])
check("extract_local non vuoto", len(b.extract_local("x" * 500 + " temperatura", "temperatura", 100)) > 0)

print("\n%d verifiche, %d fallite" % (n_check, len(fails)))
if fails:
    print("Da guardare:", ", ".join(fails))
