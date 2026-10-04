# IGDE

Integrated Grammar Development Environment: a web interface to the high-performance
[ACE](http://sweaglesw.org/linguistics/ace/) processor for working with
[DELPH-IN](http://www.delph-in.net) style
[HPSG](https://en.wikipedia.org/wiki/Head-driven_phrase_structure_grammar) grammars:
parsing, generation and exploring grammars (typed feature structures, lexical
entries, rules, the type hierarchy, interactive unification), plus a file
manager for the grammar's source files.

IGDE runs on your own machine: a small [Django](https://www.djangoproject.com)
server drives your local ACE install and reads your grammar files in place,
and a [React](https://react.dev) app is the user interface.

## Features

* **ACE settings**: point IGDE at your ACE install (`ACE_ROOT`), check its
  version, set processing limits (results, timeout, memory), and see and stop
  the ACE processes IGDE is running.
* **Grammars**: an explorer of the grammars stored on your machine and
  their files. Add a grammar by its ACE `config.tdl` or folder (IGDE compiles
  it with ACE in the background and shows the log) or by a precompiled
  image (`.dat`); expand it to browse and edit its TDL in the editor (with
  save conflict detection), recompile after changes, and choose the active
  grammar. A Disk tab opens any other file.
* **Test Suites**: [incr tsdb()] profiles. Create a test suite from
  sentences (a leading `*` marks an ungrammatical item) or add any existing
  profile (e.g. a grammar's `tsdb/gold` profiles), edit its items, and run it
  with the active grammar: each run is a new profile (in `~/.igde/profiles`
  by default), processed by ACE in the background with progress and cancel.
  Inspect coverage, overgeneration, readings, timing and errors, open any
  item's trees and MRS, and compare a run with an earlier run or with gold:
  items are marked gained, lost, changed (the other profile's analysis is no
  longer produced; MRSs compared up to isomorphism) or readings (same
  analysis, different number of readings).
* **Workbench**: one running feed. From the input bar at the top, parse a
  sentence, generate from an MRS (paste one, or pick any parse in the feed),
  or look up a type, lexical entry, rule or instance; each result is added to
  the top of the feed:
  * parses: every reading's tree (node labels or rule names) and semantics
    as an MRS AVM, a DMRS graph, or SimpleMRS, DMRS and EDS text, with
    “Generate from this MRS”;
  * realizations, with their trees, each one parseable in turn;
  * typed feature structures: click any node of a parse tree to add its full
    feature structure (from ACE's LUI mode) to the feed; definitions link to
    their TDL source in the editor;
  * the type hierarchy around a type;
  * interactive unification: click a feature in one feature structure and
    another in a second one, and the result (or the failure, highlighted at
    the failing path) is added to the feed.

The pages are in a sidebar on the left, which collapses to icons with the
« button or Ctrl/⌘+B.

## Requirements

* Python 3.10+
* Node.js 20+ (only to build the frontend)
* [ACE](http://sweaglesw.org/linguistics/ace/) 0.9.24+ (Linux or macOS), e.g. from
  [Homebrew](https://github.com/delph-in/homebrew-delphin):
  `brew install delph-in/delphin/ace`
* a grammar, e.g. the [ERG](https://github.com/delph-in/erg)

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate

cd frontend
npm install
npm run build
cd ..

.venv/bin/python manage.py runserver
```

Then open <http://127.0.0.1:8000/> and:

1. **ACE Settings**: IGDE finds ACE on its own when `ACE_ROOT` is left
   empty: from the `$ACE_ROOT` environment variable, `ace` on `$PATH`, or a
   Homebrew install (`/opt/homebrew`, `/usr/local`, Linuxbrew, including
   versioned formulas like `ace@0.9.33`); the page lists every ACE it found.
   Otherwise set `ACE_ROOT` to the directory containing the `ace` binary
   (e.g. an unpacked `ace-0.9.34/`) or to the binary itself, click *Test*,
   then *Save settings*.
2. **Grammars → + Add grammar**: browse to a grammar directory (one with
   `ace/config.tdl` or `config.tdl`) or a compiled `.dat` image and click
   *Add*.  Source grammars are compiled into `~/.igde/grammars/`.
3. Parse, generate, and browse.

IGDE keeps its state (database, secret key, compiled grammars) in `~/.igde`;
set `IGDE_HOME` to use another directory.

### Development

Run Django and the Vite dev server (with hot reloading) side by side; Vite
proxies `/api` to Django:

```sh
.venv/bin/python manage.py runserver      # http://127.0.0.1:8000
cd frontend && npm run dev                # http://localhost:5173
```

### Tests

```sh
# backend; the ACE integration tests run when ACE can be found
IGDE_TEST_ACE_ROOT=/path/to/ace-0.9.34 .venv/bin/python manage.py test core

# frontend
cd frontend && npm test && npm run lint && npx tsc -b
```

The integration tests compile and use `core/tests/fixtures/tiniest`, a tiny
grammar derived from
[delphin-tiniest-grammar](https://github.com/dantiston/delphin-tiniest-grammar).

## How it works

* `core/ace/environment.py` resolves and validates ACE from `ACE_ROOT`, and
  runs ACE with a UTF-8 locale (ACE can't read the ERG's TDL otherwise).
* `core/ace/manager.py` keeps one parser, one generator and one LUI session
  per grammar alive, restarting them when ACE, the grammar image or the
  options change, and runs grammar compilation in the background.  Parsing
  and generation go through [PyDelphin](https://github.com/delph-in/pydelphin)'s
  ACE interface.
* `core/ace/lui_session.py` drives `ace -l` as if it were the
  [LUI](https://github.com/delph-in/docs/wiki/LkbLui) viewer: sentences and
  `:t`/`:l`/`:r`/`:H` commands go to ACE's stdin, `browse`/`unify` requests
  go over the `--lui-fd` socket, and `core/ace/lui.py` parses ACE's replies
  (`#D[...]` AVMs, `#T[...]` trees, hierarchies) into JSON.
* `core/views.py` is the JSON API under `/api/`; it also serves the built
  React app from `frontend/dist`.
* `frontend/` is a React 19 + TypeScript app built with Vite.

### Security

IGDE can read and write any file your user can, and runs the ACE binary you
configure, so it only answers on `localhost`/`127.0.0.1` (set
`IGDE_ALLOWED_HOSTS` to change that) and every change requires Django's
CSRF token.  Don't expose it to a network.

# VERSION HISTORY

* v2.0: React 19 frontend, Django 5.2; ACE_ROOT configuration (and Homebrew
  detection) and process management; local grammar/file manager with
  compilation and editing; a workbench feed of parses (trees, MRS, DMRS,
  EDS), generations, and typed feature structures with interactive
  unification via ACE's LUI mode; [incr tsdb()] test suites with runs,
  inspection and comparison.
* v0.1: basic UI, parsing.
