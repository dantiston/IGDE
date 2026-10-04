from pathlib import Path

from django.conf import settings
from django.db import models


class Processor(models.Model):
    """A grammar processor IGDE can drive: a backend (see
    ``core.processors.registry``), where it's installed, and its options."""

    name = models.CharField(max_length=200)
    backend = models.CharField(max_length=32)
    # Where the processor is installed (backend-specific, e.g. an ACE_ROOT);
    # empty means "find it automatically".
    location = models.CharField(max_length=4096, blank=True, default="")
    options = models.JSONField(default=dict, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

    def get_backend(self):
        from core.processors import registry

        return registry.get(self.backend)

    def to_dict(self):
        try:
            backend = self.get_backend()
            options, label = backend.resolved_options(self.options), backend.label
        except KeyError:
            options, label = dict(self.options), self.backend
        return {
            "id": self.id,
            "name": self.name,
            "backend": self.backend,
            "backendLabel": label,
            "location": self.location,
            "options": options,
        }


class AppSettings(models.Model):
    """Singleton holding IGDE's settings."""

    # the processor for grammars that don't name one
    default_processor = models.ForeignKey(
        Processor, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # how many results to keep per input, and how long to spend on one
    max_results = models.PositiveIntegerField(default=5)
    timeout_seconds = models.PositiveIntegerField(default=60)
    # Where compiled grammar images go by default.
    grammar_image_dir = models.CharField(max_length=4096, blank=True, default="")
    # Where test suite runs (processed [incr tsdb()] profiles) are written.
    profiles_dir = models.CharField(max_length=4096, blank=True, default="")
    active_grammar = models.ForeignKey(
        "Grammar", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        if created and not Processor.objects.exists():
            # Start with one processor per backend, each finding its
            # installation automatically.
            from core.processors import registry

            for b in registry.all_backends():
                p = Processor.objects.create(name=b.label, backend=b.key)
                if obj.default_processor_id is None:
                    obj.default_processor = p
            obj.save(update_fields=["default_processor"])
        return obj

    def processor(self) -> Processor | None:
        """The default processor (the first one if none was chosen)."""
        return self.default_processor or Processor.objects.first()

    def image_dir(self) -> Path:
        if self.grammar_image_dir:
            return Path(self.grammar_image_dir).expanduser()
        return settings.IGDE_HOME / "grammars"

    def run_dir(self) -> Path:
        if self.profiles_dir:
            return Path(self.profiles_dir).expanduser()
        return settings.IGDE_HOME / "profiles"

    def to_dict(self):
        default = self.processor()
        return {
            "defaultProcessor": default.id if default else None,
            "maxResults": self.max_results,
            "timeoutSeconds": self.timeout_seconds,
            "grammarImageDir": self.grammar_image_dir,
            "defaultGrammarImageDir": str(settings.IGDE_HOME / "grammars"),
            "profilesDir": self.profiles_dir,
            "defaultProfilesDir": str(settings.IGDE_HOME / "profiles"),
            "activeGrammar": self.active_grammar_id,
        }


class Grammar(models.Model):
    """A grammar on the user's machine that IGDE knows about.

    Either a source grammar (``config_path`` points at the processor's
    grammar configuration, e.g. ACE's config.tdl, and ``image_path`` is
    where IGDE compiles it to) or a precompiled grammar image
    (``config_path`` empty, ``image_path`` points at the image).

    ``processor`` is the processor that runs it; empty means the default.
    """

    COMPILE_IDLE = "idle"
    COMPILE_RUNNING = "running"
    COMPILE_OK = "ok"
    COMPILE_FAILED = "failed"

    name = models.CharField(max_length=200)
    config_path = models.CharField(max_length=4096, blank=True, default="")
    image_path = models.CharField(max_length=4096)
    created = models.DateTimeField(auto_now_add=True)
    compile_status = models.CharField(max_length=16, default=COMPILE_IDLE)
    compile_log = models.TextField(blank=True, default="")
    compiled_at = models.DateTimeField(null=True, blank=True)
    processor = models.ForeignKey(Processor, null=True, blank=True, on_delete=models.SET_NULL, related_name="grammars")

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

    @property
    def is_source(self) -> bool:
        return bool(self.config_path)

    def effective_processor(self) -> Processor | None:
        return self.processor or AppSettings.load().processor()

    def backend(self):
        p = self.effective_processor()
        try:
            return p.get_backend() if p else None
        except KeyError:
            return None

    @property
    def root_dir(self) -> Path:
        """The directory to show in the grammar's file tree."""
        b = self.backend()
        if self.config_path:
            cfg = Path(self.config_path)
            return b.grammar_root(cfg) if b else cfg.parent
        image = Path(self.image_path)
        return b.image_grammar_root(image) if b else image.parent

    def image_info(self):
        p = Path(self.image_path)
        if p.is_file():
            st = p.stat()
            return {"exists": True, "size": st.st_size, "mtime": st.st_mtime}
        return {"exists": False, "size": None, "mtime": None}

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "kind": "source" if self.is_source else "image",
            "configPath": self.config_path,
            "imagePath": self.image_path,
            "rootDir": str(self.root_dir),
            "image": self.image_info(),
            "compileStatus": self.compile_status,
            "compiledAt": self.compiled_at.isoformat() if self.compiled_at else None,
            "processor": self.processor_id,
        }


class Profile(models.Model):
    """An [incr tsdb()] profile on the user's machine.

    A *test suite* is a profile the user created or added (a skeleton of test
    items, or any existing profile such as a grammar's gold profiles).  A
    *run* is a profile IGDE made by processing a test suite's items with a
    grammar; IGDE owns its directory.
    """

    SUITE = "suite"
    RUN = "run"

    RUN_IDLE = "idle"
    RUN_RUNNING = "running"
    RUN_OK = "ok"
    RUN_FAILED = "failed"
    RUN_CANCELLED = "cancelled"

    name = models.CharField(max_length=300)
    path = models.CharField(max_length=4096)
    kind = models.CharField(max_length=8, default=SUITE)
    suite = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="runs")
    grammar = models.ForeignKey(Grammar, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    grammar_name = models.CharField(max_length=200, blank=True, default="")
    owned = models.BooleanField(default=False)  # IGDE created the directory
    created = models.DateTimeField(auto_now_add=True)
    run_status = models.CharField(max_length=16, default=RUN_IDLE)
    run_log = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["kind", "name", "id"]

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "kind": self.kind,
            "suite": self.suite_id,
            "grammar": self.grammar_id,
            "grammarName": self.grammar_name,
            "owned": self.owned,
            "created": self.created.isoformat() if self.created else None,
            "runStatus": self.run_status,
            "exists": Path(self.path).is_dir(),
        }
