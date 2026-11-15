# bocconcini

**Zero runtime dependencies.** A Python client for local LLMs whose *usable*
window is smaller than the advertised one. Born on a Samsung S20 Ultra in
Termux, built to never lie about what it did.

Why "bocconcini"? A child, a huge cake, a small mouth: [STORIA.md](STORIA.md).
Italian edition: [README.it.md](README.it.md).

## Verification status

- **Verified live:** KoboldCpp, Samsung S20 Ultra, smol-tools-4b.
- **Implemented but NOT verified live:** llama.cpp native, Ollama, cloud.
- 43 checks: `python test_bocconcini.py` and `python test_regressioni.py`.

## What it does

- Chunks text / Python / JSON, never inside a string or an escape sequence.
- Output budget from the context window, not from generation speed.
- **Cognitive window:** `client.calibra()` measures how much the model actually
  understands, not how much the server can hold. Only a passed probe is stored.
- Detects silent prompt truncation, and only near the window: far from it a
  shortfall is our own estimate, not a cut.
- Continues answers cut by the token limit, stitching without duplicates.
- Disk-backed tree: `DocTree`, `naviga`, `albero_codice` (lossless AST partition).
- `trova_fatti`: deterministic scan for codes / IDs / measurements / keys,
  each with its surrounding sentence.

Some public names are Italian (`trova_fatti`, `contesto`, `invia_adattivo`).
They are kept as-is for compatibility.

## What it does

- Chunks text / Python / JSON, never inside a string or an escape sequence.
- Output budget from the context window, not from generation speed.
- **Cognitive window:** `client.calibra()` measures how much the model actually
  understands, not how much the server can hold. Only a passed probe is stored.
- Detects silent prompt truncation, and only near the window: far from it a
  shortfall is our own estimate, not a cut.
- Continues answers cut by the token limit, stitching without duplicates.
- Disk-backed tree: `DocTree`, `naviga`, `albero_codice` (lossless AST partition).
- `trova_fatti`: deterministic scan for codes / IDs / measurements / keys,
  each with its surrounding sentence.

Some public names are Italian (`trova_fatti`, `contesto`, `invia_adattivo`).
They are kept as-is for compatibility.

## Quickstart

    from bocconcini import LlamaCppClient
    cl = LlamaCppClient("http://127.0.0.1:5001")
    print(cl.chat("Answer with one word: ok"))

## Finding facts without blind compression

    from bocconcini_tree import trova_fatti
    facts = trova_fatti(document)      # reads every character, no model call
    context = "\n".join(f["contesto"] for f in facts)

Measured on the reference phone, 4 codes hidden in 32,000 characters:
blind compression 0/4 in 2562 s; trova_fatti 4/4 in 52 s,
~265 prompt tokens instead of ~10923.

`auto_reduce=True` is **lossy**: it can discard the middle of a document.
To find facts, use `trova_fatti` or explicit chunking.

## License

MIT. Keeping the name and the story is a courtesy, not a requirement.
