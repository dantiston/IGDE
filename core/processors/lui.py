"""Parser for the LUI protocol (as spoken by e.g. ``ace -l``).

A processor in LUI mode (normally used with the ``yzlui`` viewer) writes
messages such as::

    group 1 "n1 iv"
    tree 1 #T[1 "S" nil 8 subj-head #T[2 "N" "n1" 3 n1] ...] "n1 iv"
    avm 4 #D[noun-lex ARGS: #D[list] STEM: <1>= #D[cons ...] ...] "n1"
    hierarchy 1 "ref-ind" [ #H["*top*" [] [ 1] ] ... ]
    text 3 #X[ 0 "name" newline ...] #M["Display AVM" "daglist %d" 0 ...] "title"]

This module turns a buffer of such messages into plain Python structures
(JSON-ready) that the React UI renders.

AVMs become ``{"type": str, "tag": int|None, "features": [[feat, avm], ...]}``
or, for a re-entrancy pointer, ``{"ref": int}``.
"""

from __future__ import annotations

import re

KEYWORDS = {"parameter", "group", "tree", "avm", "hierarchy", "text", "close", "quit", "chart"}


class LuiParseError(ValueError):
    pass


_TAGDEF = re.compile(r"<(-?\d+)>=")
_TAGREF = re.compile(r"<(-?\d+)>")
_ATOM = re.compile(r'[^\s\[\]"]+')


class _Reader:
    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.n = len(text)

    # -- low level ---------------------------------------------------------
    def eof(self):
        return self.i >= self.n

    def skip_ws(self, newlines=True):
        s, n = self.s, self.n
        # \f (form feed) terminates LUI messages
        while self.i < n and s[self.i] in (" \t\r\f\n" if newlines else " \t\r\f"):
            self.i += 1

    def peek(self):
        return self.s[self.i] if self.i < self.n else ""

    def rest_of_line(self):
        j = self.s.find("\n", self.i)
        if j < 0:
            j = self.n
        out = self.s[self.i:j]
        self.i = min(j + 1, self.n)
        return out

    def expect(self, lit):
        self.skip_ws()
        if not self.s.startswith(lit, self.i):
            raise LuiParseError(f"expected {lit!r} at {self.i}: {self.s[self.i:self.i + 40]!r}")
        self.i += len(lit)

    def string(self):
        self.skip_ws()
        if self.peek() != '"':
            raise LuiParseError(f"expected string at {self.i}: {self.s[self.i:self.i + 40]!r}")
        self.i += 1
        out = []
        s, n = self.s, self.n
        while self.i < n:
            c = s[self.i]
            if c == "\\" and self.i + 1 < n:
                out.append(s[self.i + 1])
                self.i += 2
                continue
            if c == '"':
                self.i += 1
                return "".join(out)
            out.append(c)
            self.i += 1
        raise LuiParseError("unterminated string")

    def atom(self):
        self.skip_ws()
        m = _ATOM.match(self.s, self.i)
        if not m:
            raise LuiParseError(f"expected atom at {self.i}: {self.s[self.i:self.i + 40]!r}")
        self.i = m.end()
        return m.group(0)

    def integer(self):
        tok = self.atom()
        try:
            return int(tok)
        except ValueError as e:
            raise LuiParseError(f"expected integer, got {tok!r}") from e

    # -- generic items -------------------------------------------------------
    def item(self):
        """Read one item: a string, atom, tag def/ref, or bracketed group.

        Returns ("str", s) | ("atom", a) | ("def", n) | ("ref", n) |
        ("group", kind, [items]) where kind is "" for a plain [ ... ] or the
        letter of a #X[ ... ] form.
        """
        self.skip_ws()
        c = self.peek()
        if c == '"':
            return ("str", self.string())
        if c == "[":
            self.i += 1
            return ("group", "", self._group_items())
        if c == "#" and self.s.startswith("[", self.i + 2):
            kind = self.s[self.i + 1]
            self.i += 3
            return ("group", kind, self._group_items())
        if c == "<":
            m = _TAGDEF.match(self.s, self.i)
            if m:
                self.i = m.end()
                return ("def", int(m.group(1)))
            m = _TAGREF.match(self.s, self.i)
            if m:
                self.i = m.end()
                return ("ref", int(m.group(1)))
        if c == "]":
            raise LuiParseError(f"unexpected ']' at {self.i}")
        return ("atom", self.atom())

    def _group_items(self):
        items = []
        while True:
            self.skip_ws()
            if self.eof():
                raise LuiParseError("unterminated bracket")
            if self.peek() == "]":
                self.i += 1
                return items
            items.append(self.item())


# ---------------------------------------------------------------------------
# Interpreting items


def _scalar(item):
    if item[0] in ("str", "atom"):
        return item[1]
    raise LuiParseError(f"expected scalar, got {item[0]}")


def _avm_from_items(items, tag=None):
    """Interpret the contents of a #D[ ... ] form."""
    if not items:
        raise LuiParseError("empty #D[]")
    head = items[0]
    if head[0] == "str":
        typ = '"' + head[1] + '"'
    elif head[0] == "atom":
        typ = head[1]
    else:
        raise LuiParseError("AVM without a type")
    features = []
    i = 1
    while i < len(items):
        feat = items[i]
        if feat[0] != "atom" or not feat[1].endswith(":"):
            raise LuiParseError(f"expected feature name, got {feat!r}")
        i += 1
        value_tag = None
        if i < len(items) and items[i][0] == "def":
            value_tag = items[i][1]
            i += 1
        if i >= len(items):
            raise LuiParseError(f"feature {feat[1]} without value")
        val = items[i]
        i += 1
        features.append([feat[1][:-1], _avm_value(val, value_tag)])
    return {"type": typ, "tag": tag, "features": features}


