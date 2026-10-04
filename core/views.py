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

from delphin import tsdb as delphin_tsdb

from . import fs, profiles
from .models import AppSettings, Grammar, Processor, Profile
from .processors import registry, results
from .processors.base import ProcessorUnavailable
from .processors.lui_session import LuiError
from .processors.manager import manager

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
            except ProcessorUnavailable as e:
                return JsonResponse({"error": str(e), "processor": True}, status=503)
            except LuiError as e:
                return JsonResponse({"error": str(e), "processor": True}, status=502)
            except Grammar.DoesNotExist:
                return JsonResponse({"error": "No such grammar."}, status=404)
            except Processor.DoesNotExist:
                return JsonResponse({"error": "No such processor."}, status=404)
            except Profile.DoesNotExist:
                return JsonResponse({"error": "No such test suite or profile."}, status=404)
            except profiles.ProfileError as e:
                return JsonResponse({"error": str(e)}, status=e.status)
            except delphin_tsdb.TSDBError as e:
                return JsonResponse({"error": f"[incr tsdb()] error: {e}"}, status=400)

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


def _processor_dict(p: Processor, cfg: AppSettings | None = None):
    cfg = cfg or AppSettings.load()
    default = cfg.processor()
    return {
        **p.to_dict(),
        "isDefault": default is not None and default.id == p.id,
        "grammars": p.grammars.count(),
        "status": manager.status(p).to_dict(),
    }


@ensure_csrf_cookie
@api("GET")
def status(request):
    cfg = AppSettings.load()
    # the processor the workbench uses: the active grammar's
    current = cfg.active_grammar.effective_processor() if cfg.active_grammar else cfg.processor()
    return {
        "processor": _processor_dict(current, cfg) if current else None,
        "processors": [_processor_dict(p, cfg) for p in Processor.objects.all()],
        "backends": [b.to_dict() for b in registry.all_backends()],
        "settings": cfg.to_dict(),
        "activeGrammar": _grammar_dict(cfg.active_grammar) if cfg.active_grammar else None,
        "grammars": [_grammar_dict(g) for g in Grammar.objects.all()],
        "processes": manager.processes(),
        "igdeHome": str(settings.IGDE_HOME),
    }


SETTING_FIELDS = {
    "maxResults": ("max_results", int),
    "timeoutSeconds": ("timeout_seconds", int),
    "grammarImageDir": ("grammar_image_dir", str),
    "profilesDir": ("profiles_dir", str),
}
SETTING_LIMITS = {
    "max_results": (1, 10000),
    "timeout_seconds": (1, 86400),
}


def _abs_path_or_empty(value, key):
    value = (value or "").strip()
    if value and not Path(value).expanduser().is_absolute():
        raise ApiError(f"'{key}' must be an absolute path.")
    return value


@api("GET", "PUT")
def settings_view(request):
    cfg = AppSettings.load()
    if request.method == "PUT":
        for key, (attr, typ) in SETTING_FIELDS.items():
            if key not in request.json:
                continue
            value = request.json[key]
            if typ is int:
                value = _positive_int(value, key, *SETTING_LIMITS[attr])
            else:
                value = _abs_path_or_empty(value, key)
            setattr(cfg, attr, value)
        if "defaultProcessor" in request.json:
            pid = request.json["defaultProcessor"]
            cfg.default_processor = Processor.objects.get(pk=int(pid)) if pid not in (None, "") else None
        cfg.save()
        manager.settings_changed()
    return {"settings": cfg.to_dict()}


# ---------------------------------------------------------------------------
# Processors


def _backend(key):
    try:
        return registry.get(str(key or ""))
    except KeyError as e:
        raise ApiError(str(e.args[0])) from e


def _apply_processor(p: Processor, data: dict, creating=False):
    """Validate and apply the fields in *data* to *p* (unsaved)."""
    if creating:
        p.backend = _backend(data.get("backend")).key
    backend = _backend(p.backend)
    if "name" in data or creating:
        p.name = (data.get("name") or "").strip() or p.name or backend.label
    if "location" in data:
        p.location = _abs_path_or_empty(data["location"], "location")
    if "options" in data:
        if not isinstance(data["options"], dict):
            raise ApiError("'options' must be an object.")
        try:
            p.options = backend.clean_options(data["options"], p.options)
        except ValueError as e:
            raise ApiError(str(e)) from e
    if p.location and ("location" in data) and not data.get("force"):
        st = backend.check(p.location)
        if not st.ok:
            raise ApiError(st.error, check=st.to_dict())


