from bocconcini.memory import _evict, _msg_tokens

print("=== TEST OFFLINE DI _evict ===")

# Simula una conversazione con 3 letture di rami (tool results grandi)
msgs = [
    {"role": "system", "content": "Regole del documento. " * 20},
    {"role": "user", "content": "Qual e' il codice segreto?"},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "function": {"name": "leggi_nodo", "arguments": '{"id": "sec_000"}'}}]},
    {"role": "tool", "tool_call_id": "1", "content": "Testo del ramo zero con dettagli. " * 40, "_node": "sec_000"},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "2", "function": {"name": "leggi_nodo", "arguments": '{"id": "sec_001"}'}}]},
    {"role": "tool", "tool_call_id": "2", "content": "Testo del ramo uno con dettagli. " * 40, "_node": "sec_001"},
    {"role": "assistant", "content": "", "tool_calls": [{"id": "3", "function": {"name": "leggi_nodo", "arguments": '{"id": "sec_002"}'}}]},
    {"role": "tool", "tool_call_id": "3", "content": "Testo del ramo due con dettagli. " * 40, "_node": "sec_002"},
]

cpt, ovh = 3.2, 8.0
tok_before = _msg_tokens(msgs, cpt, ovh)
print("Token prima di eviction: %d" % tok_before)

# Budget stretto: forza l'eviction di almeno un vecchio ramo
budget = tok_before - 150

removed = _evict(msgs, budget, cpt, ovh, "codice segreto")
tok_after = _msg_tokens(msgs, cpt, ovh)
print("Rimossi (stub): %d" % removed)
print("Token dopo eviction: %d (target <= %d)" % (tok_after, budget))

# Verifica 1: il ramo più recente (sec_002) NON deve essere toccato
last_tool_content = msgs[-1]["content"]
ok_fresh = "Testo del ramo due" in last_tool_content
print("Ramo piu' recente intatto:", "OK" if ok_fresh else "FALLITO")

# Verifica 2: almeno un vecchio ramo deve essere stato stubbato
stubbed = [m for m in msgs if m.get("role") == "tool" and m.get("_stub")]
print("Rami stubbati: %d" % len(stubbed))

# Verifica 3: il contenuto stub deve menzionare che il testo è su disco
ok_stub_msg = all("on disk" in m["content"].lower() or "su disco" in m["content"].lower() or "evicted" in m["content"].lower() for m in stubbed)
print("Stub dichiara reversibilita':", "OK" if ok_stub_msg else "FALLITO")

# Verifica 4: il conteggio removed corrisponde al numero di stub
ok_count = removed == len(stubbed)
print("Conteggio removed coerente:", "OK" if ok_count else "FALLITO")

print()
if ok_fresh and len(stubbed) >= 1 and ok_stub_msg and ok_count and removed >= 1:
    print("TEST _evict SUPERATO")
else:
    print("TEST _evict FALLITO")
    # Stampa lo stato per debug
    for i, m in enumerate(msgs):
        if m.get("role") == "tool":
            print("  [%d] node=%s stub=%s content=%.60s" % (i, m.get("_node"), m.get("_stub"), m["content"]))
