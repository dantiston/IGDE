from pathlib import Path

from django.conf import settings
from django.db import models


class AceConfig(models.Model):
    """Singleton holding how IGDE finds and drives the local ACE install."""

    # Directory containing the ``ace`` binary (an unpacked ACE release, or
    # e.g. /usr/local/bin), or the path to the binary itself.  Empty means
    # "use $ACE_ROOT, then ``ace`` on $PATH".
    ace_root = models.CharField(max_length=4096, blank=True, default="")
    max_results = models.PositiveIntegerField(default=5)
    timeout_seconds = models.PositiveIntegerField(default=60)
    max_chart_megabytes = models.PositiveIntegerField(default=1200)
    max_unpack_megabytes = models.PositiveIntegerField(default=1500)
    # Where compiled grammar images go by default.
    grammar_image_dir = models.CharField(max_length=4096, blank=True, default="")
    # Where test suite runs (processed [incr tsdb()] profiles) are written.
    profiles_dir = models.CharField(max_length=4096, blank=True, default="")
    active_grammar = models.ForeignKey(
        "Grammar", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def image_dir(self) -> Path:
        if self.grammar_image_dir:
            return Path(self.grammar_image_dir).expanduser()
        return settings.IGDE_HOME / "grammars"

    def run_dir(self) -> Path:
        if self.profiles_dir:
            return Path(self.profiles_dir).expanduser()
        return settings.IGDE_HOME / "profiles"

    def to_dict(self):
        return {
            "aceRoot": self.ace_root,
            "maxResults": self.max_results,
            "timeoutSeconds": self.timeout_seconds,
            "maxChartMegabytes": self.max_chart_megabytes,
            "maxUnpackMegabytes": self.max_unpack_megabytes,
            "grammarImageDir": self.grammar_image_dir,
            "defaultGrammarImageDir": str(settings.IGDE_HOME / "grammars"),
            "profilesDir": self.profiles_dir,
            "defaultProfilesDir": str(settings.IGDE_HOME / "profiles"),
            "activeGrammar": self.active_grammar_id,
        }


class Grammar(models.Model):
    """A grammar on the user's machine that IGDE knows about.

    Either a source grammar (``config_path`` points at an ACE config.tdl and
    ``image_path`` is where IGDE compiles it to) or a precompiled grammar
    image (``config_path`` empty, ``image_path`` points at the .dat file).
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

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

    @property
    def is_source(self) -> bool:
        return bool(self.config_path)

    @property
    def root_dir(self) -> Path:
        """The directory to show in the grammar's file tree."""
        if self.config_path:
            cfg = Path(self.config_path)
            # DELPH-IN convention: <grammar>/ace/config.tdl
            if cfg.parent.name == "ace":
                return cfg.parent.parent
            return cfg.parent
        image = Path(self.image_path)
        # a precompiled image is often kept beside its grammar's directory
        # (e.g. erg.dat next to erg/)
        beside = image.parent / image.stem
        if (beside / "ace" / "config.tdl").is_file() or (beside / "config.tdl").is_file():
            return beside
        return image.parent

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
