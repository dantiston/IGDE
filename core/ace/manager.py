"""Owns every ACE process IGDE starts.

* one PyDelphin ACEParser / ACEGenerator per grammar, kept alive between
  requests (loading even the ERG is fast, but not free);
* one LUI session per grammar for TFS browsing;
* background grammar compilation jobs.

Processes are restarted transparently when ACE's executable, the grammar
image or the processing options change, or when a process dies.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from delphin import ace as delphin_ace
from django.db import close_old_connections
from django.utils import timezone

from . import environment
from .lui_session import LuiError, LuiSession

log = logging.getLogger(__name__)

# Restart LUI sessions periodically: in LUI mode ACE keeps every parse
# chart around so that it can be browsed later.
LUI_MAX_PARSES = 200


class AceUnavailable(RuntimeError):
    pass


@dataclass
class Managed:
    kind: str  # "parser" | "generator" | "lui"
    grammar_id: int
    grammar_name: str
    signature: tuple
    obj: object
    stderr: object = None
    started: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    requests: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def pid(self):
        if self.kind == "lui":
            return self.obj.pid
        return self.obj._p.pid

    def alive(self):
        if self.kind == "lui":
            return self.obj.alive()
        return self.obj._p.poll() is None

    def stderr_tail(self, n=2000):
        if self.stderr is None:
            return ""
        try:
            self.stderr.flush()
            self.stderr.seek(0, os.SEEK_END)
            size = self.stderr.tell()
            self.stderr.seek(max(0, size - n))
            return self.stderr.read().decode("utf-8", "replace")
        except (OSError, ValueError):
            return ""

    def close(self):
        try:
            self.obj.close()
        except Exception as e:  # noqa: BLE001
            log.debug("closing %s: %s", self.kind, e)
        if self.stderr is not None:
            self.stderr.close()

    def to_dict(self):
        return {
            "key": f"{self.kind}:{self.grammar_id}",
            "kind": self.kind,
            "grammarId": self.grammar_id,
            "grammarName": self.grammar_name,
            "pid": self.pid,
            "alive": self.alive(),
            "started": self.started,
            "lastUsed": self.last_used,
            "requests": self.requests,
            **({"session": self.obj.id} if self.kind == "lui" else {}),
        }


class AceManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._procs: dict[tuple[str, int], Managed] = {}
        self._status_cache: tuple | None = None
        self._compiles: dict[int, threading.Thread] = {}

    # -- configuration -----------------------------------------------------
    def config(self):
        from core.models import AceConfig

        return AceConfig.load()

    def status(self, cfg=None):
        cfg = cfg or self.config()
        key = (cfg.ace_root, os.environ.get("ACE_ROOT"), os.environ.get("PATH"))
        cached = self._status_cache
        # Only successful lookups are cached, so that e.g. a fresh
        # `brew install` is picked up without touching the settings.
        if cached and cached[0] == key:
            exe = cached[1].executable
            if Path(exe).exists() and Path(exe).stat().st_mtime == cached[2]:
                return cached[1]
        st = environment.check(cfg.ace_root)
        self._status_cache = (key, st, Path(st.executable).stat().st_mtime) if st.ok else None
        return st

    def executable(self, cfg=None) -> str:
        st = self.status(cfg)
        if not st.ok:
            raise AceUnavailable(st.error)
        return st.executable

    @staticmethod
    def _cmdargs(cfg, n=None):
        return [
            "-n", str(n or cfg.max_results),
            "--timeout", str(cfg.timeout_seconds),
            "--max-chart-megabytes", str(cfg.max_chart_megabytes),
            "--max-unpack-megabytes", str(cfg.max_unpack_megabytes),
        ]

    def settings_changed(self):
        self._status_cache = None
        self.stop_all()

    # -- process pool ------------------------------------------------------
    def _get(self, kind, grammar, n=None) -> Managed:
        cfg = self.config()
        exe = self.executable(cfg)
        image = Path(grammar.image_path)
        if not image.is_file():
            raise AceUnavailable(
                f"Grammar image {image} does not exist"
                + (" - compile the grammar first." if grammar.is_source else ".")
            )
        args = self._cmdargs(cfg, n)
        sig = (exe, str(image), image.stat().st_mtime, tuple(args))
        key = (kind, grammar.id)
        with self._lock:
            m = self._procs.get(key)
            if m and m.signature == sig and m.alive():
                if not (kind == "lui" and m.obj.parses >= LUI_MAX_PARSES):
                    return m
            if m:
                self._procs.pop(key)
                m.close()
            m = self._start(kind, grammar, exe, image, args, sig)
            self._procs[key] = m
            return m

    def _start(self, kind, grammar, exe, image, args, sig) -> Managed:
        env = environment.process_env()
        log.info("starting ACE %s for %s", kind, grammar.name)
        if kind == "lui":
            try:
                obj = LuiSession(exe, image, args, env=env, cwd=str(grammar.root_dir) if grammar.root_dir.is_dir() else None)
            except LuiError as e:
                raise AceUnavailable(f"Could not start ACE: {e}") from e
            return Managed(kind, grammar.id, grammar.name, sig, obj)
        cls = delphin_ace.ACEParser if kind == "parser" else delphin_ace.ACEGenerator
        stderr = tempfile.TemporaryFile()
        try:
            obj = cls(str(image), cmdargs=list(args), executable=exe, env=env, stderr=stderr)
        except Exception as e:
            stderr.close()
            raise AceUnavailable(f"Could not start ACE: {e}") from e
        return Managed(kind, grammar.id, grammar.name, sig, obj, stderr=stderr)

    def _interact(self, kind, grammar, datum, n=None):
        m = self._get(kind, grammar, n)
        with m.lock:
            m.last_used = time.time()
            m.requests += 1
            response = m.obj.interact(datum)
            if not m.alive():
                tail = m.stderr_tail()
                with self._lock:
                    if self._procs.get((kind, grammar.id)) is m:
                        self._procs.pop((kind, grammar.id))
                m.close()
                raise AceUnavailable(f"ACE exited while processing the input.\n{tail}".strip())
            return response

    def parse(self, grammar, sentence, n=None):
        return self._interact("parser", grammar, sentence, n)

    def generate(self, grammar, mrs, n=None):
        return self._interact("generator", grammar, mrs, n)

    def lui(self, grammar) -> Managed:
        return self._get("lui", grammar)

    def lui_existing(self, grammar_id) -> Managed | None:
        with self._lock:
            m = self._procs.get(("lui", grammar_id))
            return m if m and m.alive() else None

    def processes(self):
        with self._lock:
            return [m.to_dict() for m in self._procs.values()]

    def stop(self, key: str):
        kind, _, gid = key.partition(":")
        with self._lock:
            m = self._procs.pop((kind, int(gid)), None)
        if m:
            m.close()
        return m is not None

    def stop_grammar(self, grammar_id):
        with self._lock:
            victims = [k for k in self._procs if k[1] == grammar_id]
            ms = [self._procs.pop(k) for k in victims]
        for m in ms:
            m.close()

    def stop_all(self):
        with self._lock:
            ms = list(self._procs.values())
            self._procs.clear()
        for m in ms:
            m.close()

    # -- compilation -------------------------------------------------------
    def compiling(self, grammar_id) -> bool:
        t = self._compiles.get(grammar_id)
        return bool(t and t.is_alive())

    def compile(self, grammar):
        from core.models import Grammar

        if not grammar.is_source:
            raise AceUnavailable("Only grammars with a config.tdl can be compiled.")
        if self.compiling(grammar.id):
            raise AceUnavailable("This grammar is already being compiled.")
        exe = self.executable()
        cfg_path = Path(grammar.config_path)
        if not cfg_path.is_file():
            raise AceUnavailable(f"Config file {cfg_path} does not exist.")
        grammar.compile_status = Grammar.COMPILE_RUNNING
        grammar.compile_log = ""
        grammar.save(update_fields=["compile_status", "compile_log"])
        t = threading.Thread(target=self._compile_job, args=(grammar.id, exe), daemon=True)
        self._compiles[grammar.id] = t
        t.start()

    def _compile_job(self, grammar_id, exe):
        from core.models import Grammar

        close_old_connections()
        grammar = Grammar.objects.get(pk=grammar_id)
        cfg_path = Path(grammar.config_path)
        out = Path(grammar.image_path)
        tmp = out.with_name(out.name + ".igde-tmp")
        status, logtext = Grammar.COMPILE_FAILED, ""
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            cmd = [exe, "-g", str(cfg_path), "-G", str(tmp)]
            started = time.time()
            proc = subprocess.run(
                cmd,
                cwd=str(cfg_path.parent),
                env=environment.process_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=3600,
            )
            logtext = "$ " + " ".join(cmd) + "\n" + proc.stdout.decode("utf-8", "replace")
            if proc.returncode == 0 and tmp.is_file() and tmp.stat().st_size > 0:
                # Running processes have the old image mmap'd; stop them
                # before swapping the file underneath them.
                self.stop_grammar(grammar_id)
                os.replace(tmp, out)
                status = Grammar.COMPILE_OK
                logtext += f"\nCompiled {out} in {time.time() - started:.1f}s\n"
            else:
                logtext += f"\nCompilation failed (exit status {proc.returncode}).\n"
        except Exception as e:  # noqa: BLE001
            logtext += f"\nCompilation failed: {e}\n"
        finally:
            tmp.unlink(missing_ok=True)
            Grammar.objects.filter(pk=grammar_id).update(
                compile_status=status,
                compile_log=_strip_ansi(logtext),
                compiled_at=timezone.now() if status == Grammar.COMPILE_OK else grammar.compiled_at,
            )
            close_old_connections()


def _strip_ansi(text):
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", text)


manager = AceManager()
