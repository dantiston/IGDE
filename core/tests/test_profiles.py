"""Test suites ([incr tsdb()] profiles): API tests, plus runs with a real ACE."""

import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from delphin import itsdb
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from core import profiles
from core.models import Grammar, Profile
from core.processors.manager import manager

from .test_ace_integration import ACE_ROOT, FIXTURES, use_ace


class ItemLinesTests(SimpleTestCase):
    def test_parse_item_lines(self):
        items = profiles.parse_item_lines("The dog barks.\n\n*Dog the barks.\n; comment\n# also\n  *  Barks dog.  \n")
        self.assertEqual(
            items,
            [{"input": "The dog barks.", "wf": 1}, {"input": "Dog the barks.", "wf": 0}, {"input": "Barks dog.", "wf": 0}],
        )


class ProfileApiTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        o = override_settings(IGDE_HOME=self.tmp / "home")
        o.enable()
        self.addCleanup(o.disable)

    def call(self, method, url, data=None, status=200):
        fn = getattr(self.client, method)
        r = fn(url, json.dumps(data), content_type="application/json") if data is not None else fn(url)
        self.assertEqual(r.status_code, status, r.content[:400])
        return r.json()

    def test_create_edit_and_read_a_suite(self):
        p = self.call("post", "/api/profiles", {"action": "create", "name": "My suite", "text": "n1 iv\n*iv n1"})["profile"]
        self.assertEqual(p["path"], str(self.tmp / "home" / "testsuites" / "My-suite"))
        self.assertEqual((p["stats"]["items"], p["stats"]["illformed"], p["stats"]["processed"]), (2, 1, 0))
        ts = itsdb.TestSuite(p["path"])
        item = ts["item"][1]
        self.assertEqual((item["i-input"], item["i-wf"], item["i-length"], item["i-origin"]), ("iv n1", 0, 2, "IGDE"))

        detail = self.call("get", f"/api/profiles/{p['id']}")["profile"]
        self.assertEqual([(r["id"], r["input"], r["wf"]) for r in detail["rows"]], [(1, "n1 iv", 1), (2, "iv n1", 0)])

        # edit one, delete one, add one; other columns of kept items survive
        rows = self.call(
            "put",
            f"/api/profiles/{p['id']}/items",
            {"items": [{"id": 1, "input": "n1 iv", "wf": 1, "comment": "basic"}, {"id": None, "input": "n2 iv", "wf": 1}]},
        )["profile"]["rows"]
        self.assertEqual([(r["id"], r["input"], r["comment"]) for r in rows], [(1, "n1 iv", "basic"), (3, "n2 iv", "")])
        self.assertEqual(itsdb.TestSuite(p["path"])["item"][0]["i-origin"], "IGDE")

        self.call("put", f"/api/profiles/{p['id']}/items", {"items": [{"input": "  "}]}, status=400)
        self.call("post", "/api/profiles", {"action": "create", "name": "My suite", "text": "x"}, status=400)  # exists
        self.call("post", "/api/profiles", {"action": "create", "name": "Empty", "text": "; nothing"}, status=400)

    def test_add_existing_profile_and_remove(self):
        made = self.call("post", "/api/profiles", {"action": "create", "name": "elsewhere", "text": "n1 iv", "directory": str(self.tmp)})
        path = made["profile"]["path"]
        self.assertEqual(path, str(self.tmp / "elsewhere"))
        added = self.call("post", "/api/profiles", {"action": "add", "path": path, "name": "again"})["profile"]
        self.assertEqual((added["name"], added["stats"]["items"]), ("again", 1))
        self.call("post", "/api/profiles", {"action": "add", "path": str(self.tmp)}, status=400)  # not a profile
        # removing an added profile never deletes it, and files can only be
        # deleted for runs IGDE made
        self.call("delete", f"/api/profiles/{added['id']}?files=1", status=400)
        self.call("delete", f"/api/profiles/{added['id']}")
        self.assertTrue(Path(path, "relations").exists())
        self.call("get", f"/api/profiles/{added['id']}", status=404)

    def test_run_needs_a_grammar(self):
        p = self.call("post", "/api/profiles", {"action": "create", "name": "s", "text": "n1 iv"})["profile"]
        self.call("post", f"/api/profiles/{p['id']}/run", {}, status=409)


