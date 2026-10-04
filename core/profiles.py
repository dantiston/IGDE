"""[incr tsdb()] test suites: creating, editing, running and inspecting
profiles with PyDelphin."""

from __future__ import annotations

import datetime as dt
import getpass
import logging
import re
import shutil
import tempfile
import threading
import time
from pathlib import Path

from delphin import ace as delphin_ace
from delphin import commands, itsdb, mrs as mrs_mod, tsdb
from delphin.codecs import simplemrs
from django.db import close_old_connections

from .ace import environment, results
from .ace.manager import AceUnavailable, manager

log = logging.getLogger(__name__)

RELATIONS = Path(__file__).parent / "tsdb" / "Relations"


class ProfileError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def is_profile(path) -> bool:
    return tsdb.is_database_directory(path)


def _open(path) -> itsdb.TestSuite:
    if not is_profile(path):
        raise ProfileError(f"{path} is not an [incr tsdb()] profile (no relations file).", 404)
    return itsdb.TestSuite(path)


def _num(v, default=None):
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default


# ---------------------------------------------------------------------------
# Items


def parse_item_lines(text: str) -> list[dict]:
    """One test item per line; a leading ``*`` marks an ungrammatical item
    (i-wf 0), as in [incr tsdb()] test suite files.  Blank lines and lines
    starting with ``;`` or ``#`` are skipped."""
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in ";#":
            continue
        wf = 1
        if line.startswith("*"):
            wf, line = 0, line[1:].strip()
        if line:
            items.append({"input": line, "wf": wf})
    return items


def read_items(path) -> list[dict]:
    ts = _open(path)
    out = []
    for row in ts["item"]:
        out.append(
            {
                "id": _num(row["i-id"]),
                "input": row["i-input"] or "",
                "wf": _num(row["i-wf"], 1),
                "comment": row["i-comment"] or "",
            }
        )
    out.sort(key=lambda r: (r["id"] is None, r["id"]))
    return out


def write_items(path, items: list[dict]):
    """Replace a profile's items, keeping any other columns of items whose
    id is unchanged; new items get fresh ids."""
    ts = _open(path)
    fields = ts.schema["item"]
    names = [f.name for f in fields]
    existing = {_num(r["i-id"]): {n: r[n] for n in names} for r in ts["item"]}
    used = {i["id"] for i in items if i.get("id") is not None}
    if len(used) != len([i for i in items if i.get("id") is not None]):
        raise ProfileError("Item ids must be unique.")
    next_id = max([*existing, *used, 0]) + 1
    today = dt.date.today()
    records = []
    for item in items:
        text = (item.get("input") or "").strip()
        if not text:
            raise ProfileError("Items cannot be empty.")
        iid = item.get("id")
        if iid is None:
            iid, next_id = next_id, next_id + 1
        rec = existing.get(iid) or {n: None for n in names}
        rec.update(
            {
                "i-id": int(iid),
                "i-input": text,
                "i-wf": 1 if item.get("wf", 1) else 0,
                "i-comment": (item.get("comment") or None),
                "i-length": len(text.split()),
            }
        )
        if iid not in existing:
            rec.update({"i-origin": "IGDE", "i-author": _user(), "i-date": today, "i-difficulty": 1})
        records.append([rec[n] for n in names])
    gz = (Path(path) / "item.gz").exists()
    tsdb.write(path, "item", records, fields=fields, gzip=gz)
    _cache.clear()


def _user():
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return None


def create_suite(path, items: list[dict]):
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise ProfileError(f"{path} already exists and is not empty.")
    path.mkdir(parents=True, exist_ok=True)
    tsdb.initialize_database(path, schema=RELATIONS, files=True)
    write_items(path, items)


# ---------------------------------------------------------------------------
# Reading results

_cache: dict = {}


def _stamp(path):
    p = Path(path)
    out = []
    for name in ("item", "parse", "result", "run"):
        for f in (p / name, p / f"{name}.gz"):
            if f.exists():
                st = f.stat()
                out.append((f.name, st.st_mtime_ns, st.st_size))
    return tuple(out)


def _cached(kind, path, fn):
    key = (kind, str(path))
    stamp = _stamp(path)
    hit = _cache.get(key)
    if hit and hit[0] == stamp:
        return hit[1]
    value = fn()
    _cache[key] = (stamp, value)
    return value


def _parses_by_item(ts):
    """i-id -> the (last) parse row for it."""
    out = {}
    for row in ts["parse"]:
        out[_num(row["i-id"])] = row
    return out


