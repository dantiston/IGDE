"""API tests that don't need a real processor (a stub ``ace`` script stands in)."""

import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from core.models import AppSettings, Grammar, Processor
from core.processors.manager import manager

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
        brew = mock.patch("core.processors.ace.homebrew_prefixes", lambda: self.brew_prefixes)
        brew.start()
        self.addCleanup(brew.stop)
        os.environ.pop("ACE_ROOT", None)

    def call(self, method, url, data=None, **kw):
        fn = getattr(self.client, method.lower())
        if data is not None:
            return fn(url, json.dumps(data), content_type="application/json", **kw)
        return fn(url, **kw)

    def ace(self):
        """The ACE processor IGDE starts with, from the status endpoint."""
        return self.call("GET", "/api/status").json()["processor"]


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
        self.assertEqual(AppSettings.load().max_results, 3)

    def test_only_local_hosts_are_served(self):
        r = self.client.get("/api/status", HTTP_HOST="evil.example.com")
        self.assertEqual(r.status_code, 400)


class ProcessorTests(ApiTestCase):
    def check(self, location, backend="ace"):
        return self.call("POST", "/api/processors/check", {"backend": backend, "location": str(location)}).json()

    def test_unconfigured(self):
        data = self.call("GET", "/api/status").json()
        # IGDE starts with one processor per backend, found automatically
        self.assertEqual([(p["name"], p["backend"], p["location"], p["isDefault"]) for p in data["processors"]], [("ACE", "ace", "", True)])
        self.assertEqual(data["processor"]["id"], data["processors"][0]["id"])
        self.assertFalse(data["processor"]["status"]["ok"])
        self.assertIn("ACE_ROOT", data["processor"]["status"]["error"])
        backend = data["backends"][0]
        self.assertEqual((backend["key"], backend["locationLabel"]), ("ace", "ACE_ROOT"))
        self.assertEqual([o["key"] for o in backend["options"]], ["maxChartMegabytes", "maxUnpackMegabytes"])
        self.assertEqual(data["processor"]["options"], {"maxChartMegabytes": 1200, "maxUnpackMegabytes": 1500})

    def test_location_directory_binary_and_bin(self):
        make_fake_ace(self.tmp)
        (self.tmp / "prefix" / "bin").mkdir(parents=True)
        make_fake_ace(self.tmp / "prefix" / "bin", "0.9.31")
        for root, version in ((self.tmp, "0.9.34"), (self.tmp / "ace", "0.9.34"), (self.tmp / "prefix", "0.9.31")):
            r = self.check(root)
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["version"], version)

    def test_save_validates_location(self):
        pid = self.ace()["id"]
        r = self.call("PUT", f"/api/processors/{pid}", {"location": str(self.tmp / "missing")})
        self.assertEqual(r.status_code, 400)
        self.assertIn("No executable 'ace'", r.json()["error"])
        make_fake_ace(self.tmp)
        r = self.call("PUT", f"/api/processors/{pid}", {"location": str(self.tmp), "options": {"maxChartMegabytes": 3000}})
        self.assertEqual(r.status_code, 200, r.content)
        p = r.json()["processor"]
        self.assertEqual(p["status"]["source"], "settings")
        self.assertEqual(p["options"], {"maxChartMegabytes": 3000, "maxUnpackMegabytes": 1500})
        self.assertEqual(Processor.objects.get(pk=pid).options, {"maxChartMegabytes": 3000})
        self.assertEqual(self.call("PUT", "/api/settings", {"maxResults": 7}).status_code, 200)
        self.assertEqual(AppSettings.load().max_results, 7)

    def test_env_ace_root_and_path(self):
        make_fake_ace(self.tmp)
        with mock.patch.dict(os.environ, {"ACE_ROOT": str(self.tmp)}):
            manager.settings_changed()
            self.assertEqual(self.ace()["status"]["source"], "env")
        with mock.patch.dict(os.environ, {"PATH": str(self.tmp)}):
            manager.settings_changed()
            self.assertEqual(self.ace()["status"]["source"], "path")

    def test_homebrew(self):
        prefix = self.tmp / "homebrew"
        (prefix / "bin").mkdir(parents=True)
        (prefix / "opt" / "ace@0.9.31" / "bin").mkdir(parents=True)
        (prefix / "opt" / "ace@0.9.33" / "bin").mkdir(parents=True)
        make_fake_ace(prefix / "opt" / "ace@0.9.31" / "bin", "0.9.31")
        make_fake_ace(prefix / "opt" / "ace@0.9.33" / "bin", "0.9.33")
        self.brew_prefixes = [prefix]
        # versioned (keg-only) formulas are found, newest first
        st = self.ace()["status"]
        self.assertEqual((st["ok"], st["source"], st["version"]), (True, "homebrew", "0.9.33"))
        found = self.call("GET", "/api/processors/detect").json()["found"]
        self.assertEqual([(f["backend"], f["version"]) for f in found], [("ace", "0.9.33"), ("ace", "0.9.31")])
        # the current formula links bin/ace and wins
        make_fake_ace(prefix / "bin", "0.9.34")
        manager.settings_changed()
        self.assertEqual(self.ace()["status"]["version"], "0.9.34")

    def test_missing_ace_is_noticed_once_installed(self):
        self.assertFalse(self.ace()["status"]["ok"])
        self.brew_prefixes = [self.tmp]
        (self.tmp / "bin").mkdir()
        make_fake_ace(self.tmp / "bin")
        self.assertTrue(self.ace()["status"]["ok"])

    def test_rejects_bad_values(self):
        pid = self.ace()["id"]
        self.assertEqual(self.call("PUT", "/api/settings", {"maxResults": 0}).status_code, 400)
        self.assertEqual(self.call("PUT", f"/api/processors/{pid}", {"location": "relative/path"}).status_code, 400)
        r = self.call("PUT", f"/api/processors/{pid}", {"options": {"maxChartMegabytes": 1}})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Chart memory", r.json()["error"])
        r = self.call("POST", "/api/processors", {"backend": "nope"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Unknown processor type", r.json()["error"])
        self.assertEqual(self.call("PUT", "/api/processors/999", {}).status_code, 404)

    def test_not_ace(self):
        exe = self.tmp / "ace"
        exe.write_text("#!/bin/sh\necho hello\n")
        exe.chmod(0o755)
        r = self.check(exe)
        self.assertFalse(r["ok"])
        self.assertIn("does not look like ACE", r["error"])

    def test_several_processors(self):
        first = self.ace()
        (self.tmp / "old").mkdir()
        make_fake_ace(self.tmp / "old", "0.9.31")
        make_fake_ace(self.tmp, "0.9.34")
        self.call("PUT", f"/api/processors/{first['id']}", {"location": str(self.tmp)})
        r = self.call("POST", "/api/processors", {"backend": "ace", "name": "ACE 0.9.31", "location": str(self.tmp / "old")})
        old = r.json()["processor"]
        self.assertEqual((old["name"], old["isDefault"], old["status"]["version"]), ("ACE 0.9.31", False, "0.9.31"))

        # a grammar can use a processor other than the default
        image = self.tmp / "g.dat"
        image.write_bytes(b"\x00")
        g = self.call("POST", "/api/grammars", {"imagePath": str(image)}).json()["grammar"]
        self.assertIsNone(g["processor"])
        self.assertEqual(self.ace()["status"]["version"], "0.9.34")
        g = self.call("PATCH", f"/api/grammars/{g['id']}", {"processor": old["id"]}).json()["grammar"]
        self.assertEqual(g["processor"], old["id"])
        # the status reports the active grammar's processor
        self.assertEqual(self.ace()["status"]["version"], "0.9.31")

        # change the default
        self.call("PUT", "/api/settings", {"defaultProcessor": old["id"]})
        data = self.call("GET", "/api/status").json()
        self.assertEqual({p["name"]: p["isDefault"] for p in data["processors"]}, {"ACE": False, "ACE 0.9.31": True})

        # removing a processor: its grammars fall back to the default
        self.call("PUT", "/api/settings", {"defaultProcessor": first["id"]})
        self.assertEqual(self.call("DELETE", f"/api/processors/{old['id']}").status_code, 200)
        self.assertIsNone(Grammar.objects.get(pk=g["id"]).processor)
        self.assertEqual(self.ace()["status"]["version"], "0.9.34")


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
        self.assertEqual(AppSettings.load().active_grammar_id, g["id"])
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
        self.assertEqual(AppSettings.load().active_grammar_id, other.id)
        self.assertEqual(self.call("DELETE", f"/api/grammars/{other.id}").status_code, 200)
        self.assertIsNone(AppSettings.load().active_grammar_id)
        self.assertTrue(image.exists())  # removing a grammar never deletes files
        self.assertEqual(self.call("POST", "/api/grammars", {"imagePath": str(self.tmp / "nope.dat")}).status_code, 404)

    def test_processing_needs_a_processor_and_grammar(self):
        self.assertEqual(self.call("POST", "/api/parse", {"sentence": "n1 iv"}).status_code, 409)
        g = Grammar.objects.create(name="t", image_path=str(self.tmp / "missing.dat"))
        r = self.call("POST", "/api/parse", {"sentence": "n1 iv", "grammar": g.id})
        self.assertEqual(r.status_code, 503)
        self.assertTrue(r.json()["processor"])
        r = self.call("POST", "/api/generate", {"mrs": "[ not an mrs", "grammar": g.id})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Could not read the MRS", r.json()["error"])
