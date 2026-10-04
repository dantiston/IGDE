"""The ACE backend: http://sweaglesw.org/linguistics/ace/

ACE is found, in order of precedence, from:

1. the location configured for the processor in IGDE (an ACE_ROOT),
2. the ``$ACE_ROOT`` environment variable,
3. ``ace`` on ``$PATH``,
4. a Homebrew install (``brew install delph-in/delphin/ace``), which is
   often missing from the PATH of servers not started from a login shell.

An ACE_ROOT may be the ``ace`` binary itself or a directory containing it
(an unpacked ACE release such as ``ace-0.9.34/``, or a prefix with
``bin/ace``).

Grammars are described by an ACE ``config.tdl`` (by DELPH-IN convention
``<grammar>/ace/config.tdl``) and compiled to an image with ``ace -G``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from delphin import ace as delphin_ace

from .base import COMPILE, GENERATE, PARSE, TFS, Backend, GrammarInfo, Install, Option, ProcessorStatus, utf8_env
from .lui_session import LuiError, LuiSession

VERSION_RE = re.compile(r"ACE version ([\d.]+)")
_GRAMMAR_TOP_RE = re.compile(r"^\s*grammar-top\s*:=\s*\"?([^\".\s]+(?:\.[^\".\s]+)*)\"?\s*\.", re.M)


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


def process_env() -> dict:
    # In LUI mode ACE keeps a readline history in $HOME/.ace_history; give
    # it a private HOME so IGDE's traffic doesn't pollute the user's history.
    return utf8_env(home="ace-home")


def _config_in(d: Path) -> Path | None:
    for cand in (d / "ace" / "config.tdl", d / "config.tdl"):
        if cand.is_file():
            return cand
    return None


class AceLuiSession(LuiSession):
    """``ace -l``: ACE's LUI mode.

    Sentinels are lookups of a type that doesn't exist, which ACE answers
    with "no such type": a ``:t`` command on stdin (handled by ACE's main
    loop) or a ``type ... skeleton`` request on the LUI socket (handled by
    ACE's LUI listener thread).
    """

    label = "ACE"
    stale_chart_re = re.compile(r"out-of-date chart (\d+) requested \[(\d+) is current\]")

    def command(self, executable, grammar_image, lui_fd, cmdargs):
        return [str(executable), "-g", str(grammar_image), "-l", "--lui-fd", str(lui_fd), *cmdargs]

    def stdin_sentinel(self, token):
        return f":t {token}", f"no such type `{token}'".encode()

    def lui_sentinel(self, token):
        return f"type {token} skeleton", f"no such type `{token}'".encode()

    LOOKUP = {"type": ":t", "lex": ":l", "rule": ":r", "instance": ":i"}

    def lookup_command(self, kind, name):
        return f"{self.LOOKUP[kind]} {name}"

    def hierarchy_command(self, type_name):
        return f":H {type_name}"

    def parse_definition(self, output):
        m = re.search(r"^(\S+) -- defined at (.+):(\d+)\n(.*)", output, re.S | re.M)
        if m:
            return {"name": m.group(1), "file": m.group(2), "line": int(m.group(3)), "tdl": m.group(4).strip()}
        return None


class AceBackend(Backend):
    key = "ace"
    label = "ACE"
    description = "The Answer Constraint Engine: a fast DELPH-IN parser and generator."
    homepage = "https://sweaglesw.org/linguistics/ace/"
    capabilities = frozenset({PARSE, GENERATE, TFS, COMPILE})
    options = (
        Option("maxChartMegabytes", "Chart memory (MB)", 1200, "ACE --max-chart-megabytes", min=10, max=1_000_000),
        Option("maxUnpackMegabytes", "Unpacking memory (MB)", 1500, "ACE --max-unpack-megabytes", min=10, max=1_000_000),
    )
    location_label = "ACE_ROOT"
    location_help = (
        "The directory containing the ace binary (an unpacked ace-0.9.34 release or a Homebrew prefix) "
        "or the binary itself. Leave it empty to use $ACE_ROOT, ace on $PATH, or a Homebrew install."
    )
    sources = {
        "settings": "ACE_ROOT",
        "env": "the $ACE_ROOT environment variable",
        "path": "$PATH",
        "homebrew": "Homebrew",
    }
    install_command = "brew install delph-in/delphin/ace"
    env_vars = ("ACE_ROOT",)
    config_label = "ACE config.tdl"
    image_suffix = ".dat"
    # ACE images have no documented magic number; recognise them by name
    image_suffixes = frozenset({".dat", ".grm", ".ace"})

    # -- installation ------------------------------------------------------
    def check(self, location):
        if location:
            source, root = "settings", location
        elif os.environ.get("ACE_ROOT"):
            source, root = "env", os.environ["ACE_ROOT"]
        elif shutil.which("ace"):
            source, root = "path", shutil.which("ace")
        elif homebrew_executables():
            source, root = "homebrew", str(homebrew_executables()[0])
        else:
            return ProcessorStatus(
                False, None, None, None, None,
                f"ACE not found: install it (e.g. {self.install_command}) "
                "or set ACE_ROOT to the directory containing the ace binary.",
            )

        exe = find_executable(root)
        if exe is None:
            return ProcessorStatus(
                False, source, root, None, None,
                f"No executable 'ace' found at {root} (looked for {root}, {root}/ace and {root}/bin/ace).",
            )
        try:
            version = ace_version(exe)
        except Exception as e:  # noqa: BLE001 - surface any failure to the user
            return ProcessorStatus(False, source, root, str(exe), None, str(e))
        return ProcessorStatus(True, source, root, str(exe), version, None)

    def detect(self):
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
            out.append(Install(source, str(exe), version))
        return out

    def env(self):
        return process_env()

    # -- grammars ----------------------------------------------------------
    def classify(self, p, is_dir):
        if is_dir:
            return "grammar-dir" if _config_in(p) else None
        if p.name == "config.tdl" or (p.suffix == ".tdl" and p.parent.name == "ace" and "config" in p.stem):
            return "config"
        if p.suffix in self.image_suffixes:
            return "image"
        return None

    def describe_grammar(self, p):
        if p.is_dir():
            cfg = _config_in(p)
            if cfg:
                return self._describe_config(cfg)
            images = sorted(x for x in p.iterdir() if x.suffix in self.image_suffixes and x.is_file())
            if images:
                return GrammarInfo("image", images[0].stem, image_path=str(images[0]))
            return None
        if p.suffix == ".tdl":
            return self._describe_config(p)
        if p.suffix in self.image_suffixes:
            return GrammarInfo("image", p.stem, image_path=str(p))
        return None

    def _describe_config(self, cfg: Path) -> GrammarInfo:
        text = cfg.read_text(encoding="utf-8", errors="replace")
        if "grammar-top" not in text:
            raise ValueError(f"{cfg} does not look like an ACE config file (no grammar-top setting).")
        m = _GRAMMAR_TOP_RE.search(text)
        return GrammarInfo(
            "source", self.grammar_root(cfg).name, config_path=str(cfg), extra={"grammarTop": m.group(1) if m else None}
        )

    def grammar_root(self, config_path):
        # DELPH-IN convention: <grammar>/ace/config.tdl
        return config_path.parent.parent if config_path.parent.name == "ace" else config_path.parent

    def image_grammar_root(self, image_path):
        # a precompiled image is often kept beside its grammar's directory
        # (e.g. erg.dat next to erg/)
        beside = image_path.parent / image_path.stem
        return beside if _config_in(beside) else image_path.parent

    def compile_command(self, executable, config, image):
        return [str(executable), "-g", str(config), "-G", str(image)]

    # -- processing --------------------------------------------------------
    def processing_args(self, options, max_results, timeout):
        o = self.resolved_options(options)
        return [
            "-n", str(max_results),
            "--timeout", str(timeout),
            "--max-chart-megabytes", str(o["maxChartMegabytes"]),
            "--max-unpack-megabytes", str(o["maxUnpackMegabytes"]),
        ]

    def parser(self, executable, image, args, env, stderr):
        return delphin_ace.ACEParser(str(image), cmdargs=list(args), executable=str(executable), env=env, stderr=stderr)

    def generator(self, executable, image, args, env, stderr):
        return delphin_ace.ACEGenerator(str(image), cmdargs=list(args), executable=str(executable), env=env, stderr=stderr)

    def lui_session(self, executable, image, args, env, cwd):
        return AceLuiSession(executable, image, args, env=env, cwd=cwd)


__all__ = ["AceBackend", "AceLuiSession", "LuiError", "find_executable", "homebrew_prefixes"]