@api("GET", "POST")
def processor_list(request):
    if request.method == "POST":
        p = Processor()
        _apply_processor(p, request.json, creating=True)
        p.save()
        cfg = AppSettings.load()
        if cfg.default_processor_id is None or request.json.get("makeDefault"):
            cfg.default_processor = p
            cfg.save(update_fields=["default_processor"])
        return {"processor": _processor_dict(p)}
    return {"processors": [_processor_dict(p) for p in Processor.objects.all()]}


@api("GET", "PUT", "DELETE")
def processor_detail(request, pid):
    p = Processor.objects.get(pk=pid)
    if request.method == "DELETE":
        for g in p.grammars.all():
            manager.stop_grammar(g.id)
        p.delete()  # its grammars fall back to the default processor
        manager.settings_changed()
        return {"deleted": pid}
    if request.method == "PUT":
        _apply_processor(p, request.json)
        p.save()
        if request.json.get("makeDefault"):
            cfg = AppSettings.load()
            cfg.default_processor = p
            cfg.save(update_fields=["default_processor"])
        manager.settings_changed()
    return {"processor": _processor_dict(p)}


@api("POST")
def processor_check(request):
    """Validate a processor location without saving it."""
    backend = _backend(request.json.get("backend"))
    return backend.check(_abs_path_or_empty(request.json.get("location"), "location")).to_dict()


@api("GET")
def processor_detect(request):
    """Processor installs found on this machine, for every backend."""
    return {
        "found": [
            {"backend": b.key, "backendLabel": b.label, **i.to_dict()}
            for b in registry.all_backends()
            for i in b.detect()
        ]
    }


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
    return fs.find_grammar_config(request.GET.get("path", ""), _preferred_backend(request.GET.get("processor")))


def _preferred_backend(processor_id):
    if processor_id not in (None, ""):
        return Processor.objects.get(pk=int(processor_id)).backend
    default = AppSettings.load().processor()
    return default.backend if default else None


def _processor_or_none(value):
    return Processor.objects.get(pk=int(value)) if value not in (None, "") else None


# ---------------------------------------------------------------------------
# Grammars


