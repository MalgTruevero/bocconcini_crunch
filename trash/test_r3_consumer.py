"""Test R3: Consumer test. Tool data must survive reduction intact."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# R2: Import ONLY from the public entry point
from bocconcini import LlamaCppClient

def test_tool_result_survives_tight_budget():
    """Verify _reduce_messages does not drop or mangle a tool result."""
    client = LlamaCppClient("http://127.0.0.1:8082")
    
    # Simulate a history with a system prompt, a user request, and a tool result
    msgs = [
        {"role": "system", "content": "Sei un assistente utile."},
        {"role": "user", "content": "Quanta batteria ho?"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "function": {"name": "batteria", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": '{"percentage": 51}'}
    ]
    
    meta = {}
    # Force a very tight budget to trigger reduction logic
    budget = 150 
    
    # This is the exact method chat_full calls internally
    reduced_msgs = client._reduce_messages(msgs, budget, "Quanta batteria ho?", meta)
    
    # Find the tool message in the reduced output
    tool_msgs = [m for m in reduced_msgs if m.get("role") == "tool"]
    assert len(tool_msgs) == 1, f"Expected 1 tool message, found {len(tool_msgs)}"
    
    tool_content = tool_msgs[0].get("content", "")
    assert "51" in tool_content, f"Tool data was mangled or dropped! Content: {tool_content}"
    assert tool_content == '{"percentage": 51}', f"Tool data was altered! Expected exact match, got: {tool_content}"
    
    print("OK: Tool result {'percentage': 51} survived tight budget reduction 100% intact")

if __name__ == "__main__":
    try:
        test_tool_result_survives_tight_budget()
        print("\nR3 CONSUMER TEST: PASSED")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nR3 CONSUMER TEST: FAILED -> {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nR3 CONSUMER TEST: ERROR -> {e}")
        sys.exit(1)
