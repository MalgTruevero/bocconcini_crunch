import sys, pathlib
import bocconcini as bb
full = pathlib.Path(bb.__file__).read_text(encoding="utf-8")
print("righe:", len(full.splitlines()))
ch = bb.split_text(full, max_chars=3000, kind="python")
print("chunk:", len(ch), "max:", max(len(c.text) for c in ch))
print("tutti <=3000?", all(len(c.text)<=3000 for c in ch))
print("nessuno finisce con backslash?", all(not c.text.endswith("\\") for c in ch))
