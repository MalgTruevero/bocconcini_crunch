"""bocconcini - Local LLM client for small usable windows."""

from .client import (
    LlamaCppClient, OpenAICompatClient, ChatReply, ModelError, Chunk,
    split_text, iter_chunks, detect_kind, estimate_tokens,
    LlamaServerTokenizer, split_thinking, parse_tool_calls_from_text,
    extract_local, ask_stepwise,
)
from .memory import (
    DocNode, DocTree, TreeError, etichetta, naviga, albero_codice,
    trova_fatti, prepara_albero_ricco, calibra_navigazione,
)
from .rami import Spill, spill_messaggi

__all__ = [
    "LlamaCppClient", "OpenAICompatClient", "ChatReply", "ModelError",
    "Chunk", "split_text", "iter_chunks", "detect_kind", "estimate_tokens",
    "LlamaServerTokenizer", "split_thinking", "parse_tool_calls_from_text",
    "extract_local", "ask_stepwise",
    "DocNode", "DocTree", "TreeError", "etichetta", "naviga", "albero_codice",
    "trova_fatti", "prepara_albero_ricco", "calibra_navigazione",
    "Spill", "spill_messaggi",
]
