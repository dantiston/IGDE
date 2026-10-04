"""What IGDE needs from a grammar processor.

IGDE isn't tied to one processor: a *backend* (a subclass of
:class:`Backend`) knows how to find, validate and run one kind of
processor, and how to recognise the grammars it reads.  The user then
configures any number of *processors* (``core.models.Processor``: a
backend plus where it's installed and its options) and picks one per
grammar.

Parsing and generation go through PyDelphin's processor interface
(``interact(datum) -> Response``), so they work with any processor
PyDelphin can drive; TFS browsing needs a processor that speaks the LUI
protocol (see ``lui_session.py``).
"""

from __future__ import annotations

import os
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path

from django.conf import settings

# What a processor can do; the UI hides what it can't.
PARSE, GENERATE, TFS, COMPILE = "parse", "generate", "tfs", "compile"


class ProcessorUnavailable(RuntimeError):
    """The processor can't do what was asked (not installed, no image, ...)."""


@dataclass
class Option:
    """A processor-specific setting, shown as a field on the Settings page."""

    key: str
    label: str
    default: int | str
    help: str = ""
    type: str = "int"  # "int" | "str"
    min: int | None = None
    max: int | None = None

    def clean(self, value):
        if self.type == "int":
            try:
                v = int(value)
            except (TypeError, ValueError) as e:
                raise ValueError(f"'{self.label}' must be an integer.") from e
            if (self.min is not None and v < self.min) or (self.max is not None and v > self.max):
                raise ValueError(f"'{self.label}' must be between {self.min} and {self.max}.")
            return v
        return str(value or "").strip()

    def to_dict(self):
        return asdict(self)


@dataclass
class ProcessorStatus:
    ok: bool
    source: str | None  # how the executable was found (a key of Backend.sources)
    location: str | None  # what it was found from
    executable: str | None
    version: str | None
    error: str | None

    def to_dict(self):
        return asdict(self)


@dataclass
class Install:
    """A processor found on this machine."""

    source: str
    path: str
    version: str

    def to_dict(self):
        return asdict(self)


@dataclass
class GrammarInfo:
    """What a backend makes of a grammar path (see Backend.describe_grammar)."""

    kind: str  # "source" | "image"
    name: str
    config_path: str = ""
    image_path: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        d = {"kind": self.kind, "name": self.name, **self.extra}
        if self.config_path:
            d["configPath"] = self.config_path
        if self.image_path:
            d["imagePath"] = self.image_path
        return d


class Backend:
    """One kind of grammar processor."""

    key: str = ""
    label: str = ""
    description: str = ""
    homepage: str = ""
    capabilities: frozenset[str] = frozenset()
    #: processor-specific options (beyond IGDE's general results/timeout)
    options: tuple[Option, ...] = ()
    #: how to describe where the processor is installed
    location_label: str = "Location"
    location_help: str = ""
    #: how each Install/ProcessorStatus ``source`` reads in the UI
    sources: dict[str, str] = {}
    #: a shell command that installs the processor, if there's an easy one
    install_command: str = ""
    #: environment variables that change where the processor is found
    env_vars: tuple[str, ...] = ()
    #: the grammar description (config) files and images this backend reads
    config_label: str = "grammar configuration"
    image_suffix: str = ".dat"
    image_suffixes: frozenset[str] = frozenset()

    # -- installation ------------------------------------------------------
    def check(self, location: str | None) -> ProcessorStatus:
        """Resolve and validate the processor; *location* may be empty
        (find it automatically)."""
        raise NotImplementedError

    def detect(self) -> list[Install]:
        """Installs of this processor found on the machine."""
        return []

    def env(self) -> dict:
        """The environment to run the processor in."""
        return utf8_env()

    # -- grammars ----------------------------------------------------------
    def classify(self, p: Path, is_dir: bool) -> str | None:
        """A file manager hint: "grammar-dir", "config" or "image"."""
        return None

    def describe_grammar(self, p: Path) -> GrammarInfo | None:
        """Work out what grammar *p* (a directory, config file or image) is,
        or None if this backend doesn't recognise it.  Raises ValueError for
        a file that's meant for this backend but broken."""
        return None

    def grammar_root(self, config_path: Path) -> Path:
        """The directory of the grammar described by *config_path*."""
        return config_path.parent

    def image_grammar_root(self, image_path: Path) -> Path:
        """The grammar directory for a precompiled image."""
        return image_path.parent

    def compile_command(self, executable: str, config: Path, image: Path) -> list[str]:
        raise ProcessorUnavailable(f"{self.label} grammars can't be compiled by IGDE.")

    # -- processing --------------------------------------------------------
    def processing_args(self, options: dict, max_results: int, timeout: int) -> list[str]:
        """Command line arguments for processing with these options."""
        return []

    def parser(self, executable, image, args, env, stderr):
        """A PyDelphin processor (``interact(sentence) -> Response``)."""
        raise ProcessorUnavailable(f"{self.label} can't parse.")

    def generator(self, executable, image, args, env, stderr):
        """A PyDelphin processor (``interact(mrs) -> Response``)."""
        raise ProcessorUnavailable(f"{self.label} can't generate.")

    def lui_session(self, executable, image, args, env, cwd):
        """A ``LuiSession`` for TFS browsing."""
        raise ProcessorUnavailable(f"{self.label} doesn't support TFS browsing (LUI).")

    # -- helpers -----------------------------------------------------------
    def clean_options(self, values: dict | None, partial: dict | None = None) -> dict:
        """Validated options: *values* over *partial* (the saved ones)."""
        out = {}
        values = values or {}
        for opt in self.options:
            if opt.key in values:
                out[opt.key] = opt.clean(values[opt.key])
            elif partial and opt.key in partial:
                out[opt.key] = partial[opt.key]
        return out

    def resolved_options(self, saved: dict | None) -> dict:
        return {opt.key: (saved or {}).get(opt.key, opt.default) for opt in self.options}

    def to_dict(self):
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "homepage": self.homepage,
            "capabilities": sorted(self.capabilities),
            "options": [o.to_dict() for o in self.options],
            "locationLabel": self.location_label,
            "locationHelp": self.location_help,
            "sources": self.sources,
            "installCommand": self.install_command,
            "envVars": {v: os.environ.get(v) for v in self.env_vars},
            "configLabel": self.config_label,
            "imageSuffixes": sorted(self.image_suffixes),
        }


def _utf8_locale() -> str:
    return "en_US.UTF-8" if platform.system() == "Darwin" else "C.UTF-8"


def utf8_env(home: str | None = None) -> dict:
    """The server's environment, with a UTF-8 locale.

    DELPH-IN grammars are UTF-8, and C processors read them through the C
    locale, so they fail on non-ASCII TDL (e.g. the ERG) without one.  With
    *home*, HOME points at a private directory under IGDE_HOME so that the
    processor's dotfiles (e.g. readline history) stay out of the user's.
    """
    env = dict(os.environ)
    current = env.get("LC_ALL") or env.get("LC_CTYPE") or env.get("LANG") or ""
    if "utf-8" not in current.lower() and "utf8" not in current.lower():
        env["LC_ALL"] = _utf8_locale()
    if home:
        d = Path(settings.IGDE_HOME) / home
        d.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(d)
    return env
