"""Turn PyDelphin/ACE responses into JSON-friendly structures for the UI."""

from __future__ import annotations

import json
import logging
import re

from delphin import derivation, dmrs, eds
from delphin.codecs import dmrsjson, eds as edscodec, mrsjson, simpledmrs, simplemrs

log = logging.getLogger(__name__)

DERIVATION_FIELDS = ["id", "entity", "score", "start", "end", "form", "type"]


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 - one bad view shouldn't sink the result
        log.debug("conversion failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Labelled ("LKB-style") trees: ("S" ("NP" ("DET" ("the")) ...) ...)

_SEXPR_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')


def parse_labelled_tree(text: str | None):
    """Parse ACE's --report-labels tree into ``{label, children}`` /
    ``{form}`` nodes."""
    if not text:
        return None
    pos = 0
    tokens = []
    while pos < len(text):
        m = _SEXPR_TOKEN.match(text, pos)
        if not m:
            break
        pos = m.end()
        if m.group(1):
            tokens.append("(")
        elif m.group(2):
            tokens.append(")")
        elif m.group(3) is not None:
            tokens.append(("str", re.sub(r"\\(.)", r"\1", m.group(3))))
        elif m.group(4):
            tokens.append(("str", m.group(4)))
    it = iter(tokens)

    def node():
        # just consumed "("
        children = []
        label = None
        for tok in it:
            if tok == "(":
                children.append(node())
            elif tok == ")":
                break
            elif label is None:
                label = tok[1]
            else:
                children.append({"form": tok[1]})
        if not children and label is not None:
            return {"form": label}
        return {"label": label, "children": children}

    for tok in it:
        if tok == "(":
            return node()
    return None


# ---------------------------------------------------------------------------
# Semantics


_EP_PRED = re.compile(r'\[\s*("(?:[^"\\]|\\.)*"|[^\s<\[\]"]+)(?:<[^>]*>)?\s+LBL:')


def raw_predicates(raw: str | None) -> list[str]:
    """Predicates exactly as ACE wrote them, in EP order.

    PyDelphin normalizes predicates (``"_dog_n_rel"`` becomes ``_dog_n``),
    but grammar engineers need to see, and ACE needs to be given back, the
    grammar's own predicate strings."""
    return [m.group(1) for m in _EP_PRED.finditer(raw or "")]


def format_simplemrs(raw: str) -> str:
    """Indent ACE's one-line SimpleMRS without changing any of its tokens."""
    out, depth, in_str, in_rels, seen_ep = [], 0, False, False, False
    i = 0
    while i < len(raw):
        c = raw[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < len(raw):
                out.append(raw[i + 1])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif c == "[":
            if depth == 1 and in_rels:
                if seen_ep:
                    while out and out[-1] == " ":
                        out.pop()
                    out.append("\n" + " " * 10)
                seen_ep = True
            depth += 1
            out.append(c)
        elif c == "]":
            depth -= 1
            out.append(c)
        elif depth == 1 and c == ">":
            in_rels = False
            out.append(c)
        else:
            if depth == 1 and c != " " and (i == 0 or raw[i - 1] == " "):
                word = raw[i:].split(" ", 1)[0]
                if word in ("INDEX:", "RELS:", "HCONS:", "ICONS:"):
                    while out and out[-1] == " ":
                        out.pop()
                    out.append("\n  ")
                    in_rels = word == "RELS:"
            out.append(c)
        i += 1
    return "".join(out).strip()


def semantics(mrs_obj, raw: str | None = None) -> dict:
    """All the views of one MRS the UI offers."""
    out = {
        "simplemrs": format_simplemrs(raw) if raw else simplemrs.encode(mrs_obj, indent=True),
        "mrs": json.loads(mrsjson.encode(mrs_obj)),
        "dmrs": None,
        "simpledmrs": None,
        "eds": None,
    }
    preds = raw_predicates(raw)
    if len(preds) != len(out["mrs"]["relations"]):
        preds = None
    if preds:
        for rel, pred in zip(out["mrs"]["relations"], preds):
            rel["predicate"] = pred
    d = _safe(dmrs.from_mrs, mrs_obj)
    if d is not None:
        out["dmrs"] = _safe(lambda: json.loads(dmrsjson.encode(d)))
        if preds and out["dmrs"] and len(out["dmrs"]["nodes"]) == len(preds):
            # DMRS nodes are created in EP order
            for node, pred in zip(sorted(out["dmrs"]["nodes"], key=lambda n: n["nodeid"]), preds):
                node["predicate"] = pred
        out["simpledmrs"] = _safe(simpledmrs.encode, d, indent=True)
    e = _safe(eds.from_mrs, mrs_obj)
    if e is not None:
        out["eds"] = _safe(edscodec.encode, e, indent=True)
    return out


def derivation_dict(deriv_str: str | None):
    if not deriv_str:
        return None
    d = _safe(derivation.from_string, deriv_str)
    if d is None:
        return None
    return d.to_dict(fields=DERIVATION_FIELDS)


def entity_signature(node) -> list[str]:
    """Pre-order list of entity names; used to match a parse result with the
    corresponding tree in a LUI (TFS browsing) session."""
    if not node:
        return []
    out = [node.get("entity")]
    for d in node.get("daughters", []) or []:
        out.extend(entity_signature(d))
    return out


def _flag(result, name):
    for key, value in result.get("flags", []) or []:
        if key == name:
            return value
    return None


def _messages(response, key):
    return [str(m) for m in (response.get(key) or [])]


def _response_common(response) -> dict:
    return {
        "readings": response.get("readings"),
        "error": response.get("error") or None,
        "notes": _messages(response, "NOTES"),
        "warnings": _messages(response, "WARNINGS"),
        "errors": _messages(response, "ERRORS"),
        "time": response.get("tcpu"),
        "pedges": response.get("pedges"),
        "aedges": response.get("aedges"),
    }


def parse_response(response) -> dict:
    results = []
    for res in response.results():
        deriv = derivation_dict(res.get("derivation"))
        item = {
            "id": res.get("result-id"),
            "score": _flag(res, ":ascore"),
            "probability": _flag(res, ":probability"),
            "derivation": deriv,
            "signature": entity_signature(deriv),
            "tree": parse_labelled_tree(res.get("tree")),
            "mrsString": res.get("mrs"),
        }
        m = _safe(res.mrs)
        raw = res.get("mrs")
        item.update(semantics(m, raw) if m is not None else {"simplemrs": raw})
        results.append(item)
    return {"input": response.get("input"), "results": results, **_response_common(response)}


def generate_response(response) -> dict:
    results = []
    for res in response.results():
        deriv = derivation_dict(res.get("derivation"))
        results.append(
            {
                "id": res.get("result-id"),
                "surface": res.get("surface"),
                "score": _flag(res, ":ascore"),
                "probability": _flag(res, ":probability"),
                "derivation": deriv,
                "tree": parse_labelled_tree(res.get("tree")),
            }
        )
    return {"input": response.get("input"), "results": results, **_response_common(response)}
