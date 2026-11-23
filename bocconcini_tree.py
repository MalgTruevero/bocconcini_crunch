"""Deprecated alias: use bocconcini (or bocconcini.memory) instead.

.. deprecated:: 5.0.0
    Removed in 6.0.0; import DocTree and co. from bocconcini.
"""
import warnings as _w
from bocconcini.memory import *  # noqa: F401,F403
from bocconcini.memory import __all__  # noqa: F401

_w.warn("bocconcini_tree is deprecated since 5.0.0, removed in 6.0.0; "
        "use from bocconcini import DocTree instead.",
        DeprecationWarning, stacklevel=2)
