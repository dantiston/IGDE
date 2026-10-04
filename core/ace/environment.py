"""Locating and validating the local ACE installation.

ACE is found, in order of precedence, from:

1. the ACE_ROOT configured in IGDE's settings,
2. the ``$ACE_ROOT`` environment variable,
3. ``ace`` on ``$PATH``.

An ACE_ROOT may be the ``ace`` binary itself or a directory containing it
(an unpacked ACE release such as ``ace-0.9.34/``, or a prefix with
``bin/ace``).
"""

from __future__ import annotations

import locale
import os
import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from django.conf import settings

VERSION_RE = re.compile(r"ACE version ([\d.]+)")


@dataclass
class AceStatus:
    ok: bool
    source: str | None  # "settings" | "env" | "path" | None
    aceRoot: str | None
    executable: str | None
    version: str | None
    error: str | None

    def to_dict(self):
        return asdict(self)


def _candidates(root: Path):
    root = root.expanduser()
    if root.is_file():
        yield root
        return
    yield root / "ace"
    yield root / "bin" / "ace"


def find_executable(root: str | os.PathLike) -> Path | None:
    for cand in _candidates(Path(root)):
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand.resolve()
    return None


def ace_version(executable: str | os.PathLike) -> str:
    """Run ``ace -V`` and return the version string (raises on failure)."""
    proc = subprocess.run(
        [str(executable), "-V"],
        capture_output=True,
        text=True,
        timeout=15,
        env=process_env(),
    )
    m = VERSION_RE.search(proc.stdout + proc.stderr)
    if not m:
        raise RuntimeError(
            f"{executable} does not look like ACE (output: {(proc.stdout + proc.stderr).strip()[:200]!r})"
        )
    return m.group(1)


def check(ace_root: str | None) -> AceStatus:
    """Resolve and validate ACE given the configured ACE_ROOT (may be empty)."""
    if ace_root:
        source, root = "settings", ace_root
    elif os.environ.get("ACE_ROOT"):
        source, root = "env", os.environ["ACE_ROOT"]
    else:
        found = shutil.which("ace")
        if not found:
            return AceStatus(
                False, None, None, None, None,
                "ACE not configured: set ACE_ROOT to the directory containing the ace binary.",
            )
        source, root = "path", found

    exe = find_executable(root)
    if exe is None:
        return AceStatus(
            False, source, root, None, None,
            f"No executable 'ace' found at {root} (looked for {root}, {root}/ace and {root}/bin/ace).",
        )
    try:
        version = ace_version(exe)
    except Exception as e:  # noqa: BLE001 - surface any failure to the user
        return AceStatus(False, source, root, str(exe), None, str(e))
    return AceStatus(True, source, root, str(exe), version, None)


def _utf8_locale() -> str:
    if platform.system() == "Darwin":
        return "en_US.UTF-8"
    return "C.UTF-8"


def process_env(extra: dict | None = None) -> dict:
    """Environment for ACE child processes.

    ACE reads grammar files and input as UTF-8 through the C locale, so it
    fails on non-ASCII TDL (e.g. the ERG) unless a UTF-8 locale is active.
    """
    env = dict(os.environ)
    current = env.get("LC_ALL") or env.get("LC_CTYPE") or env.get("LANG") or ""
    if "utf-8" not in current.lower() and "utf8" not in current.lower():
        env["LC_ALL"] = _utf8_locale()
    # In LUI mode ACE keeps a readline history in $HOME/.ace_history; give
    # it a private HOME so IGDE's traffic doesn't pollute the user's history.
    ace_home = settings.IGDE_HOME / "ace-home"
    ace_home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(ace_home)
    if extra:
        env.update(extra)
    return env


def preferred_encoding() -> str:
    return locale.getpreferredencoding(False) or "utf-8"
