"""JSON API for the IGDE React app (all routes under /api/)."""

from __future__ import annotations

import functools
import json
import logging
import os
import re
from pathlib import Path

from delphin.codecs import simplemrs
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from . import fs
from .ace import environment, results
from .ace.lui_session import LuiError
from .ace.manager import AceUnavailable, manager
from .models import AceConfig, Grammar

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, message, status=400, **extra):
        super().__init__(message)
        self.status = status
        self.extra = extra


def api(*methods):
    """JSON in/out, uniform error handling."""

    def deco(fn):
        @require_http_methods(list(methods))
        @functools.wraps(fn)
        def wrapper(request, *args, **kwargs):
            try:
                if request.body and request.content_type == "application/json":
                    try:
                        request.json = json.loads(request.body)
                    except json.JSONDecodeError as e:
                        raise ApiError(f"Invalid JSON: {e}") from e
                else:
                    request.json = {}
                out = fn(request, *args, **kwargs)
                if isinstance(out, HttpResponse):
                    return out
                return JsonResponse(out, safe=False)
            except ApiError as e:
                return JsonResponse({"error": str(e), **e.extra}, status=e.status)
            except fs.FsError as e:
                return JsonResponse({"error": str(e)}, status=e.status)
            except AceUnavailable as e:
                return JsonResponse({"error": str(e), "ace": True}, status=503)
            except LuiError as e:
                return JsonResponse({"error": str(e), "ace": True}, status=502)
            except Grammar.DoesNotExist:
                return JsonResponse({"error": "No such grammar."}, status=404)

        return wrapper

    return deco


def _body(request, key, required=True, default=None):
    value = request.json.get(key, default)
    if required and value in (None, ""):
        raise ApiError(f"Missing '{key}'.")
    return value


def _positive_int(value, name, lo=1, hi=10**6):
    try:
        v = int(value)
    except (TypeError, ValueError) as e:
        raise ApiError(f"'{name}' must be an integer.") from e
    if not lo <= v <= hi:
        raise ApiError(f"'{name}' must be between {lo} and {hi}.")
    return v


# ---------------------------------------------------------------------------
# Status & settings


def _grammar_dict(g: Grammar):
    if g.compile_status == Grammar.COMPILE_RUNNING and not manager.compiling(g.id):
        # the server was restarted while compiling
        g.compile_status = Grammar.COMPILE_FAILED
        g.compile_log += "\n(interrupted: IGDE was restarted during compilation)\n"
        g.save(update_fields=["compile_status", "compile_log"])
    return g.to_dict()


@ensure_csrf_cookie
@api("GET")
def status(request):
    cfg = AceConfig.load()
    return {
        "ace": manager.status(cfg).to_dict(),
        "settings": cfg.to_dict(),
        "activeGrammar": _grammar_dict(cfg.active_grammar) if cfg.active_grammar else None,
        "grammars": [_grammar_dict(g) for g in Grammar.objects.all()],
        "processes": manager.processes(),
        "igdeHome": str(settings.IGDE_HOME),
        "envAceRoot": os.environ.get("ACE_ROOT"),
    }


SETTING_FIELDS = {
    "aceRoot": ("ace_root", str),
    "maxResults": ("max_results", int),
    "timeoutSeconds": ("timeout_seconds", int),
    "maxChartMegabytes": ("max_chart_megabytes", int),
    "maxUnpackMegabytes": ("max_unpack_megabytes", int),
    "grammarImageDir": ("grammar_image_dir", str),
}
SETTING_LIMITS = {
    "max_results": (1, 10000),
    "timeout_seconds": (1, 86400),
    "max_chart_megabytes": (10, 1_000_000),
    "max_unpack_megabytes": (10, 1_000_000),
}


@api("GET", "PUT")
def settings_view(request):
    cfg = AceConfig.load()
    if request.method == "PUT":
        for key, (attr, typ) in SETTING_FIELDS.items():
            if key not in request.json:
                continue
            value = request.json[key]
            if typ is int:
                value = _positive_int(value, key, *SETTING_LIMITS[attr])
            else:
                value = (value or "").strip()
                if value and not Path(value).expanduser().is_absolute():
                    raise ApiError(f"'{key}' must be an absolute path.")
            setattr(cfg, attr, value)
        if cfg.ace_root:
            st = environment.check(cfg.ace_root)
            if not st.ok and not request.json.get("force"):
                raise ApiError(st.error, ace=st.to_dict())
        cfg.save()
        manager.settings_changed()
    return {"settings": cfg.to_dict(), "ace": manager.status(cfg).to_dict()}


@api("POST")
def test_ace(request):
    """Validate an ACE_ROOT without saving it."""
    return environment.check((request.json.get("aceRoot") or "").strip()).to_dict()


# ---------------------------------------------------------------------------
# Filesystem


@api("GET")
def fs_roots(request):
    return {"roots": fs.roots()}


