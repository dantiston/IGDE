"""A long-lived ``ace -l`` process that IGDE talks to as if it were LUI.

Plumbing:

* stdin (pipe): sentences to parse and ``:t``/``:l``/``:r``/``:i``/``:H``
  browsing commands, exactly as typed at ACE's interactive LUI prompt;
* the LUI channel (one end of a socketpair passed with ``--lui-fd``): ACE
  writes trees/AVMs/hierarchies there and reads ``browse``/``unify``
  requests from it;
* stdout+stderr (a pty, so ACE line-buffers rather than block-buffers):
  diagnostics, and the replies to our synchronisation sentinels.

ACE never acknowledges a command, so after each one we send a sentinel
that makes ACE print a recognisable "no such type" error on the same
channel's thread: a ``:t`` lookup via stdin (handled by ACE's main loop) or
a ``type ... skeleton`` request via the LUI socket (handled by ACE's LUI
listener thread).  Once the sentinel's reply arrives, everything the
command wrote to the LUI socket is already in the socket buffer.
"""

from __future__ import annotations

import itertools
import os
import pty
import re
import select
import socket
import subprocess
import termios
import threading
import time

from .lui import parse_messages

_CHART_RE = re.compile(r"out-of-date chart (\d+) requested \[(\d+) is current\]")
_session_ids = itertools.count(1)


class LuiError(RuntimeError):
    pass


