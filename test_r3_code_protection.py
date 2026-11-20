"""Test R3-bis: Code protection. Python and JSON must survive reduction intact."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# R2: Import ONLY from the public entry point
from bocconcini import LlamaCppClient

def test_python_code_survives():
    """Verify Python code with indentation survives reduction."""
    client = LlamaCppClient("http://127.0.0.1:8082")
    
    python_code = '''def calculate_total(items):
    total = 0
    for item in items:
        if item["price"] > 0:
            total += item["price"] * item["quantity"]
    return total

# Example usage
cart = [{"price": 10, "quantity": 2}, {"price": 5, "quantity": 3}]
result = calculate_total(cart)
print(f"Total: {result}")'''
    
    msgs = [
        {"role": "system", "content": "Sei un assistente per sviluppatori Python."},
        {"role": "user", "content": "Mostrami una funzione per calcolare il totale di un carrello."},
        {"role": "assistant", "content": python_code}
    ]
    
    meta = {}
    budget = 200  # Tight budget to force reduction
    
    reduced_msgs = client._reduce_messages(msgs, budget, "Mostrami una funzione", meta)
    
    assistant_content = reduced_msgs[-1].get("content", "")
    
    # Check that the code is still valid Python (can be parsed)
    try:
        compile(assistant_content, "<string>", "exec")
        print("OK: Python code survived reduction and is still syntactically valid")
    except SyntaxError as e:
        print(f"FAIL: Python code was mangled! SyntaxError: {e}")
        print(f"Content after reduction:\n{assistant_content}")
        raise AssertionError("Python code was mangled during reduction")
    
    # Check that key elements are preserved
    assert "def calculate_total" in assistant_content, "Function definition was lost"
    assert "return total" in assistant_content, "Return statement was lost"
    assert "    total += item" in assistant_content, "Indented code was lost"

def test_json_code_survives():
    """Verify nested JSON survives reduction."""
    client = LlamaCppClient("http://127.0.0.1:8082")
    
    json_code = '''{
  "user": {
    "id": 12345,
    "name": "Alice",
    "preferences": {
      "theme": "dark",
      "notifications": true,
      "language": "it"
    },
    "orders": [
      {"id": 1, "total": 99.99, "items": ["book", "pen"]},
      {"id": 2, "total": 49.50, "items": ["coffee"]}
    ]
  },
  "metadata": {
    "version": "2.1.0",
    "timestamp": "2026-11-20T10:30:00Z"
  }
}'''
    
    msgs = [
        {"role": "system", "content": "Sei un assistente per gestione dati JSON."},
        {"role": "user", "content": "Mostrami la struttura di un utente con ordini."},
        {"role": "assistant", "content": json_code}
    ]
    
    meta = {}
    budget = 200  # Tight budget to force reduction
    
    reduced_msgs = client._reduce_messages(msgs, budget, "Mostrami la struttura", meta)
    
    assistant_content = reduced_msgs[-1].get("content", "")
    
    # Check that the JSON is still valid (can be parsed)
    import json
    try:
        parsed = json.loads(assistant_content)
        print("OK: JSON code survived reduction and is still valid JSON")
    except json.JSONDecodeError as e:
        print(f"FAIL: JSON was mangled! JSONDecodeError: {e}")
        print(f"Content after reduction:\n{assistant_content}")
        raise AssertionError("JSON was mangled during reduction")
    
    # Check that key elements are preserved
    assert "user" in parsed, "User object was lost"
    assert "orders" in parsed["user"], "Orders array was lost"
    assert parsed["user"]["id"] == 12345, "User ID was altered"
    assert len(parsed["user"]["orders"]) == 2, "Orders were lost"

if __name__ == "__main__":
    try:
        test_python_code_survives()
        test_json_code_survives()
        print("\nR3 CODE PROTECTION TEST: PASSED (2/2)")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nR3 CODE PROTECTION TEST: FAILED -> {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nR3 CODE PROTECTION TEST: ERROR -> {e}")
        sys.exit(1)
