# bocconcini

Client Python per LLM locali con finestra utile piccola. **Zero dipendenze runtime.**
Nata su Samsung S20 Ultra / Termux, per non mentire su cio' che ha fatto.

## Stato verificato

- Verificato dal vivo: KoboldCpp, Samsung S20 Ultra, smol-tools-4b.
- Implementati ma NON verificati dal vivo: llama.cpp native, Ollama, cloud.
- Test: python test_bocconcini.py e python test_regressioni.py (43 verifiche).

## Cosa fa

- Chunking di testo / Python / JSON: mai dentro stringhe o escape.
- Budget dal context window, non dalla velocita'.
- Finestra cognitiva: client.calibra() misura quanto il modello capisce davvero.
- Rileva il troncamento silenzioso del prompt solo vicino alla finestra.
- Continuazione delle risposte tagliate, senza duplicati.
- Albero su disco: bocconcini_tree.DocTree, naviga, albero_codice.
- trova_fatti: scansione deterministica di codici/sigle/misure/chiavi.

## Quickstart

    from bocconcini import LlamaCppClient
    cl = LlamaCppClient("http://127.0.0.1:5001")
    print(cl.chat("Rispondi con una parola: ok"))

## Cercare fatti senza compressione cieca

    from bocconcini_tree import trova_fatti
    fatti = trova_fatti(documento)

auto_reduce=True e' LOSSY: puo' buttare il centro di un documento.
Per cercare fatti usa trova_fatti o lo chunking esplicito.

## Licenza

MIT.

## Storia

Il nome nasce da una torta troppo grande per una bocca piccola: [STORIA.md](STORIA.md).
Se modifichi e ripubblichi, per cortesia porta con te quel file.
