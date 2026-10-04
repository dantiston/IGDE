"""End-to-end tests against a real ACE, using the tiniest grammar fixture.

Skipped unless ACE can be found: set IGDE_TEST_ACE_ROOT (or ACE_ROOT) to the
directory containing the ``ace`` binary, or put ``ace`` on $PATH.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from django.test import TransactionTestCase, override_settings

from core.models import AppSettings, Grammar
from core.processors.ace import find_executable
from core.processors.manager import manager

FIXTURES = Path(__file__).parent / "fixtures"


def _ace_root():
    for root in (os.environ.get("IGDE_TEST_ACE_ROOT"), os.environ.get("ACE_ROOT"), shutil.which("ace")):
        if root and find_executable(root):
            return root
    return None


ACE_ROOT = _ace_root()


def use_ace(test):
    """Point IGDE's ACE processor at ACE_ROOT."""
    pid = AppSettings.load().processor().id
    test.post(f"/api/processors/{pid}", {"location": ACE_ROOT}, method="put")


@unittest.skipUnless(ACE_ROOT, "ACE not found (set IGDE_TEST_ACE_ROOT)")
class AceIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        override = override_settings(IGDE_HOME=self.tmp / "home")
        override.enable()
        self.addCleanup(override.disable)
        (self.tmp / "home").mkdir()
        self.grammar_dir = self.tmp / "tiniest"
        shutil.copytree(FIXTURES / "tiniest", self.grammar_dir)
        manager.settings_changed()
        self.addCleanup(manager.settings_changed)
        use_ace(self)
        g = self.post("/api/grammars", {"configPath": str(self.grammar_dir), "compile": True})["grammar"]
        self.gid = g["id"]
        self.wait_for_compile()

    def post(self, url, data, method="post", status=200):
        r = getattr(self.client, method)(url, json.dumps(data), content_type="application/json")
        self.assertEqual(r.status_code, status, r.content[:500])
        return r.json()

    def wait_for_compile(self):
        deadline = time.time() + 120
        while time.time() < deadline:
            g = Grammar.objects.get(pk=self.gid)
            if g.compile_status != Grammar.COMPILE_RUNNING:
                self.assertEqual(g.compile_status, Grammar.COMPILE_OK, g.compile_log)
                return g
            time.sleep(0.1)
        self.fail("compilation did not finish")

    def test_compile_parse_generate(self):
        g = Grammar.objects.get(pk=self.gid)
        self.assertTrue(Path(g.image_path).is_file())
        self.assertIn("Compiled", g.compile_log)

        r = self.post("/api/parse", {"sentence": "n1 iv"})
        self.assertEqual(r["readings"], 1)
        res = r["results"][0]
        self.assertEqual(res["derivation"]["entity"], "subj-head")
        self.assertEqual(res["signature"], ["subj-head", "n1", "iv"])
        self.assertEqual([x["predicate"] for x in res["mrs"]["relations"]], ['"_n1_n_rel"', '"_iv_v_rel"'])

        self.assertEqual(self.post("/api/parse", {"sentence": "iv n1"})["readings"], 0)

        gen = self.post("/api/generate", {"mrs": res["simplemrs"]})
        self.assertEqual([x["surface"] for x in gen["results"]], ["N1 iv"])

        kinds = {p["kind"] for p in self.client.get("/api/processes").json()["processes"]}
        self.assertEqual(kinds, {"parser", "generator"})
        self.post("/api/processes/stop", {})
        self.assertEqual(self.client.get("/api/processes").json()["processes"], [])
        # processes restart on demand
        self.assertEqual(self.post("/api/parse", {"sentence": "n1 iv"})["readings"], 1)

    def test_recompile_after_edit(self):
        lexicon = self.grammar_dir / "lexicon.tdl"
        lexicon.write_text(
            lexicon.read_text() + '\nn2 := noun-lex & [ STEM < "n2" >, SYNSEM.LKEYS.KEYREL.PRED "_n2_n_rel" ].\n'
        )
        self.assertEqual(self.post("/api/parse", {"sentence": "n2 iv"})["readings"], 0)
        self.post(f"/api/grammars/{self.gid}/compile", {})
        self.wait_for_compile()
        self.assertEqual(self.post("/api/parse", {"sentence": "n2 iv"})["readings"], 1)

    def test_tfs_browsing(self):
        p = self.post("/api/tfs/parse", {"sentence": "n1 iv"})
        self.assertEqual(p["count"], 1)
        tree = p["trees"][0]
        self.assertEqual(tree["signature"], ["subj-head", "n1", "iv"])
        session = p["session"]

        n1 = tree["children"][0]
        node = self.post("/api/tfs/node", {"id": n1["id"], "session": session})
        self.assertEqual(node["avm"]["type"], "noun-lex")
        mrs = self.post("/api/tfs/node", {"id": tree["id"], "session": session, "what": "mrs"})
        self.assertEqual(mrs["avm"]["type"], "mrs")

        rule = self.post("/api/tfs/lookup", {"kind": "rule", "name": "subj-head"})
        self.assertEqual(rule["title"], "subj-head")
        self.assertEqual(rule["definition"]["path"], str(self.grammar_dir / "rules.tdl"))
        self.assertEqual(rule["definition"]["line"], 1)
        lex = self.post("/api/tfs/lookup", {"kind": "lex", "name": "iv"})
        self.assertEqual(lex["avm"]["type"], "intransitive-verb-lex")
        partial = self.post("/api/tfs/lookup", {"kind": "type", "name": "-lex"})
        self.assertIn("noun-lex", partial["matches"])
        self.assertEqual(self.post("/api/tfs/lookup", {"kind": "type", "name": "nonexistent"})["matches"], [])

        h = self.post("/api/tfs/hierarchy", {"type": "ref-ind"})
        names = [n["name"] for n in h["nodes"]]
        self.assertIn("*top*", names)
        self.assertIn("individual", names)

        # the n1 noun can fill the rule's subject slot...
        ok = self.post(
            "/api/tfs/unify",
            {"left": {"id": node["id"], "path": []}, "right": {"id": rule["id"], "path": ["ARGS", "FIRST"]}, "session": session},
        )
        self.assertTrue(ok["ok"], ok)
        self.assertIn("ARGS", [f for f, _ in ok["avm"]["features"]])
        # ...but not its head daughter, which must still want a subject
        bad = self.post(
            "/api/tfs/unify",
            {"left": {"id": node["id"], "path": []}, "right": {"id": rule["id"], "path": ["ARGS", "REST", "FIRST"]}, "session": session},
        )
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["failure"]["path"][:3], ["ARGS", "REST", "FIRST"])
        self.assertEqual(bad["failure"]["path"][-1], "SUBJ")

        stale = self.client.post(
            "/api/tfs/node", json.dumps({"id": n1["id"], "session": session + 1000}), content_type="application/json"
        )
        self.assertEqual(stale.status_code, 409)
        self.assertTrue(stale.json()["stale"])
        unknown = self.client.post(
            "/api/tfs/node", json.dumps({"id": 99999, "session": session}), content_type="application/json"
        )
        self.assertEqual(unknown.status_code, 502)

    def test_settings_change_restarts_processes(self):
        self.post("/api/parse", {"sentence": "n1 iv"})
        self.assertTrue(self.client.get("/api/processes").json()["processes"])
        self.post("/api/settings", {"maxResults": 2}, method="put")
        self.assertEqual(self.client.get("/api/processes").json()["processes"], [])
        self.assertEqual(AppSettings.load().max_results, 2)
