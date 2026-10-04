"""API tests that don't need a real ACE (a stub ``ace`` script stands in)."""

import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from core.ace.manager import manager
from core.models import AceConfig, Grammar

FIXTURES = Path(__file__).parent / "fixtures"


def make_fake_ace(directory: Path, version="0.9.34") -> Path:
    exe = directory / "ace"
    exe.write_text(f'#!/bin/sh\necho "ACE version {version}"\n')
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


class ApiTestCase(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        override = override_settings(IGDE_HOME=self.tmp / "home")
        override.enable()
        self.addCleanup(override.disable)
        (self.tmp / "home").mkdir()
        manager.settings_changed()
        self.addCleanup(manager.settings_changed)
        env = mock.patch.dict(os.environ, {"PATH": "/nonexistent"})
        env.start()
        self.addCleanup(env.stop)
        # don't find a real Homebrew ACE on the machine running the tests
        self.brew_prefixes = []
        brew = mock.patch("core.ace.environment.homebrew_prefixes", lambda: self.brew_prefixes)
        brew.start()
        self.addCleanup(brew.stop)
        os.environ.pop("ACE_ROOT", None)

    def call(self, method, url, data=None, **kw):
        fn = getattr(self.client, method.lower())
        if data is not None:
            return fn(url, json.dumps(data), content_type="application/json", **kw)
        return fn(url, **kw)


class CsrfTests(ApiTestCase):
    def test_mutations_require_csrf_token(self):
        client = self.client_class(enforce_csrf_checks=True)
        r = client.put("/api/settings", json.dumps({"maxResults": 3}), content_type="application/json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("CSRF", r.json()["error"])
        # the status endpoint hands out the cookie; with the header it works
        client.get("/api/status")
        token = client.cookies["csrftoken"].value
        r = client.put(
            "/api/settings", json.dumps({"maxResults": 3}), content_type="application/json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(AceConfig.load().max_results, 3)

    def test_only_local_hosts_are_served(self):
        r = self.client.get("/api/status", HTTP_HOST="evil.example.com")
        self.assertEqual(r.status_code, 400)


class SettingsTests(ApiTestCase):
    def test_unconfigured(self):
        data = self.call("GET", "/api/status").json()
        self.assertFalse(data["ace"]["ok"])
        self.assertIn("ACE_ROOT", data["ace"]["error"])

    def test_ace_root_directory_binary_and_bin(self):
        make_fake_ace(self.tmp)
        (self.tmp / "prefix" / "bin").mkdir(parents=True)
        make_fake_ace(self.tmp / "prefix" / "bin", "0.9.31")
        for root, version in ((self.tmp, "0.9.34"), (self.tmp / "ace", "0.9.34"), (self.tmp / "prefix", "0.9.31")):
            r = self.call("POST", "/api/settings/test-ace", {"aceRoot": str(root)}).json()
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["version"], version)

    def test_save_validates_ace_root(self):
        r = self.call("PUT", "/api/settings", {"aceRoot": str(self.tmp / "missing")})
        self.assertEqual(r.status_code, 400)
        self.assertIn("No executable 'ace'", r.json()["error"])
        make_fake_ace(self.tmp)
        r = self.call("PUT", "/api/settings", {"aceRoot": str(self.tmp), "maxResults": 7})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["ace"]["source"], "settings")
        self.assertEqual(AceConfig.load().max_results, 7)

    def test_env_ace_root_and_path(self):
        make_fake_ace(self.tmp)
        with mock.patch.dict(os.environ, {"ACE_ROOT": str(self.tmp)}):
            manager.settings_changed()
            self.assertEqual(self.call("GET", "/api/status").json()["ace"]["source"], "env")
        with mock.patch.dict(os.environ, {"PATH": str(self.tmp)}):
            manager.settings_changed()
            self.assertEqual(self.call("GET", "/api/status").json()["ace"]["source"], "path")

    def test_homebrew(self):
        prefix = self.tmp / "homebrew"
        (prefix / "bin").mkdir(parents=True)
        (prefix / "opt" / "ace@0.9.31" / "bin").mkdir(parents=True)
        (prefix / "opt" / "ace@0.9.33" / "bin").mkdir(parents=True)
        make_fake_ace(prefix / "opt" / "ace@0.9.31" / "bin", "0.9.31")
        make_fake_ace(prefix / "opt" / "ace@0.9.33" / "bin", "0.9.33")
        self.brew_prefixes = [prefix]
        # versioned (keg-only) formulas are found, newest first
        st = self.call("GET", "/api/status").json()["ace"]
        self.assertEqual((st["ok"], st["source"], st["version"]), (True, "homebrew", "0.9.33"))
        found = self.call("GET", "/api/settings/detect-ace").json()["found"]
        self.assertEqual([f["version"] for f in found], ["0.9.33", "0.9.31"])
        # the current formula links bin/ace and wins
        make_fake_ace(prefix / "bin", "0.9.34")
        manager.settings_changed()
        self.assertEqual(self.call("GET", "/api/status").json()["ace"]["version"], "0.9.34")

    def test_missing_ace_is_noticed_once_installed(self):
        self.assertFalse(self.call("GET", "/api/status").json()["ace"]["ok"])
        self.brew_prefixes = [self.tmp]
        (self.tmp / "bin").mkdir()
        make_fake_ace(self.tmp / "bin")
        self.assertTrue(self.call("GET", "/api/status").json()["ace"]["ok"])

    def test_rejects_bad_values(self):
        self.assertEqual(self.call("PUT", "/api/settings", {"maxResults": 0}).status_code, 400)
        self.assertEqual(self.call("PUT", "/api/settings", {"aceRoot": "relative/path"}).status_code, 400)

    def test_not_ace(self):
        exe = self.tmp / "ace"
        exe.write_text("#!/bin/sh\necho hello\n")
        exe.chmod(0o755)
        r = self.call("POST", "/api/settings/test-ace", {"aceRoot": str(exe)}).json()
        self.assertFalse(r["ok"])
        self.assertIn("does not look like ACE", r["error"])


class FilesystemTests(ApiTestCase):
    def test_list_with_grammar_hints(self):
        g = self.tmp / "mygrammar"
        shutil.copytree(FIXTURES / "tiniest", g)
        (self.tmp / "image.dat").write_bytes(b"\x00\x01")
        (self.tmp / ".hidden").write_text("x")
        data = self.call("GET", f"/api/fs/list?path={self.tmp}").json()
        names = {e["name"]: e for e in data["entries"]}
        self.assertEqual(names["mygrammar"]["hint"], "grammar-dir")
        self.assertEqual(names["image.dat"]["hint"], "image")
        self.assertNotIn(".hidden", names)
        self.assertEqual(data["parent"], str(self.tmp.parent))
        data = self.call("GET", f"/api/fs/list?path={self.tmp}&hidden=1").json()
        self.assertIn(".hidden", {e["name"] for e in data["entries"]})
        inner = self.call("GET", f"/api/fs/list?path={g}").json()
        self.assertEqual({e["name"]: e["hint"] for e in inner["entries"]}["config.tdl"], "config")

    def test_list_errors(self):
        self.assertEqual(self.call("GET", f"/api/fs/list?path={self.tmp}/nope").status_code, 404)
        self.assertEqual(self.call("GET", "/api/fs/list?path=relative").status_code, 400)

    def test_read_and_write(self):
        f = self.tmp / "lexicon.tdl"
        f.write_text("a := b.\n")
        data = self.call("GET", f"/api/fs/file?path={f}").json()
        self.assertEqual(data["content"], "a := b.\n")
        r = self.call("PUT", "/api/fs/file", {"path": str(f), "content": "c := d.\n", "expectedMtime": data["mtime"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(f.read_text(), "c := d.\n")
        # stale mtime -> conflict, unless forced
        r = self.call("PUT", "/api/fs/file", {"path": str(f), "content": "x", "expectedMtime": data["mtime"] - 100})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(f.read_text(), "c := d.\n")
        r = self.call("PUT", "/api/fs/file", {"path": str(f), "content": "x"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(f.read_text(), "x")
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["home", "lexicon.tdl"])

    def test_binary_files_are_not_opened(self):
        f = self.tmp / "grammar.dat"
        f.write_bytes(b"\x00\x01\x02")
        self.assertEqual(self.call("GET", f"/api/fs/file?path={f}").status_code, 415)


class GrammarTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.grammar_dir = self.tmp / "tiniest"
        shutil.copytree(FIXTURES / "tiniest", self.grammar_dir)

    def test_detect(self):
        r = self.call("GET", f"/api/fs/detect-grammar?path={self.grammar_dir}").json()
        self.assertEqual(r["kind"], "source")
        self.assertEqual(r["configPath"], str(self.grammar_dir / "config.tdl"))
        self.assertEqual(r["grammarTop"], "definition.tdl")
        bad = self.tmp / "other.tdl"
        bad.write_text("a := b.")
        self.assertEqual(self.call("GET", f"/api/fs/detect-grammar?path={bad}").status_code, 400)

    def test_register_source_grammar(self):
        r = self.call("POST", "/api/grammars", {"configPath": str(self.grammar_dir / "config.tdl")})
        self.assertEqual(r.status_code, 200, r.content)
        g = r.json()["grammar"]
        self.assertEqual((g["name"], g["kind"], g["compileStatus"]), ("tiniest", "source", "idle"))
        self.assertEqual(g["imagePath"], str(self.tmp / "home" / "grammars" / "tiniest.dat"))
        self.assertEqual(g["rootDir"], str(self.grammar_dir))
        # the first grammar becomes the active one
        self.assertEqual(AceConfig.load().active_grammar_id, g["id"])
        # a second registration of the same grammar gets its own image
        g2 = self.call("POST", "/api/grammars", {"configPath": str(self.grammar_dir)}).json()["grammar"]
        self.assertTrue(g2["imagePath"].endswith("tiniest-2.dat"))
        files = self.call("GET", f"/api/grammars/{g['id']}/files").json()["files"]
        self.assertIn("lexicon.tdl", {f["rel"] for f in files})

    def test_register_image_and_activate_and_remove(self):
        image = self.tmp / "erg.dat"
        image.write_bytes(b"\x00")
        g = self.call("POST", "/api/grammars", {"imagePath": str(image)}).json()["grammar"]
        self.assertEqual((g["name"], g["kind"]), ("erg", "image"))
        self.assertEqual(self.call("POST", f"/api/grammars/{g['id']}/compile", {}).status_code, 503)
        other = Grammar.objects.create(name="x", image_path=str(image))
        self.call("POST", f"/api/grammars/{other.id}/activate", {})
        self.assertEqual(AceConfig.load().active_grammar_id, other.id)
        self.assertEqual(self.call("DELETE", f"/api/grammars/{other.id}").status_code, 200)
        self.assertIsNone(AceConfig.load().active_grammar_id)
        self.assertTrue(image.exists())  # removing a grammar never deletes files
        self.assertEqual(self.call("POST", "/api/grammars", {"imagePath": str(self.tmp / "nope.dat")}).status_code, 404)

    def test_processing_needs_ace_and_grammar(self):
        self.assertEqual(self.call("POST", "/api/parse", {"sentence": "n1 iv"}).status_code, 409)
        g = Grammar.objects.create(name="t", image_path=str(self.tmp / "missing.dat"))
        r = self.call("POST", "/api/parse", {"sentence": "n1 iv", "grammar": g.id})
        self.assertEqual(r.status_code, 503)
        self.assertTrue(r.json()["ace"])
        r = self.call("POST", "/api/generate", {"mrs": "[ not an mrs", "grammar": g.id})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Could not read the MRS", r.json()["error"])