class LuiSession:
    def __init__(self, executable, grammar_image, cmdargs=(), env=None, cwd=None, startup_timeout=180):
        self.id = next(_session_ids)
        self.lock = threading.RLock()
        self.chart_id = 0
        self.parses = 0
        self.started = time.time()
        self._sync = itertools.count(1)
        self._known_ids: set[int] = set()
        self._out = bytearray()  # pty (stdout/stderr) text since the last command
        self._lui = bytearray()

        parent, child = socket.socketpair()
        master, slave = pty.openpty()
        attrs = termios.tcgetattr(slave)
        attrs[1] &= ~termios.OPOST  # no \n -> \r\n translation
        attrs[3] &= ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        try:
            self.proc = subprocess.Popen(
                [str(executable), "-g", str(grammar_image), "-l", "--lui-fd", str(child.fileno()), *cmdargs],
                stdin=subprocess.PIPE,
                stdout=slave,
                stderr=slave,
                pass_fds=[child.fileno()],
                env=env,
                cwd=cwd,
                start_new_session=True,
            )
        finally:
            child.close()
            os.close(slave)
        self._sock = parent
        self._pty = master
        try:
            self._stdin_sync(startup_timeout)
        except Exception:
            self.close()
            raise

    # -- process lifetime ----------------------------------------------------
    @property
    def pid(self):
        return self.proc.pid

    def alive(self):
        return self.proc.poll() is None

    def close(self):
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except OSError:
            pass
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        for closer in (self._sock.close, lambda: os.close(self._pty)):
            try:
                closer()
            except OSError:
                pass

    # -- I/O -------------------------------------------------------------------
    def _read_available(self, wait):
        r, _, _ = select.select([self._pty, self._sock], [], [], wait)
        got = False
        if self._pty in r:
            try:
                data = os.read(self._pty, 1 << 16)
            except OSError:  # EIO once ACE exits and the pty slave closes
                data = b""
            if data:
                self._out.extend(data.replace(b"\r", b""))
                got = True
        if self._sock in r:
            data = self._sock.recv(1 << 20)
            if data:
                self._lui.extend(data)
                got = True
        return got

    def _drain_lui(self):
        while True:
            try:
                data = self._sock.recv(1 << 20, socket.MSG_DONTWAIT)
            except BlockingIOError:
                return
            if not data:
                return
            self._lui.extend(data)

    def _pump_until(self, needle: bytes, timeout):
        deadline = time.monotonic() + timeout
        while needle not in self._out:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LuiError(f"ACE did not respond within {timeout:.0f}s")
            if not self._read_available(min(remaining, 0.5)) and self.proc.poll() is not None:
                # drain whatever is left, then report
                while self._read_available(0):
                    pass
                if needle in self._out:
                    break
                raise LuiError(f"ACE exited (status {self.proc.returncode}): {self.output_tail()}")
        self._drain_lui()

    def output_tail(self, n=2000):
        return self._out.decode("utf-8", "replace")[-n:].strip()

    def _begin(self):
        if not self.alive():
            raise LuiError(f"ACE exited (status {self.proc.returncode}): {self.output_tail()}")
        self._out.clear()
        self._lui.clear()

    def _finish(self, sentinel: bytes):
        out = bytes(self._out)
        cut = out.find(sentinel)
        stdout = out[:cut] if cut >= 0 else out
        # drop the line the sentinel is on
        stdout = stdout[: stdout.rfind(b"\n") + 1] if b"\n" in stdout else b""
        messages = parse_messages(self._lui.decode("utf-8", "replace"))
        for m in messages:
            self._note(m)
        return messages, stdout.decode("utf-8", "replace")

    def _note(self, m):
        kind = m["kind"]
        if kind == "tree":
            self.chart_id = max(self.chart_id, m["chart"])

            def walk(t):
                self._known_ids.add(t["id"])
                for c in t["children"]:
                    walk(c)

            walk(m["tree"])
        elif kind == "avm":
            self._known_ids.add(m["id"])

    def _stdin_sync(self, timeout):
        token = f"__igde_sync_{next(self._sync)}__"
        self.proc.stdin.write(f":t {token}\n".encode())
        self.proc.stdin.flush()
        sentinel = f"no such type `{token}'".encode()
        self._pump_until(sentinel, timeout)
        return sentinel

    def stdin_command(self, line: str, timeout=120):
        """Send a line on ACE's stdin (a sentence or a :command)."""
        line = line.replace("\n", " ").strip()
        with self.lock:
            self._begin()
            self.proc.stdin.write((line + "\n").encode())
            self.proc.stdin.flush()
            sentinel = self._stdin_sync(timeout)
            return self._finish(sentinel)

    def lui_command(self, line: str, timeout=60):
        """Send a request over the LUI channel (browse/unify/daglist)."""
        with self.lock:
            self._begin()
            token = f"__igde_sync_{next(self._sync)}__"
            self._sock.sendall(f"{line}\ntype {token} skeleton\n".encode())
            sentinel = f"no such type `{token}'".encode()
            self._pump_until(sentinel, timeout)
            return self._finish(sentinel)

    # -- high level operations -------------------------------------------------
    def knows(self, ident: int) -> bool:
        # ACE dereferences unknown object ids without checking, so only ever
        # send it ids it handed out.
        return ident in self._known_ids

    def parse(self, sentence: str, timeout=120):
        msgs, out = self.stdin_command(sentence, timeout)
        self.parses += 1
        trees = [m for m in msgs if m["kind"] == "tree"]
        group = next((m for m in msgs if m["kind"] == "group"), None)
        return {
            "sentence": group["sentence"] if group else sentence,
            "count": group["count"] if group else len(trees),
            "chart": trees[0]["chart"] if trees else None,
            "trees": [t["tree"] for t in trees],
            "output": out.strip(),
        }

    def _browse(self, ident: int, what: str):
        if not self.knows(ident):
            raise LuiError(f"unknown object #{ident} (stale TFS session?)")
        for _ in range(2):
            msgs, out = self.lui_command(f"browse {self.chart_id} {ident} {what}")
            m = _CHART_RE.search(out)
            if m and not [x for x in msgs if x["kind"] == "avm"]:
                self.chart_id = int(m.group(2))
                continue
            return msgs, out
        return msgs, out

    def node_avm(self, ident: int):
        msgs, out = self._browse(ident, "avm")
        return _single_avm(msgs, out)

    def node_mrs(self, ident: int):
        msgs, out = self._browse(ident, "mrs simple")
        return _single_avm(msgs, out)

    def lookup(self, kind: str, name: str):
        """Look up a type/lexical entry/rule/instance by (partial) name."""
        cmd = {"type": "t", "lex": "l", "rule": "r", "instance": "i"}[kind]
        name = name.strip()
        if not name or any(c.isspace() for c in name):
            raise LuiError("names cannot be empty or contain whitespace")
        msgs, out = self.stdin_command(f":{cmd} {name}")
        avms = [m for m in msgs if m["kind"] == "avm"]
        texts = [m for m in msgs if m["kind"] == "text"]
        definition = None
        m = re.search(r"^(\S+) -- defined at (.+):(\d+)\n(.*)", out, re.S | re.M)
        if m:
            definition = {"name": m.group(1), "file": m.group(2), "line": int(m.group(3)), "tdl": m.group(4).strip()}
        if avms:
            a = avms[0]
            return {"avm": a["avm"], "id": a["id"], "title": a["title"], "definition": definition}
        if texts:
            matches = [e["text"] for e in texts[-1]["entries"] if e["index"] is not None and not e["text"].startswith("... and ")]
            more = next((e["text"] for e in texts[-1]["entries"] if e["text"].startswith("... and ")), None)
            return {"matches": matches, "more": more}
        return {"matches": [], "message": out.strip()}

    def hierarchy(self, type_name: str):
        type_name = type_name.strip()
        if not type_name or any(c.isspace() for c in type_name):
            raise LuiError("type names cannot be empty or contain whitespace")
        msgs, out = self.stdin_command(f":H {type_name}")
        h = next((m for m in msgs if m["kind"] == "hierarchy"), None)
        if h is None:
            raise LuiError(out.strip() or f"no such type {type_name}")
        return {"name": h["name"], "nodes": h["nodes"]}

    def unify(self, left_id: int, left_path: list[str], right_id: int, right_path: list[str]):
        for ident in (left_id, right_id):
            if not self.knows(ident):
                raise LuiError(f"unknown object #{ident} (stale TFS session?)")
        for f in itertools.chain(left_path, right_path):
            if not re.fullmatch(r"[^\s\[\]]+", f):
                raise LuiError(f"bad feature name {f!r}")
        cmd = f"unify {left_id} [{' '.join(left_path)}] {right_id} [{' '.join(right_path)}]"
        msgs, out = self.lui_command(cmd)
        avm = next((m for m in msgs if m["kind"] == "avm"), None)
        if avm is not None:
            return {
                "ok": avm["failure"] is None,
                "avm": avm["avm"],
                "id": avm["id"],
                "title": avm["title"],
                "failure": avm["failure"],
            }
        text = next((m for m in msgs if m["kind"] == "text"), None)
        if text is not None:
            self.chart_id += 1  # lui_text() advances ACE's chart counter
            return {"ok": False, "message": " ".join(e["text"] for e in text["entries"])}
        raise LuiError(out.strip() or "unification produced no result")


def _single_avm(msgs, out):
    avm = next((m for m in msgs if m["kind"] == "avm"), None)
    if avm is None:
        raise LuiError(out.strip() or "ACE returned no AVM")
    return {"avm": avm["avm"], "id": avm["id"], "title": avm["title"]}
