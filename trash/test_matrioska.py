import tempfile
from pathlib import Path

from bocconcini import (
    DocNode,
    DocTree,
    naviga,
    LlamaCppClient,
)

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
LIVE_MODEL = True                 # False = solo test struttura, senza modello
BASE_URL = None                   # es. "http://127.0.0.1:8082"

TOTAL_LEAVES = 128
TARGET_LEAF = 77
NEEDLE = "4271"
MAX_CHILDREN = 8
SESSION = "matrioska_test"

# ------------------------------------------------------------------
# Costruzione manuale della matrioska
# ------------------------------------------------------------------
def build_leaves(total: int, target: int, needle: str):
    leaves = []

    for i in range(total):
        text = f"Sezione {i}. Contenuto ordinario senza dati speciali."

        if i == target:
            text += f" Qui si trova il codice di verifica {needle}."

        leaves.append(
            DocNode(
                id=f"leaf_{i:03d}",
                label=f"Sezione {i}",
                summary="",
                text=text,
                tokens=max(8, len(text) // 4),
                children=[],
            )
        )

    return leaves


def build_matrioska(nodes, max_children: int):
    """
    Raggruppa i nodi in contenitori da max_children figli.

    128 foglie:
      128 -> 16 contenitori -> 2 radici
    """
    level = nodes
    depth = 0

    while len(level) > max_children:
        next_level = []

        for i in range(0, len(level), max_children):
            group = level[i:i + max_children]

            container_id = f"cont_{depth}_{i // max_children:03d}"
            label = f"Container {depth}:{i // max_children}"
            summary = (
                f"Contains {len(group)} branches "
                f"from {group[0].id} to {group[-1].id}"
            )

            next_level.append(
                DocNode(
                    id=container_id,
                    label=label,
                    summary=summary,
                    text="",
                    tokens=sum(n.tokens for n in group),
                    children=group,
                )
            )

        level = next_level
        depth += 1

    return level


def check_width(nodes, max_children: int):
    """Verifica che nessun nodo abbia più di max_children figli."""
    stack = list(nodes)

    while stack:
        node = stack.pop()
        assert len(node.children) <= max_children, (
            f"node {node.id} has {len(node.children)} children"
        )
        stack.extend(node.children)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    leaves = build_leaves(TOTAL_LEAVES, TARGET_LEAF, NEEDLE)
    roots = build_matrioska(leaves, MAX_CHILDREN)

    check_width(roots, MAX_CHILDREN)

    with tempfile.TemporaryDirectory() as tmp:
        tree = DocTree(Path(tmp))

        info = tree.save(SESSION, roots)
        print("Tree saved:", info)

        idx = tree.index(SESSION)
        print("Roots:", len(idx["nodes"]))

        root_view = tree.vista(
            SESSION,
            None,
            budget_tokens=400,
            chars_per_token=3.2,
        )

        print("\n--- ROOT VIEW ---")
        print(root_view["text"])

        target_id = f"leaf_{TARGET_LEAF:03d}"
        target_text = tree.load(SESSION, target_id)

        print("\n--- TARGET LEAF DIRECT CHECK ---")
        print("Target id:", target_id)
        print("Target text:", target_text)

        assert NEEDLE in target_text, "target leaf does not contain needle"

        if not LIVE_MODEL:
            print("\nDry run completed. Set LIVE_MODEL=True to test the model.")
            return

        client_kwargs = {}
        if BASE_URL:
            client_kwargs["base_url"] = BASE_URL

        client = LlamaCppClient(**client_kwargs)

        question = "Trova il codice di verifica presente nel documento."

        print("\n--- LIVE NAVIGAZIONE ---")
        print("Question:", question)

        out = naviga(
            client,
            tree,
            SESSION,
            question,
            budget_tokens=1500,
            chars_per_token=3.2,
            max_hops=8,
            max_repeats=2,
            max_tokens=300,
            temperature=0.0,
            require_read=True,
            max_calls=1,
        )

        print("\n--- ANSWER ---")
        print(out.get("text", ""))

        print("\n--- META ---")
        for k, v in out.get("meta", {}).items():
            print(f"{k}: {v}")

        if NEEDLE in out.get("text", ""):
            print("\nOK: matrioska funzionante, ago trovato.")
        else:
            print("\nFAIL: ago non trovato nella risposta finale.")
            print("\n--- ULTIMI MESSAGGI ---")
            for m in out.get("messages", [])[-12:]:
                print(m)


if __name__ == "__main__":
    main()