def item_rows(path) -> list[dict]:
    def build():
        ts = _open(path)
        parses = _parses_by_item(ts)
        nresults = {}
        for r in ts["result"]:
            pid = _num(r["parse-id"])
            nresults[pid] = nresults.get(pid, 0) + 1
        rows = []
        for item in read_items(path):
            p = parses.get(item["id"])
            row = {**item, "processed": p is not None, "readings": None, "time": None, "error": None, "results": 0}
            if p is not None:
                row["readings"] = _num(p["readings"])
                row["time"] = _num(p["tcpu"])
                row["error"] = (p["error"] or None) if p["error"] not in ("", None) else None
                row["results"] = nresults.get(_num(p["parse-id"]), 0)
            rows.append(row)
        return rows

    return _cached("rows", path, build)


def summary(path) -> dict:
    rows = item_rows(path)
    processed = [r for r in rows if r["processed"]]
    wf = [r for r in rows if r["wf"]]
    ill = [r for r in rows if not r["wf"]]
    parsed = [r for r in processed if (r["readings"] or 0) > 0]
    times = [r["time"] for r in processed if (r["time"] or -1) >= 0]
    return {
        "items": len(rows),
        "wellformed": len(wf),
        "illformed": len(ill),
        "processed": len(processed),
        "parsed": len(parsed),
        "coverage": _ratio(sum(1 for r in parsed if r["wf"]), len(wf)) if processed else None,
        "overgeneration": _ratio(sum(1 for r in parsed if not r["wf"]), len(ill)) if processed and ill else None,
        "errors": sum(1 for r in processed if r["error"]),
        "avgReadings": round(sum(r["readings"] for r in parsed) / len(parsed), 2) if parsed else None,
        "avgTime": round(sum(times) / len(times), 1) if times else None,
        "runInfo": run_info(path),
    }


def _ratio(n, d):
    return round(n / d, 4) if d else None


def run_info(path):
    ts = _open(path)
    rows = list(ts["run"])
    if not rows:
        return None
    r = rows[-1]
    keys = {f.name for f in ts.schema["run"]}

    def get(k):
        v = r[k] if k in keys else None
        return v.isoformat(sep=" ") if isinstance(v, (dt.datetime, dt.date)) else v

    return {k: get(k) for k in ("application", "grammar", "start", "end", "user", "host")}


def item_results(path, iid: int) -> dict:
    ts = _open(path)
    item = next((r for r in read_items(path) if r["id"] == iid), None)
    if item is None:
        raise ProfileError(f"No item {iid}.", 404)
    parse = _parses_by_item(ts).get(iid)
    out = {"item": item, "processed": parse is not None, "results": []}
    if parse is None:
        return out
    out["readings"] = _num(parse["readings"])
    out["error"] = parse["error"] or None
    out["time"] = _num(parse["tcpu"])
    pid = _num(parse["parse-id"])
    rows = sorted((r for r in ts["result"] if _num(r["parse-id"]) == pid), key=lambda r: _num(r["result-id"], 0))
    for r in rows:
        raw = r["mrs"] or None
        m = None
        if raw:
            try:
                m = simplemrs.decode(raw)
            except Exception:  # noqa: BLE001
                m = None
        deriv = results.derivation_dict(r["derivation"] or None)
        res = {
            "id": _num(r["result-id"]),
            "derivation": deriv,
            "tree": results.parse_labelled_tree(r["tree"] or None),
            "surface": r["surface"] or None,
            "mrsString": raw,
            "signature": results.entity_signature(deriv),
        }
        res.update(results.semantics(m, raw) if m is not None else {"simplemrs": raw})
        out["results"].append(res)
    return out


# ---------------------------------------------------------------------------
# Comparison


def _top_mrs(path):
    """i-id -> (readings, [MRS of each result, in order])."""

    def build():
        ts = _open(path)
        by_parse: dict[int, list] = {}
        for r in ts["result"]:
            by_parse.setdefault(_num(r["parse-id"]), []).append((_num(r["result-id"], 0), r["mrs"]))
        out = {}
        for iid, p in _parses_by_item(ts).items():
            mrss = []
            for _, raw in sorted(by_parse.get(_num(p["parse-id"]), []), key=lambda x: x[0]):
                try:
                    mrss.append(simplemrs.decode(raw) if raw else None)
                except Exception:  # noqa: BLE001
                    mrss.append(None)
            out[iid] = (_num(p["readings"]), mrss)
        return out

    return _cached("mrs", path, build)


def compare(path, other_path) -> dict:
    """Compare a profile with another (e.g. an earlier run, or gold).

    For each item: ``gained`` (parses now, didn't in the other), ``lost``
    (the reverse), ``changed`` (the other profile's first analysis, e.g. the
    gold one, is no longer among this profile's results), ``readings``
    (same analysis, different number of readings), or ``same``.  MRSs are
    compared up to isomorphism, so variable numbering doesn't matter."""
    a, b = _top_mrs(path), _top_mrs(other_path)
    statuses = {}
    for iid in set(a) | set(b):
        ra, ma = a.get(iid, (None, []))
        rb, mb = b.get(iid, (None, []))
        pa, pb = (ra or 0) > 0, (rb or 0) > 0
        if iid not in a or iid not in b:
            status = "missing"
        elif pa and not pb:
            status = "gained"
        elif pb and not pa:
            status = "lost"
        elif not pa:
            status = "same"
        else:
            target = next((m for m in mb if m is not None), None)
            found = target is None or any(m is not None and _iso(m, target) for m in ma)
            status = "changed" if not found else "same" if ra == rb else "readings"
        statuses[iid] = {"status": status, "readings": ra, "otherReadings": rb}
    counts: dict[str, int] = {}
    for s in statuses.values():
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    return {"items": {str(k): v for k, v in statuses.items()}, "counts": counts}