@api("GET")
def fs_list(request):
    return fs.list_dir(request.GET.get("path"), request.GET.get("hidden") == "1")


@api("GET", "PUT")
def fs_file(request):
    if request.method == "GET":
        return fs.read_text(request.GET.get("path", ""))
    content = _body(request, "content", required=False, default=None)
    if not isinstance(content, str):
        raise ApiError("'content' must be a string.")
    return fs.write_text(_body(request, "path"), content, request.json.get("expectedMtime"))


@api("GET")
def fs_detect_grammar(request):
    return fs.find_grammar_config(request.GET.get("path", ""))


# ---------------------------------------------------------------------------
# Grammars


def _slug(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "grammar"


@api("GET", "POST")
def grammars(request):
    if request.method == "GET":
        return {"grammars": [_grammar_dict(g) for g in Grammar.objects.all()]}
    cfg = AceConfig.load()
    config_path = (request.json.get("configPath") or "").strip()
    image_path = (request.json.get("imagePath") or "").strip()
    name = (request.json.get("name") or "").strip()
    if config_path:
        info = fs.find_grammar_config(config_path)
        if info["kind"] != "source":
            raise ApiError(f"{config_path} is not an ACE config file.")
        config_path = info["configPath"]
        name = name or info["name"]
        if not image_path:
            image_path = str(cfg.image_dir() / f"{_slug(name)}.dat")
            n = 2
            while Grammar.objects.filter(image_path=image_path).exists():
                image_path = str(cfg.image_dir() / f"{_slug(name)}-{n}.dat")
                n += 1
    elif image_path:
        p = fs.resolve(image_path)
        if not p.is_file():
            raise ApiError(f"{p} does not exist.", 404)
        image_path = str(p)
        name = name or p.stem
    else:
        raise ApiError("Provide a config.tdl (configPath) or a compiled grammar image (imagePath).")
    if not Path(image_path).is_absolute():
        raise ApiError("'imagePath' must be an absolute path.")
    g = Grammar.objects.create(name=name, config_path=config_path, image_path=image_path)
    if cfg.active_grammar_id is None:
        cfg.active_grammar = g
        cfg.save(update_fields=["active_grammar"])
    if request.json.get("compile") and g.is_source:
        try:
            manager.compile(g)
        except AceUnavailable as e:
            return {"grammar": _grammar_dict(g), "compileError": str(e)}
    return {"grammar": _grammar_dict(g)}


@api("GET", "PATCH", "DELETE")
def grammar_detail(request, gid):
    g = Grammar.objects.get(pk=gid)
    if request.method == "DELETE":
        manager.stop_grammar(g.id)
        g.delete()  # only forgets it; never touches files
        return {"deleted": gid}
    if request.method == "PATCH":
        if "name" in request.json:
            g.name = (request.json["name"] or "").strip() or g.name
        if "imagePath" in request.json:
            p = (request.json["imagePath"] or "").strip()
            if not p or not Path(p).is_absolute():
                raise ApiError("'imagePath' must be an absolute path.")
            manager.stop_grammar(g.id)
            g.image_path = p
        g.save()
    data = _grammar_dict(g)
    data["compileLog"] = g.compile_log
    return {"grammar": data}


@api("POST")
def grammar_activate(request, gid):
    g = Grammar.objects.get(pk=gid)
    cfg = AceConfig.load()
    cfg.active_grammar = g
    cfg.save(update_fields=["active_grammar"])
    return {"activeGrammar": _grammar_dict(g)}


@api("POST")
def grammar_compile(request, gid):
    g = Grammar.objects.get(pk=gid)
    manager.compile(g)
    g.refresh_from_db()
    return {"grammar": _grammar_dict(g)}


@api("GET")
def grammar_files(request, gid):
    g = Grammar.objects.get(pk=gid)
    root = g.root_dir
    if not root.is_dir():
        raise ApiError(f"{root} does not exist.", 404)
    return {"root": str(root), "files": fs.grammar_tree(root)}


# ---------------------------------------------------------------------------
# Processing


def _grammar_for(request) -> Grammar:
    gid = request.json.get("grammar") or request.GET.get("grammar")
    if gid:
        return Grammar.objects.get(pk=int(gid))
    cfg = AceConfig.load()
    if not cfg.active_grammar:
        raise ApiError("No grammar selected. Add one in the Grammars tab.", 409)
    return cfg.active_grammar


def _n(request):
    n = request.json.get("n")
    return _positive_int(n, "n", 1, 10000) if n not in (None, "") else None


@api("POST")
def parse(request):
    sentence = str(_body(request, "sentence")).replace("\n", " ").strip()
    if not sentence:
        raise ApiError("Missing 'sentence'.")
    g = _grammar_for(request)
    response = manager.parse(g, sentence, _n(request))
    return {"grammar": g.id, **results.parse_response(response)}


@api("POST")
def generate(request):
    mrs_text = str(_body(request, "mrs"))
    try:
        simplemrs.decode(mrs_text)  # validate
    except Exception as e:  # noqa: BLE001
        raise ApiError(f"Could not read the MRS: {e}") from e
    g = _grammar_for(request)
    # Send the MRS as written (on one line): re-encoding it with PyDelphin
    # would normalize predicates, e.g. "_dog_n_rel" to _dog_n, which ACE
    # doesn't recognize for grammars that use string predicates.
    one_line = re.sub(r"\s*\n\s*", " ", mrs_text.strip())
    response = manager.generate(g, one_line, _n(request))
    return {"grammar": g.id, **results.generate_response(response)}


@api("GET")
def processes(request):
    return {"processes": manager.processes()}


@api("POST")
def processes_stop(request):
    key = request.json.get("key")
    if key:
        manager.stop(key)
    else:
        manager.stop_all()
    return {"processes": manager.processes()}


# ---------------------------------------------------------------------------
# TFS browsing (ACE LUI mode)


def _lui(request, require_session=True):
    g = _grammar_for(request)
    if require_session:
        m = manager.lui_existing(g.id)
        session = request.json.get("session")
        if m is None or (session is not None and session != m.obj.id):
            raise ApiError("The TFS session has been restarted; parse the sentence again.", 409, stale=True)
    else:
        m = manager.lui(g)
    m.requests += 1
    return g, m


def _definition_file(g, definition):
    """ACE reports TDL locations relative to the directory it was compiled in."""
    if not definition:
        return definition
    f = Path(definition["file"])
    candidates = [f] if f.is_absolute() else []
    if g.config_path:
        candidates.append(Path(g.config_path).parent / f)
    candidates.append(g.root_dir / f)
    for c in candidates:
        c = Path(os.path.normpath(c))
        if c.is_file():
            definition["path"] = str(c)
            break
    return definition


@api("POST")
def tfs_parse(request):
    sentence = str(_body(request, "sentence")).replace("\n", " ").strip()
    g, m = _lui(request, require_session=False)
    cfg = AceConfig.load()
    with m.lock:
        out = m.obj.parse(sentence, timeout=cfg.timeout_seconds + 60)
    for t in out["trees"]:
        t["signature"] = _tree_signature(t)
    return {"grammar": g.id, "session": m.obj.id, **out}


def _tree_signature(t):
    out = [t["entity"]]
    for c in t["children"]:
        out.extend(_tree_signature(c))
    return out


@api("POST")
def tfs_node(request):
    g, m = _lui(request)
    ident = _positive_int(_body(request, "id"), "id")
    what = request.json.get("what", "avm")
    with m.lock:
        data = m.obj.node_mrs(ident) if what == "mrs" else m.obj.node_avm(ident)
    return {"session": m.obj.id, **data}


@api("POST")
def tfs_lookup(request):
    kind = _body(request, "kind")
    if kind not in ("type", "lex", "rule", "instance"):
        raise ApiError("'kind' must be one of type, lex, rule, instance.")
    g, m = _lui(request, require_session=False)
    with m.lock:
        data = m.obj.lookup(kind, str(_body(request, "name")))
    _definition_file(g, data.get("definition"))
    return {"session": m.obj.id, **data}


@api("POST")
def tfs_hierarchy(request):
    g, m = _lui(request, require_session=False)
    with m.lock:
        data = m.obj.hierarchy(str(_body(request, "type")))
    return {"session": m.obj.id, **data}


@api("POST")
def tfs_unify(request):
    g, m = _lui(request)
    left, right = _body(request, "left"), _body(request, "right")
    try:
        args = (int(left["id"]), list(left.get("path", [])), int(right["id"]), list(right.get("path", [])))
    except (TypeError, KeyError, ValueError) as e:
        raise ApiError("'left' and 'right' must be {id, path}.") from e
    with m.lock:
        data = m.obj.unify(*args)
    return {"session": m.obj.id, **data}


# ---------------------------------------------------------------------------
# The React app


@ensure_csrf_cookie
def spa(request, path=""):
    index = settings.FRONTEND_DIST / "index.html"
    if not index.is_file():
        return HttpResponse(
            "<h1>IGDE</h1><p>The frontend has not been built. Run <code>npm install && npm run build</code> "
            "in <code>frontend/</code>, or use the Vite dev server (<code>npm run dev</code>).</p>",
            status=503,
        )
    if path:
        # top-level static files of the build (favicon.svg, ...)
        root = settings.FRONTEND_DIST.resolve()
        p = (root / path).resolve()
        if p.parent == root and p.is_file():
            return FileResponse(open(p, "rb"))
    return FileResponse(open(index, "rb"), content_type="text/html")


def assets(request, path):
    root = (settings.FRONTEND_DIST / "assets").resolve()
    p = (root / path).resolve()
    if root not in p.parents or not p.is_file():
        raise Http404
    return FileResponse(open(p, "rb"))


def csrf_failure(request, reason=""):
    return JsonResponse({"error": f"CSRF check failed: {reason}. Reload the page."}, status=403)
