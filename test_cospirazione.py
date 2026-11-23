import os
import sys
import time
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bocconcini as b
import bocconcini_memory as t

BASE_URL = os.environ.get("BOCCONCINI_BASE_URL", "http://127.0.0.1:8082")

def genera_documento_trappola(ripetizioni_rumore: int = 380) -> str:
    """Genera ~25.000 token con 3 indizi multi-hop e 5 catene trappola quasi identiche."""
    rumore_base = (
        "2026-11-18 08:14:22 [INFO] kernel: sched_balance: bilanciamento carico core 0-7 completato senza latenze.\n"
        "2026-11-18 08:14:25 [DEBUG] net_stack: pacchetto TCP ACK verificato su interfaccia eth0, checksum OK.\n"
        "2026-11-18 08:14:29 [INFO] storage_mgr: sync buffer I/O completato su /dev/block/sda14 (temp 34.2C).\n"
    )
    blocco = rumore_base * ripetizioni_rumore

    # --- CATENA VERA (3 Salti: 5% -> 50% -> 95%) ---
    hop_1_vero = "\n[AUDIT-SEC-01] Il dipartimento CRIPTO-OMEGA utilizza esclusivamente la chiave hardware K77-ZULU.\n"
    hop_2_vero = "\n[INFRA-MAP-44] L'infrastruttura del dipartimento CRIPTO-OMEGA gestisce in via esclusiva il nodo server VALKYRIE-9 situato nel settore 7B.\n"
    hop_3_vero = "\n[PROTOCOLLO-ROSSO] L'accesso al nodo server VALKYRIE-9 nel settore 7B richiede la password master 'OBSIDIAN-404' per avviare il dump.\n"

    # --- TRAPPOLE (Distrattori progettati per ingannare la compressione e i regex) ---
    trappola_a = (
        "\n[AUDIT-SEC-02] Il dipartimento CRIPTO-ALPHA utilizza esclusivamente la chiave hardware K77-ALFA.\n"
        "[INFRA-MAP-45] L'infrastruttura del dipartimento CRIPTO-ALPHA gestisce il nodo server VALKYRIE-8 situato nel settore 7A.\n"
        "[PROTOCOLLO-ROSSO] L'accesso al nodo server VALKYRIE-8 nel settore 7A richiede la password master 'GRANITE-101'.\n"
    )
    trappola_b = (
        "\n[AUDIT-SEC-03] Il dipartimento CRIPTO-OMEGA-2 (dismesso) usava la chiave K77-ZULU-OLD.\n"
        "[INFRA-MAP-46] Il nodo server VALKYRIE-9 nel settore 7A (replica) richiede la password 'QUARTZ-999'.\n"
    )
    trappola_c = (
        "\n[PROTOCOLLO-ROSSO] L'accesso al nodo server VALKYRIE-7 nel settore 7B richiede la password master 'BASALT-303'.\n"
    )

    n = len(blocco)
    doc = (
        blocco[:int(n * 0.05)] + hop_1_vero +
        blocco[int(n * 0.05):int(n * 0.25)] + trappola_a +
        blocco[int(n * 0.25):int(n * 0.50)] + hop_2_vero +
        blocco[int(n * 0.50):int(n * 0.72)] + trappola_b +
        blocco[int(n * 0.72):int(n * 0.88)] + trappola_c +
        blocco[int(n * 0.88):int(n * 0.95)] + hop_3_vero +
        blocco[int(n * 0.95):]
    )
    return doc

def main():
    print("=" * 65)
    print("BENCHMARK ESTREMO: MULTI-HOP DISTRIBUITO + TRAPPOLE")
    print("=" * 65)

    doc = genera_documento_trappola()
    stima_tok = b.estimate_tokens(doc, "text")
    print(f"Dimensione documento: {len(doc):,} caratteri (~{stima_tok:,} token stimati)")

    domanda = (
        "Analizza i log e rispondi in modo conciso: qual è la password master esatta "
        "richiesta per avviare il dump sul nodo server gestito dal dipartimento "
        "che utilizza la chiave hardware K77-ZULU?"
    )

    client = b.LlamaCppClient(base_url=BASE_URL)
    info = client.stats()
    print(f"Server: {BASE_URL} | n_ctx: {info.get('n_ctx')} | cognitive_limit: {client.working_budget()}")

    # ---------------------------------------------------------
    # FASE 1: Test con auto_reduce=True (compressione diretta)
    # ---------------------------------------------------------
    print("\n--- FASE 1: LlamaCppClient (auto_reduce=True) ---")
    prompt_diretto = f"DOCUMENTO DI LOG:\n{doc}\n\nDOMANDA: {domanda}"
    t0 = time.time()
    try:
        r1 = client.chat_full(
            prompt=prompt_diretto,
            temperature=0.0,
            auto_reduce=True,
            max_tokens=150,
            continua=False
        )
        dt1 = time.time() - t0
        ok1 = "OBSIDIAN-404" in r1.text.upper()
        print(f"Tempo: {dt1:.1f}s | Reduced: {r1.meta.get('reduced')} | Hops risolti: {'SI' if ok1 else 'NO'}")
        print(f"Risposta: {r1.text.strip()}")
        print(f"Esito Fase 1: {'✅ PASS' if ok1 else '❌ FAIL (trappola o contesto perso)'}")
    except Exception as e:
        print(f"❌ ERRORE Fase 1: {e}")

    # ---------------------------------------------------------
    # FASE 2: Test con DocTree + naviga (esplorazione ad albero)
    # ---------------------------------------------------------
    print("\n--- FASE 2: DocTree + naviga (Multi-Hop su disco) ---")
    t0 = time.time()
    try:
        chunks = b.split_text(doc, "audit.log", kind="text", max_tokens=500, overlap=50)
        nodi = []
        for idx, c in enumerate(chunks):
            meta_lbl = t.etichetta(c.text)
            nodi.append(t.DocNode(
                id=f"sec_{idx:03d}",
                label=meta_lbl["label"],
                summary=meta_lbl["summary"],
                text=c.text,
                tokens=c.token_count_estimate()
            ))

        with tempfile.TemporaryDirectory() as td:
            tree = t.DocTree(Path(td))
            tree.save("cospirazione", nodi)
            print(f"Albero creato: {len(nodi)} rami su disco.")

            res = t.naviga(
                client=client,
                tree=tree,
                session="cospirazione",
                question=domanda,
                budget_tokens=client.working_budget(),
                max_hops=6,          # Servono almeno 3 letture + ricerche
                max_tokens=200,
                temperature=0.0
            )
            dt2 = time.time() - t0
            ok2 = "OBSIDIAN-404" in res["text"].upper()
            print(f"Tempo: {dt2:.1f}s | Rami letti: {res['meta'].get('nodes_read')} | Ricerche: {res['meta'].get('searches')}")
            print(f"Risposta: {res['text'].strip()}")
            print(f"Esito Fase 2: {'✅ PASS' if ok2 else '❌ FAIL'}")
    except Exception as e:
        print(f"❌ ERRORE Fase 2: {e}")

if __name__ == "__main__":
    main()