@unittest.skipUnless(ACE_ROOT, "ACE not found (set IGDE_TEST_ACE_ROOT)")
class ProfileRunTests(TransactionTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        o = override_settings(IGDE_HOME=self.tmp / "home")
        o.enable()
        self.addCleanup(o.disable)
        (self.tmp / "home").mkdir()
        manager.settings_changed()
        self.addCleanup(manager.settings_changed)
        self.grammar_dir = self.tmp / "tiniest"
        shutil.copytree(FIXTURES / "tiniest", self.grammar_dir)
        use_ace(self)
        self.gid = self.post("/api/grammars", {"configPath": str(self.grammar_dir), "compile": True})["grammar"]["id"]
        self.wait_compiled()

    def post(self, url, data, method="post", status=200):
        r = getattr(self.client, method)(url, json.dumps(data), content_type="application/json")
        self.assertEqual(r.status_code, status, r.content[:400])
        return r.json()

    def get(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, r.content[:400])
        return r.json()

    def wait_compiled(self):
        for _ in range(600):
            g = Grammar.objects.get(pk=self.gid)
            if g.compile_status != Grammar.COMPILE_RUNNING:
                self.assertEqual(g.compile_status, Grammar.COMPILE_OK, g.compile_log)
                return
            time.sleep(0.1)
        self.fail("compile timed out")

    def run_suite(self, sid):
        run = self.post(f"/api/profiles/{sid}/run", {})["profile"]
        for _ in range(600):
            p = self.get(f"/api/profiles/{run['id']}")["profile"]
            if p["runStatus"] != "running":
                self.assertEqual(p["runStatus"], "ok", p["runLog"])
                return p
            time.sleep(0.1)
        self.fail("run timed out")

    def test_run_inspect_and_compare(self):
        suite = self.post("/api/profiles", {"action": "create", "name": "tiny", "text": "n1 iv\niv n1\nn2 iv\n*n1 n1"})["profile"]
        run1 = self.run_suite(suite["id"])
        self.assertTrue(run1["owned"])
        self.assertTrue(run1["path"].startswith(str(self.tmp / "home" / "profiles" / "tiny")))
        s = run1["stats"]
        self.assertEqual((s["items"], s["processed"], s["parsed"]), (4, 4, 1))
        self.assertAlmostEqual(s["coverage"], 1 / 3, places=3)
        self.assertEqual(s["overgeneration"], 0)
        self.assertIn("ACE", s["runInfo"]["application"])
        rows = {r["input"]: r for r in run1["rows"]}
        self.assertEqual((rows["n1 iv"]["readings"], rows["iv n1"]["readings"]), (1, 0))

        item = self.get(f"/api/profiles/{run1['id']}/items/1")
        self.assertEqual(item["results"][0]["derivation"]["entity"], "subj-head")
        self.assertEqual([r["predicate"] for r in item["results"][0]["mrs"]["relations"]], ['"_n1_n_rel"', '"_iv_v_rel"'])

        # add n2, and change what n1 means
        lexicon = self.grammar_dir / "lexicon.tdl"
        lexicon.write_text(
            lexicon.read_text().replace('"_n1_n_rel"', '"_n1_new_n_rel"')
            + '\nn2 := noun-lex & [ STEM < "n2" >, SYNSEM.LKEYS.KEYREL.PRED "_n2_n_rel" ].\n'
        )
        self.post(f"/api/grammars/{self.gid}/compile", {})
        self.wait_compiled()
        run2 = self.run_suite(suite["id"])
        self.assertAlmostEqual(run2["stats"]["coverage"], 2 / 3, places=3)

        cmp = self.get(f"/api/profiles/{run2['id']}/compare/{run1['id']}")
        self.assertNotEqual(run1["path"], run2["path"])
        status = {k: v["status"] for k, v in cmp["items"].items()}
        self.assertEqual(status, {"1": "changed", "2": "same", "3": "gained", "4": "same"})
        self.assertEqual(self.get(f"/api/profiles/{run1['id']}/compare/{run2['id']}")["items"]["3"]["status"], "lost")
        self.assertEqual(self.get(f"/api/profiles/{run2['id']}/compare/{run2['id']}")["counts"], {"same": 4})

        # runs IGDE made can be deleted with their files
        r = self.client.delete(f"/api/profiles/{run1['id']}?files=1")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Path(run1["path"]).exists())
        self.assertFalse(Profile.objects.filter(pk=run1["id"]).exists())

    def test_cancel(self):
        many = "\n".join(["n1 iv"] * 3000)
        suite = self.post("/api/profiles", {"action": "create", "name": "many", "text": many})["profile"]
        run = self.post(f"/api/profiles/{suite['id']}/run", {})["profile"]
        self.post(f"/api/profiles/{run['id']}/cancel", {})
        for _ in range(600):
            p = self.get(f"/api/profiles/{run['id']}")["profile"]
            if p["runStatus"] != "running":
                break
            time.sleep(0.1)
        self.assertIn(p["runStatus"], ("cancelled", "ok"))  # a fast machine may finish first
        if p["runStatus"] == "cancelled":
            self.assertIn("Cancelled after", p["runLog"])
