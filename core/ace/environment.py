"""Locating and validating the local ACE installation.

ACE is found, in order of precedence, from:

1. the ACE_ROOT configured in IGDE's settings,
2. the ``$ACE_ROOT`` environment variable,
3. ``ace`` on ``$PATH``,
4. a Homebrew install (``brew install delph-in/delphin/ace``), which is
   often missing from the PATH of servers not started from a login shell.

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
    source: str | None  # "settings" | "env" | "path" | "homebrew" | None
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
            # keep symlinks: Homebrew's bin/ace survives `brew upgrade`,
            # the Cellar path it points to doesn't
            return Path(os.path.abspath(cand))
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


def homebrew_prefixes() -> list[Path]:
    prefixes = [os.environ.get("HOMEBREW_PREFIX"), "/opt/homebrew", "/usr/local", "/home/linuxbrew/.linuxbrew"]
    prefixes.append(str(Path.home() / ".linuxbrew"))
    out = []
    for p in prefixes:
        if p and Path(p) not in out:
            out.append(Path(p))
    return out


def _version_key(path: Path):
    # opt/ace@0.9.33 -> (0, 9, 33); the unversioned formula sorts first
    m = re.search(r"ace@([\d.]+)", str(path))
    return (1, *(-int(x) for x in m.group(1).split("."))) if m else (0,)


def homebrew_executables() -> list[Path]:
    """ACE binaries installed by Homebrew, newest formula first."""
    found, seen = [], set()
    for prefix in homebrew_prefixes():
        cands = [prefix / "bin" / "ace", prefix / "opt" / "ace" / "bin" / "ace"]
        cands += sorted((prefix / "opt").glob("ace@*/bin/ace"), key=_version_key)
        for c in cands:
            if c.is_file() and os.access(c, os.X_OK) and c.resolve() not in seen:
                seen.add(c.resolve())
                found.append(c)
    return found


def detect() -> list[dict]:
    """Every ACE IGDE can find on this machine (for the settings page)."""
    seen, out = set(), []
    cands = []
    if os.environ.get("ACE_ROOT"):
        cands.append(("env", os.environ["ACE_ROOT"]))
    if shutil.which("ace"):
        cands.append(("path", shutil.which("ace")))
    cands += [("homebrew", str(p)) for p in homebrew_executables()]
    for source, root in cands:
        exe = find_executable(root)
        if exe is None or exe.resolve() in seen:
            continue
        seen.add(exe.resolve())
        try:
            version = ace_version(exe)
        except Exception:  # noqa: BLE001
            continue
        out.append({"source": source, "path": str(exe), "version": version})
    return out


def check(ace_root: str | None) -> AceStatus:
    """Resolve and validate ACE given the configured ACE_ROOT (may be empty)."""
    if ace_root:
        source, root = "settings", ace_root
    elif os.environ.get("ACE_ROOT"):
        source, root = "env", os.environ["ACE_ROOT"]
    elif shutil.which("ace"):
        source, root = "path", shutil.which("ace")
    elif homebrew_executables():
        source, root = "homebrew", str(homebrew_executables()[0])
    else:
        return AceStatus(
            False, None, None, None, None,
            "ACE not found: install it (e.g. brew install delph-in/delphin/ace) "
            "or set ACE_ROOT to the directory containing the ace binary.",
        )

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
