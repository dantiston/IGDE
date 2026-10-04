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
* **Grammars**: register grammars stored on your machine, either a grammar's
  ACE `config.tdl` (IGDE compiles it with ACE in the background and shows the
  log) or a precompiled grammar image (`.dat`).  Switch the active grammar
  from the header.
* **Files**: browse the local disk or the active grammar's source files, view
  and edit TDL with save conflict detection, and recompile after changes.
* **Parse**: parse a sentence and see each reading's labelled tree, derivation,
  and semantics as an MRS AVM, a DMRS graph, or SimpleMRS, DMRS and EDS text.
* **Generate**: generate from an MRS, e.g. one from a parse result.
* **TFS Browser**: parse in ACE's LUI mode and click any tree node to see its
  full feature structure (and MRS); look up types, lexical entries, rules and
  instances; view the type hierarchy around a type; and unify any two
  (sub)structures, with failures shown at the failing path.  Definitions link
  to their TDL source in the editor.

## Requirements

* Python 3.10+
* Node.js 20+ (only to build the frontend)
* [ACE](http://sweaglesw.org/linguistics/ace/) 0.9.24+ (Linux or macOS)
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

1. **ACE Settings**: set `ACE_ROOT` to the directory containing the `ace`
   binary (e.g. an unpacked `ace-0.9.34/`) or to the binary itself, click
   *Test*, then *Save settings*.  If `ACE_ROOT` is left empty IGDE uses the
   `$ACE_ROOT` environment variable, then `ace` on `$PATH`.
2. **Grammars → Add grammar…**: browse to a grammar directory (one with
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

* v2.0: React 19 frontend, Django 5.2; ACE_ROOT configuration and process
  management; local grammar/file manager with compilation and editing; parse
  (trees, MRS, DMRS, EDS), generation, and TFS browsing with interactive
  unification via ACE's LUI mode.
* v0.1: basic UI, parsing.