def _avm_value(item, tag=None):
    if item[0] == "ref":
        return {"ref": item[1]}
    if item[0] == "group" and item[1] == "D":
        return _avm_from_items(item[2], tag)
    if item[0] in ("str", "atom"):
        # bare atoms are not emitted by ACE, but be lenient
        return {"type": item[1], "tag": tag, "features": []}
    raise LuiParseError(f"unexpected AVM value {item[0]}")


def parse_avm(text: str):
    """Parse a single ``#D[...]`` (optionally preceded by ``<n>=``)."""
    r = _Reader(text)
    tag = None
    it = r.item()
    if it[0] == "def":
        tag = it[1]
        it = r.item()
    return _avm_value(it, tag)


def _tree_from_items(items):
    # #T[id "label" surface|nil eid entity daughters...]
    if len(items) < 5:
        raise LuiParseError("short #T[]")
    node = {
        "id": int(_scalar(items[0])),
        "label": _scalar(items[1]),
        "eid": int(_scalar(items[3])),
        "entity": _scalar(items[4]),
        "children": [],
    }
    surface = items[2]
    if surface[0] == "str":
        node["form"] = surface[1]
    for d in items[5:]:
        if d[0] == "group" and d[1] == "T":
            node["children"].append(_tree_from_items(d[2]))
    return node


def _hierarchy_from_items(items):
    nodes = []
    for it in items:
        if it[0] != "group" or it[1] != "H":
            continue
        name, parents, children = it[2][0], it[2][1], it[2][2]
        nodes.append(
            {
                "name": _scalar(name),
                "parents": [int(_scalar(p)) for p in parents[2]],
                "children": [int(_scalar(c)) for c in children[2]],
            }
        )
    return nodes


def _text_entries(items):
    """#X[ 0 "a" newline 1 "b" newline ] -> [(0, "a"), (1, "b")] / plain lines."""
    entries = []
    pending_index = None
    for it in items:
        if it[0] == "atom" and it[1] == "newline":
            pending_index = None
            continue
        if it[0] == "atom":
            try:
                pending_index = int(it[1])
            except ValueError:
                pending_index = None
            continue
        if it[0] == "str":
            entries.append({"index": pending_index, "text": it[1]})
            pending_index = None
    return entries


def _failure_from_items(items):
    for it in items:
        if it[0] == "group" and it[1] == "U":
            u = it[2]
            kind = _scalar(u[0])
            path = [_scalar(p) for p in u[2][2]] if len(u) > 2 and u[2][0] == "group" else []
            types = [_scalar(x) for x in u[3:] if x[0] in ("atom", "str") and _scalar(x) != "-1"]
            return {"kind": kind, "path": path, "types": types}
    return None


def parse_messages(text: str) -> list[dict]:
    """Parse a buffer containing complete LUI messages."""
    r = _Reader(text)
    out = []
    while True:
        r.skip_ws()
        if r.eof():
            return out
        start = r.i
        m = _ATOM.match(r.s, r.i)
        word = m.group(0) if m else ""
        if word not in KEYWORDS:
            # Stray output (e.g. a stdout leak or the unbalanced ']' ACE
            # appends to some "text" messages); skip to the next line.
            r.rest_of_line()
            continue
        r.i = m.end()
        if word == "parameter":
            line = r.rest_of_line().strip()
            name, _, value = line.partition(" ")
            out.append({"kind": "parameter", "name": name, "value": value})
        elif word == "group":
            out.append({"kind": "group", "count": r.integer(), "sentence": r.string()})
        elif word == "tree":
            chart = r.integer()
            t = r.item()
            if t[0] != "group" or t[1] != "T":
                raise LuiParseError("tree message without #T[]")
            out.append({"kind": "tree", "chart": chart, "tree": _tree_from_items(t[2]), "title": r.string()})
        elif word == "avm":
            ident = r.integer()
            # ACE can leak buffered stdout in front of the dag; skip to it.
            j = r.s.find("#D[", r.i)
            if j < 0:
                raise LuiParseError("avm message without #D[]")
            leaked = r.s[r.i:j].strip()
            r.i = j
            avm = _avm_value(r.item())
            title = r.string()
            failure = None
            r.skip_ws(newlines=False)
            if r.peek() == "[":
                failure = _failure_from_items(r.item()[2])
            msg = {"kind": "avm", "id": ident, "avm": avm, "title": title, "failure": failure}
            if leaked:
                msg["leaked"] = leaked
            out.append(msg)
        elif word == "hierarchy":
            ident = r.integer()
            name = r.string()
            body = r.item()
            out.append({"kind": "hierarchy", "id": ident, "name": name, "nodes": _hierarchy_from_items(body[2])})
        elif word == "text":
            ident = r.integer()
            entries, menu, title = [], None, None
            r.skip_ws(newlines=False)
            while r.peek() not in ("", "\n"):
                if r.peek() == "]":  # stray closing bracket ACE emits
                    r.i += 1
                else:
                    it = r.item()
                    if it[0] == "group" and it[1] == "X":
                        entries = _text_entries(it[2])
                    elif it[0] == "group" and it[1] == "M":
                        menu = [_scalar(x) for x in it[2] if x[0] in ("str", "atom")]
                    elif it[0] == "str":
                        title = it[1]
                r.skip_ws(newlines=False)
            out.append({"kind": "text", "id": ident, "entries": entries, "menu": menu, "title": title})
        elif word in ("close", "quit"):
            out.append({"kind": word, "id": r.integer()})
        else:  # chart: not used by IGDE
            r.i = start
            out.append({"kind": word, "raw": r.rest_of_line()})
