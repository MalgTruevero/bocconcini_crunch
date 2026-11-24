"""V4: agentic cycle via chat_full. The tool datum must reach the answer."""
from bocconcini import LlamaCppClient

def test_tool_datum_reaches_answer():
    client = LlamaCppClient("http://127.0.0.1:8082")
    filler = "Il registro di sistema riporta attivita di routine senza eventi rilevanti. " * 120
    msgs = [{"role": "system", "content": "Rispondi in italiano, brevissimo."}]
    for i in range(6):
        msgs.append({"role": "user", "content": "Nota %d: %s" % (i, filler)})
        msgs.append({"role": "assistant", "content": "Ricevuto."})
    msgs.append({"role": "user", "content": "Quanta batteria ho?"})
    msgs.append({"role": "assistant", "content": "", "tool_calls": [
        {"id": "call_1", "type": "function",
         "function": {"name": "batteria", "arguments": "{}"}}]})
    msgs.append({"role": "tool", "tool_call_id": "call_1",
                 "content": '{"percentage": 51}'})
    reply = client.chat_full(messages=msgs, max_tokens=64, stream=False, auto_reduce=True)
    print("RISPOSTA:", reply.text.strip()[:200])
    assert "51" in reply.text, "il dato del tool non e' arrivato alla risposta"
    print("V4 PASSED: 51 arrivato alla risposta via chat_full")

if __name__ == "__main__":
    test_tool_datum_reaches_answer()
