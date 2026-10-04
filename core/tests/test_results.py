from django.test import SimpleTestCase

from core.ace.results import entity_signature, format_simplemrs, parse_labelled_tree, raw_predicates, semantics
from delphin.codecs import simplemrs

TINIEST_MRS = (
    '[ LTOP: handle0 INDEX: e2 RELS: < [ "_n1_n_rel"<-1:-1> LBL: h3 ARG0: x4 ]  '
    '[ "_iv_v_rel"<-1:-1> LBL: h1 ARG0: e2 ARG1: x5 ] > HCONS: < handle0 qeq h1 > ]'
)
ERG_MRS = (
    "[ LTOP: h0 INDEX: e2 [ e SF: prop TENSE: pres ] RELS: < "
    "[ _the_q<0:3> LBL: h4 ARG0: x3 [ x PERS: 3 NUM: sg ] RSTR: h5 BODY: h6 ]  "
    "[ _dog_n_1<4:7> LBL: h7 ARG0: x3 ]  [ _bark_v_1<8:13> LBL: h1 ARG0: e2 ARG1: x3 ] > "
    "HCONS: < h0 qeq h1 h5 qeq h7 > ICONS: < > ]"
)


class ResultsTests(SimpleTestCase):
    def test_labelled_tree(self):
        tree = parse_labelled_tree('("S" ("NP" ("DET" ("the")) ("N" ("dog"))) ("VP" ("V" ("barks"))))')
        self.assertEqual(tree["label"], "S")
        np, vp = tree["children"]
        self.assertEqual(np["children"][0], {"label": "DET", "children": [{"form": "the"}]})
        self.assertEqual(vp["children"][0]["children"], [{"form": "barks"}])
        self.assertIsNone(parse_labelled_tree(None))

    def test_raw_predicates_preserve_grammar_strings(self):
        self.assertEqual(raw_predicates(TINIEST_MRS), ['"_n1_n_rel"', '"_iv_v_rel"'])
        # variable property brackets are not EPs
        self.assertEqual(raw_predicates(ERG_MRS), ["_the_q", "_dog_n_1", "_bark_v_1"])

    def test_format_simplemrs_only_changes_whitespace(self):
        for raw in (TINIEST_MRS, ERG_MRS):
            out = format_simplemrs(raw)
            self.assertEqual(out.split(), raw.split())
            self.assertIn("\n  RELS: < [", out)
        self.assertEqual(format_simplemrs(ERG_MRS).count("\n"), 6)

    def test_semantics_uses_the_grammars_predicates(self):
        sem = semantics(simplemrs.decode(TINIEST_MRS), TINIEST_MRS)
        self.assertEqual([r["predicate"] for r in sem["mrs"]["relations"]], ['"_n1_n_rel"', '"_iv_v_rel"'])
        self.assertIn('"_iv_v_rel"', sem["simplemrs"])
        sem = semantics(simplemrs.decode(ERG_MRS), ERG_MRS)
        self.assertEqual(sorted(n["predicate"] for n in sem["dmrs"]["nodes"]), ["_bark_v_1", "_dog_n_1", "_the_q"])
        self.assertIn("_bark_v_1", sem["eds"])

    def test_entity_signature(self):
        d = {"entity": "a", "daughters": [{"entity": "b"}, {"entity": "c", "daughters": [{"entity": "d"}]}]}
        self.assertEqual(entity_signature(d), ["a", "b", "c", "d"])
