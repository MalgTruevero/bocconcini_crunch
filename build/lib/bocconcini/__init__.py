"""bocconcini - Local LLM client for small usable windows."""

from .client import (
    LlamaCppClient, OpenAICompatClient, ChatReply, ModelError, Chunk,
    split_text, iter_chunks, detect_kind, estimate_tokens,
    LlamaServerTokenizer, split_thinking, parse_tool_calls_from_text,
    extract_local, ask_stepwise, get_model_info,
)
from .memory import (
    DocNode, DocTree, TreeError, etichetta, naviga, albero_codice,
    trova_fatti, prepara_albero_ricco, matrioska_profile, prepare_matrioska_tree, calibra_navigazione,
)
from .rami import Spill, spill_messaggi

__all__ = [
    "LlamaCppClient", "OpenAICompatClient", "ChatReply", "ModelError",
    "Chunk", "split_text", "iter_chunks", "detect_kind", "estimate_tokens",
    "LlamaServerTokenizer", "split_thinking", "parse_tool_calls_from_text",
    "extract_local", "ask_stepwise", "get_model_info",
    "DocNode", "DocTree", "TreeError", "etichetta", "naviga", "albero_codice",
    "trova_fatti", "prepara_albero_ricco", "matrioska_profile", "prepare_matrioska_tree", "calibra_navigazione",
    "Spill", "spill_messaggi",
]

from . import client, docs
from .client import *
from .client import __version__
__all__ = sorted(set(__all__) | set(client.__all__) | {"docs", "__version__"})
