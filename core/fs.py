"""Local filesystem access for the file manager.

IGDE runs on the user's own machine and only listens on loopback, so it
can show and edit the user's grammar files in place.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

MAX_TEXT_BYTES = 5 * 1024 * 1024
GRAMMAR_SOURCE_EXTS = {".tdl", ".rpp", ".vpm", ".mtr", ".tab", ".set", ".smi", ".txt", ".lsp", ".mem", ".dat"}

# Grammar images written by ACE don't have a documented magic number, so we
# recognise them by extension.
IMAGE_EXTS = {".dat", ".grm", ".ace"}


class FsError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def resolve(path: str | None) -> Path:
    if not path:
        return Path.home()
    p = Path(path).expanduser()
    if not p.is_absolute():
        raise FsError("Paths must be absolute.")
    return Path(os.path.normpath(p))


def classify(p: Path, is_dir: bool) -> str | None:
    """A hint about what a filesystem entry is, grammar-wise."""
    if is_dir:
        if (p / "ace" / "config.tdl").is_file() or (p / "config.tdl").is_file():
            return "grammar-dir"
        return None
    if p.name == "config.tdl" or (p.suffix == ".tdl" and p.parent.name == "ace" and "config" in p.stem):
        return "config"
    if p.suffix in IMAGE_EXTS:
        return "image"
    if p.suffix in GRAMMAR_SOURCE_EXTS:
        return "source"
    return None


def entry(p: Path, st=None) -> dict:
    try:
        st = st or p.stat()
        is_dir = stat.S_ISDIR(st.st_mode)
        size, mtime = (None if is_dir else st.st_size), st.st_mtime
    except OSError:
        is_dir, size, mtime = False, None, None
    return {
        "name": p.name or str(p),
        "path": str(p),
        "kind": "dir" if is_dir else "file",
        "size": size,
        "mtime": mtime,
        "hint": classify(p, is_dir),
    }


def list_dir(path: str | None, show_hidden=False) -> dict:
    p = resolve(path)
    if not p.exists():
        raise FsError(f"{p} does not exist.", 404)
    if not p.is_dir():
        raise FsError(f"{p} is not a directory.")
    entries = []
    try:
        with os.scandir(p) as it:
            for de in it:
                if not show_hidden and de.name.startswith("."):
                    continue
                try:
                    st = de.stat()
                except OSError:
                    st = None
                entries.append(entry(Path(de.path), st) if st else entry(Path(de.path)))
    except PermissionError as e:
        raise FsError(f"Permission denied: {p}", 403) from e
    entries.sort(key=lambda e: (e["kind"] != "dir", e["name"].lower()))
    parent = str(p.parent) if p.parent != p else None
    return {"path": str(p), "parent": parent, "entries": entries, "hint": classify(p, True)}


def roots() -> list[dict]:
    out = [{"name": "Home", "path": str(Path.home())}]
    cwd = Path.cwd()
    if cwd != Path.home():
        out.append({"name": "IGDE directory", "path": str(cwd)})
    out.append({"name": "Filesystem root", "path": str(Path(Path.cwd().anchor))})
    return out


def _looks_binary(data: bytes) -> bool:
    return b"\x00" in data[:8192]


def read_text(path: str) -> dict:
    p = resolve(path)
    if not p.is_file():
        raise FsError(f"{p} is not a file.", 404)
    st = p.stat()
    if st.st_size > MAX_TEXT_BYTES:
        raise FsError(f"{p.name} is too large to open in the editor ({st.st_size} bytes).", 413)
    data = p.read_bytes()
    if _looks_binary(data):
        raise FsError(f"{p.name} is a binary file.", 415)
    return {
        "path": str(p),
        "content": data.decode("utf-8", "replace"),
        "size": st.st_size,
        "mtime": st.st_mtime,
        "writable": os.access(p, os.W_OK),
    }


def write_text(path: str, content: str, expected_mtime: float | None) -> dict:
    p = resolve(path)
    if p.exists() and not p.is_file():
        raise FsError(f"{p} is not a file.")
    if p.exists() and expected_mtime is not None and abs(p.stat().st_mtime - expected_mtime) > 1e-6:
        raise FsError(f"{p.name} was changed on disk since it was opened; reload it first.", 409)
    if not p.parent.is_dir():
        raise FsError(f"{p.parent} does not exist.", 404)
    tmp = p.with_name(f".{p.name}.igde-tmp")
    tmp.write_text(content, encoding="utf-8")
    if p.exists():
        os.chmod(tmp, stat.S_IMODE(p.stat().st_mode))
    os.replace(tmp, p)
    st = p.stat()
    return {"path": str(p), "size": st.st_size, "mtime": st.st_mtime}


_GRAMMAR_TOP_RE = re.compile(r"^\s*grammar-top\s*:=\s*\"?([^\".\s]+(?:\.[^\".\s]+)*)\"?\s*\.", re.M)


def find_grammar_config(path: str) -> dict:
    """Given a directory, config file, or image, work out what grammar is there."""
    p = resolve(path)
    if p.is_dir():
        for cand in (p / "ace" / "config.tdl", p / "config.tdl"):
            if cand.is_file():
                return _describe_config(cand)
        images = sorted(x for x in p.iterdir() if x.suffix in IMAGE_EXTS and x.is_file())
        if images:
            return {"kind": "image", "imagePath": str(images[0]), "name": images[0].stem}
        raise FsError(f"No ACE config.tdl or grammar image found in {p}.", 404)
    if not p.is_file():
        raise FsError(f"{p} does not exist.", 404)
    if p.suffix == ".tdl":
        return _describe_config(p)
    return {"kind": "image", "imagePath": str(p), "name": p.stem}


def _describe_config(cfg: Path) -> dict:
    root = cfg.parent.parent if cfg.parent.name == "ace" else cfg.parent
    text = cfg.read_text(encoding="utf-8", errors="replace")
    if "grammar-top" not in text:
        raise FsError(f"{cfg} does not look like an ACE config file (no grammar-top setting).")
    m = _GRAMMAR_TOP_RE.search(text)
    return {
        "kind": "source",
        "configPath": str(cfg),
        "name": root.name,
        "grammarTop": m.group(1) if m else None,
    }


SKIP_DIRS = {".git", ".svn", "__pycache__", "node_modules", "tsdb", "www"}


def grammar_tree(root: Path, max_entries=5000) -> list[dict]:
    """Grammar files under *root* (TDL, REPP, VPM, ...) as a flat list."""
    out = []
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(filenames):
            p = Path(dirpath) / f
            if p.suffix in GRAMMAR_SOURCE_EXTS - {".dat", ".mem"} or f in ("Version.lsp", "METADATA"):
                out.append({"path": str(p), "rel": str(p.relative_to(root)), "size": p.stat().st_size})
                if len(out) >= max_entries:
                    return out
    return out
