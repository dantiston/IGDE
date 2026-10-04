"""The processor backends IGDE knows about.

To support another processor, subclass ``base.Backend`` and add it here.
"""

from __future__ import annotations

from pathlib import Path

from .ace import AceBackend
from .base import Backend, GrammarInfo

BACKENDS: dict[str, Backend] = {b.key: b for b in (AceBackend(),)}


def get(key: str) -> Backend:
    try:
        return BACKENDS[key]
    except KeyError:
        raise KeyError(f"Unknown processor type {key!r}.") from None


def all_backends() -> list[Backend]:
    return list(BACKENDS.values())


def classify(p: Path, is_dir: bool) -> str | None:
    for b in BACKENDS.values():
        hint = b.classify(p, is_dir)
        if hint:
            return hint
    return None


def describe_grammar(p: Path, prefer: str | None = None) -> tuple[Backend, GrammarInfo] | None:
    """The first backend (*prefer* first) that recognises the grammar at *p*.

    Raises ValueError if a backend recognises it but finds it broken and no
    other backend reads it."""
    order = sorted(BACKENDS.values(), key=lambda b: b.key != prefer)
    error = None
    for b in order:
        try:
            info = b.describe_grammar(p)
        except ValueError as e:
            error = error or e
            continue
        if info:
            return b, info
    if error:
        raise error
    return None
