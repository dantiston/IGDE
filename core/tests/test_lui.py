from django.test import SimpleTestCase

from core.processors.lui import LuiParseError, parse_avm, parse_messages

# Recorded from ``ace -l --lui-fd`` (with the tiniest grammar and the ERG);
# \f is the LUI message terminator.
PARAMS = (
    "parameter list-type list\n\f"
    "parameter empty-list-type null\n\f"
    "parameter avm-collapsed-types [u i p e x h]\n\f"
)
TREE = (
    'group 1 "n1 iv"\n'
    'tree 1 #T[1 "S" nil 8 subj-head #T[2 "N" "n1" 3 n1] #T[3 "V" "iv" 4 iv]] "n1 iv"\f\n'
)
AVM = (
    'avm 4 #D[noun-lex ARGS: #D[list] STEM: #D[cons FIRST: #D["n1"] REST: #D[null] ] '
    "SYNSEM: #D[lex-synsem LKEYS: #D[lexkeys KEYREL: <1>= #D[noun-relation "
    'PRED: #D["_n1_n_rel"] LBL: <2>= #D[handle] ] ] CONT: #D[mrs HOOK: #D[hook LTOP: <2> ] '
    'RELS: #D[cons FIRST: <1> REST: #D[null] ] ] ] ] "n1"\f\n'
)
HIERARCHY = (
    'hierarchy 1 "ref-ind" [\n'
    '#H["*top*" [] [ 1] ]\n'
    '#H["avm" [ 0] [ 2] ]\n'
    '#H["ref-ind" [ 1] [] ]\n'
    "]"
)
DGLIST = (
    'text 3 #X[ 0 "noun-lex" newline 1 "verb-lex" newline 2 "... and 3 more" newline] '
    '#M["Display AVM" "daglist %d" 0 1] "matching types"]\n'
)
FAILURE = (
    'avm 17 #D[mrs TOP: <0>=#D[h] INDEX: <2>=#D[e]] "unification failure" '
    "[ #U[type 1 [SYNSEM LOCAL CAT VAL SPR FIRST OPT] - + -1] ]\f\n"
)


class LuiParserTests(SimpleTestCase):
    def test_parameters_and_trees(self):
        msgs = parse_messages(PARAMS + TREE)
        self.assertEqual([m["kind"] for m in msgs], ["parameter"] * 3 + ["group", "tree"])
        self.assertEqual(msgs[0], {"kind": "parameter", "name": "list-type", "value": "list"})
        self.assertEqual(msgs[3]["count"], 1)
        tree = msgs[4]["tree"]
        self.assertEqual(msgs[4]["chart"], 1)
        self.assertEqual((tree["id"], tree["label"], tree["eid"], tree["entity"]), (1, "S", 8, "subj-head"))
        self.assertNotIn("form", tree)
        self.assertEqual([(c["entity"], c["form"]) for c in tree["children"]], [("n1", "n1"), ("iv", "iv")])

    def test_avm_with_reentrancies_and_strings(self):
        (msg,) = parse_messages(AVM)
        self.assertEqual((msg["id"], msg["title"]), (4, "n1"))
        avm = msg["avm"]
        self.assertEqual(avm["type"], "noun-lex")
        feats = dict(avm["features"])
        self.assertEqual(dict(feats["STEM"]["features"])["FIRST"]["type"], '"n1"')
        keyrel = dict(dict(feats["SYNSEM"]["features"])["LKEYS"]["features"])["KEYREL"]
        self.assertEqual((keyrel["type"], keyrel["tag"]), ("noun-relation", 1))
        cont = dict(dict(feats["SYNSEM"]["features"])["CONT"]["features"])
        self.assertEqual(dict(cont["HOOK"]["features"])["LTOP"], {"ref": 2})
        self.assertEqual(dict(cont["RELS"]["features"])["FIRST"], {"ref": 1})

    def test_hierarchy_followed_by_another_message(self):
        msgs = parse_messages(HIERARCHY + AVM)
        self.assertEqual([m["kind"] for m in msgs], ["hierarchy", "avm"])
        self.assertEqual(
            msgs[0]["nodes"],
            [
                {"name": "*top*", "parents": [], "children": [1]},
                {"name": "avm", "parents": [0], "children": [2]},
                {"name": "ref-ind", "parents": [1], "children": []},
            ],
        )

    def test_dag_list_text_with_stray_bracket(self):
        (msg,) = parse_messages(DGLIST)
        self.assertEqual(msg["title"], "matching types")
        self.assertEqual(
            msg["entries"],
            [
                {"index": 0, "text": "noun-lex"},
                {"index": 1, "text": "verb-lex"},
                {"index": 2, "text": "... and 3 more"},
            ],
        )

    def test_unification_failure(self):
        (msg,) = parse_messages(FAILURE)
        self.assertEqual(msg["avm"]["features"][0], ["TOP", {"type": "h", "tag": 0, "features": []}])
        self.assertEqual(
            msg["failure"],
            {"kind": "type", "path": ["SYNSEM", "LOCAL", "CAT", "VAL", "SPR", "FIRST", "OPT"], "types": ["-", "+"]},
        )

    def test_leaked_stdout_before_dag_is_skipped(self):
        leaked = AVM.replace("avm 4 ", 'avm 4 sign -- defined at ./t.tdl:4\navm & [ "x" ]\n')
        (msg,) = parse_messages(leaked)
        self.assertEqual(msg["avm"]["type"], "noun-lex")
        self.assertIn("defined at", msg["leaked"])

    def test_unknown_lines_and_close_messages(self):
        msgs = parse_messages("garbage line\nclose 2\n\f" + TREE)
        self.assertEqual([m["kind"] for m in msgs], ["close", "group", "tree"])

    def test_escaped_strings(self):
        avm = parse_avm('#D[token +FORM: #D["say \\"hi\\""] ]')
        self.assertEqual(avm["features"][0][1]["type"], '"say "hi""')

    def test_errors(self):
        with self.assertRaises(LuiParseError):
            parse_messages('avm 3 "no dag here"\n')
        with self.assertRaises(LuiParseError):
            parse_avm("#D[foo BAR: ")