def _iso(m1, m2):
    try:
        return mrs_mod.is_isomorphic(m1, m2)
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Running a test suite


class Cancelled(Exception):
    pass


class RunJob:
    def __init__(self, profile_id, total):
        self.profile_id = profile_id
        self.total = total
        self.done = 0
        self.cancel = threading.Event()
        self.started = time.time()
        self.thread: threading.Thread | None = None

    def to_dict(self):
        return {"done": self.done, "total": self.total, "started": self.started}


_jobs: dict[int, RunJob] = {}


def job(profile_id) -> RunJob | None:
    j = _jobs.get(profile_id)
    return j if j and j.thread and j.thread.is_alive() else None


def _slug(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-") or "profile"


def start_run(suite, grammar, n=None):
    """Copy *suite*'s items into a new profile and parse them with *grammar*
    in the background.  Returns the new (run) Profile."""
    from .models import AceConfig, Profile

    cfg = AceConfig.load()
    exe = manager.executable(cfg)
    image = Path(grammar.image_path)
    if not image.is_file():
        raise AceUnavailable(f"Grammar image {image} does not exist" + (" - compile the grammar first." if grammar.is_source else "."))
    source = Path(suite.path)
    if not is_profile(source):
        raise ProfileError(f"{source} is not an [incr tsdb()] profile.", 404)
    total = len(read_items(source))
    if not total:
        raise ProfileError("This test suite has no items.")

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = cfg.run_dir() / _slug(suite.name) / f"{_slug(grammar.name)}-{stamp}"
    base.parent.mkdir(parents=True, exist_ok=True)
    # never reuse a directory: two runs can start within the same second
    dest, n_ = base, 2
    while dest.exists():
        dest, n_ = base.with_name(f"{base.name}-{n_}"), n_ + 1
    commands.mkprof(dest, source=source, skeleton=True, quiet=True)

    run = Profile.objects.create(
        name=f"{grammar.name} {dt.datetime.now():%Y-%m-%d %H:%M:%S}",
        path=str(dest),
        kind=Profile.RUN,
        suite=suite,
        grammar=grammar,
        grammar_name=grammar.name,
        owned=True,
        run_status=Profile.RUN_RUNNING,
    )
    j = RunJob(run.id, total)
    j.thread = threading.Thread(target=_run_job, args=(j, str(dest), str(image), exe, manager._cmdargs(cfg, n)), daemon=True)
    _jobs[run.id] = j
    j.thread.start()
    return run


def _run_job(j: RunJob, dest, image, exe, cmdargs):
    from .models import Profile

    close_old_connections()
    status, logtext = Profile.RUN_FAILED, ""
    started = time.time()
    with tempfile.TemporaryFile() as stderr:
        try:
            ts = itsdb.TestSuite(dest)

            def progress(_response):
                j.done += 1
                if j.cancel.is_set():
                    raise Cancelled()

            with delphin_ace.ACEParser(image, executable=exe, cmdargs=list(cmdargs), env=environment.process_env(), stderr=stderr) as cpu:
                # small buffer: results are written as we go, so a cancelled
                # run keeps what it has done
                ts.process(cpu, callback=progress, buffer_size=20)
            status = Profile.RUN_OK
            logtext = f"Processed {j.done} items in {time.time() - started:.1f}s.\n"
        except Cancelled:
            status = Profile.RUN_CANCELLED
            logtext = f"Cancelled after {j.done} of {j.total} items.\n"
        except Exception as e:  # noqa: BLE001
            log.exception("test suite run failed")
            logtext = f"Run failed after {j.done} of {j.total} items: {e}\n"
        finally:
            try:
                stderr.seek(0)
                tail = stderr.read()[-20000:].decode("utf-8", "replace")
            except (OSError, ValueError):
                tail = ""
            _cache.clear()
            Profile.objects.filter(pk=j.profile_id).update(run_status=status, run_log=logtext + tail)
            close_old_connections()


def remove_owned(path):
    """Delete a run directory IGDE created."""
    p = Path(path)
    if p.is_dir() and is_profile(p):
        shutil.rmtree(p)
        try:
            p.parent.rmdir()  # the suite's run folder, if now empty
        except OSError:
            pass


def stats_for(profile):
    if not Path(profile.path).is_dir() or not is_profile(profile.path):
        return None
    try:
        return summary(profile.path)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