def _slug(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "grammar"


@api("GET", "POST")
def grammars(request):
    if request.method == "GET":
        return {"grammars": [_grammar_dict(g) for g in Grammar.objects.all()]}
    cfg = AppSettings.load()
    config_path = (request.json.get("configPath") or "").strip()
    image_path = (request.json.get("imagePath") or "").strip()
    name = (request.json.get("name") or "").strip()
    processor = _processor_or_none(request.json.get("processor"))
    if config_path:
        info = fs.find_grammar_config(config_path, _preferred_backend(processor.id if processor else None))
        if info["kind"] != "source":
            raise ApiError(f"{config_path} is not a grammar configuration file.")
        config_path = info["configPath"]
        name = name or info["name"]
        if processor is None and (cfg.processor() is None or cfg.processor().backend != info["backend"]):
            # run it with a processor that reads it
            processor = Processor.objects.filter(backend=info["backend"]).first()
        if not image_path:
            suffix = registry.get(info["backend"]).image_suffix
            image_path = str(cfg.image_dir() / f"{_slug(name)}{suffix}")
            n = 2
            while Grammar.objects.filter(image_path=image_path).exists():
                image_path = str(cfg.image_dir() / f"{_slug(name)}-{n}{suffix}")
                n += 1
    elif image_path:
        p = fs.resolve(image_path)
        if not p.is_file():
            raise ApiError(f"{p} does not exist.", 404)
        image_path = str(p)
        name = name or p.stem
    else:
        raise ApiError("Provide a grammar configuration file (configPath) or a compiled grammar image (imagePath).")
    if not Path(image_path).is_absolute():
        raise ApiError("'imagePath' must be an absolute path.")
    g = Grammar.objects.create(name=name, config_path=config_path, image_path=image_path, processor=processor)
    if cfg.active_grammar_id is None:
        cfg.active_grammar = g
        cfg.save(update_fields=["active_grammar"])
    if request.json.get("compile") and g.is_source:
        try:
            manager.compile(g)
        except ProcessorUnavailable as e:
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
        if "processor" in request.json:
            manager.stop_grammar(g.id)
            g.processor = _processor_or_none(request.json["processor"])
        g.save()
    data = _grammar_dict(g)
    data["compileLog"] = g.compile_log
    return {"grammar": data}


@api("POST")
def grammar_activate(request, gid):
    g = Grammar.objects.get(pk=gid)
    cfg = AppSettings.load()
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
    cfg = AppSettings.load()
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
    # would normalize predicates, e.g. "_dog_n_rel" to _dog_n, which
    # processors don't recognize for grammars that use string predicates.
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
# TFS browsing (the processor's LUI mode)


def _lui(request, require_session=True):
    g = _grammar_for(request)
    manager.require(g, "tfs")
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
    """Processors may report TDL locations relative to the directory the
    grammar was compiled in."""
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
    cfg = AppSettings.load()
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
# Test suites ([incr tsdb()] profiles)


def _profile_dict(p: Profile, stats=True):
    job = profiles.job(p.id)
    if p.run_status == Profile.RUN_RUNNING and job is None:
        # the server was restarted during the run
        p.run_status = Profile.RUN_FAILED
        p.run_log += "\n(interrupted: IGDE was restarted during the run)\n"
        p.save(update_fields=["run_status", "run_log"])
    d = p.to_dict()
    d["progress"] = job.to_dict() if job else None
    # don't read a profile while the processor is still writing it
    d["stats"] = profiles.stats_for(p) if stats and job is None else None
    return d


@api("GET", "POST")
def profile_list(request):
    if request.method == "GET":
        return {"profiles": [_profile_dict(p) for p in Profile.objects.all()]}
    action = _body(request, "action")
    name = (request.json.get("name") or "").strip()
    if action == "create":
        if not name:
            raise ApiError("Give the test suite a name.")
        directory = (request.json.get("directory") or "").strip()
        base = fs.resolve(directory) if directory else AppSettings.load().run_dir().parent / "testsuites"
        path = base / _slug(name)
        items = profiles.parse_item_lines(request.json.get("text") or "")
        if not items:
            raise ApiError("Add at least one test item (one per line).")
        profiles.create_suite(path, items)
        p = Profile.objects.create(name=name, path=str(path), kind=Profile.SUITE)
    elif action == "add":
        path = fs.resolve(_body(request, "path"))
        if not profiles.is_profile(path):
            raise ApiError(f"{path} is not an [incr tsdb()] profile (it has no relations file).")
        p = Profile.objects.create(name=name or path.name, path=str(path), kind=Profile.SUITE)
    else:
        raise ApiError("'action' must be 'create' or 'add'.")
    return {"profile": _profile_dict(p)}


@api("GET", "PATCH", "DELETE")
def profile_detail(request, pid):
    p = Profile.objects.get(pk=pid)
    if request.method == "DELETE":
        job = profiles.job(p.id)
        if job:
            job.cancel.set()
            job.thread.join(30)
        if request.GET.get("files") == "1":
            run_dir = AppSettings.load().run_dir().resolve()
            path = Path(p.path).resolve()
            if not (p.owned and run_dir in path.parents):
                raise ApiError("Only runs IGDE created can be deleted from disk.")
            profiles.remove_owned(path)
        p.delete()
        return {"deleted": pid}
    if request.method == "PATCH":
        if (request.json.get("name") or "").strip():
            p.name = request.json["name"].strip()
            p.save(update_fields=["name"])
    data = _profile_dict(p)
    data["runLog"] = p.run_log
    if data["exists"] and data["progress"] is None:
        data["rows"] = profiles.item_rows(p.path)
    elif data["exists"]:
        data["rows"] = [{**i, "processed": False} for i in profiles.read_items(p.path)]
    return {"profile": data}


@api("PUT")
def profile_items(request, pid):
    p = Profile.objects.get(pk=pid)
    if profiles.job(p.id):
        raise ApiError("This profile is being processed.", 409)
    items = request.json.get("items")
    if not isinstance(items, list):
        raise ApiError("'items' must be a list.")
    clean = []
    for i in items:
        if not isinstance(i, dict):
            raise ApiError("Each item must be an object.")
        iid = i.get("id")
        clean.append(
            {
                "id": _positive_int(iid, "id", 0, 2**31) if iid not in (None, "") else None,
                "input": str(i.get("input") or ""),
                "wf": 1 if i.get("wf", 1) else 0,
                "comment": str(i.get("comment") or ""),
            }
        )
    profiles.write_items(p.path, clean)
    return {"profile": {**_profile_dict(p), "rows": profiles.item_rows(p.path)}}


@api("POST")
def profile_run(request, pid):
    suite = Profile.objects.get(pk=pid)
    g = _grammar_for(request)
    run = profiles.start_run(suite, g, _n(request))
    return {"profile": _profile_dict(run)}


@api("POST")
def profile_cancel(request, pid):
    job = profiles.job(pid)
    if job:
        job.cancel.set()
    return {"cancelling": bool(job)}


@api("GET")
def profile_item(request, pid, iid):
    p = Profile.objects.get(pk=pid)
    if profiles.job(p.id):
        raise ApiError("This profile is being processed.", 409)
    return profiles.item_results(p.path, iid)


@api("GET")
def profile_compare(request, pid, other):
    a, b = Profile.objects.get(pk=pid), Profile.objects.get(pk=other)
    if profiles.job(a.id) or profiles.job(b.id):
        raise ApiError("Wait for the run to finish.", 409)
    return profiles.compare(a.path, b.path)


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
