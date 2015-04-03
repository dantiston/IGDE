from django.test import TestCase

from delphin.interfaces import lui

from delphin.derivation import Derivation
from delphin.mrs import Xmrs

from .models import (IgdeDerivation, IgdeXmrs,
                     IgdeHandleConstraint, IgdeElementaryPredication)


class IgdeViewsTests(TestCase):
    
    def testParse(self):
        """
        Test that the parse method
        """
        pass


class IgdeModelsTests(TestCase):

    def setUp(self):
        terminal_text = "#T[1 \"LABEL\" \"TOKEN\" 2 RULE_NAME]"
        unary_text = "#T[9 \"LABEL\" nil 93 RULE_NAME #T[10 \"LABEL2\" \"TOKEN\" 39 RULE_NAME2]]"
        binary_text = "#T[9 \"LABEL\" nil 93 RULE_NAME #T[10 \"LABEL2\" \"TOKEN\" 39 RULE_NAME2] #T[11 \"LABEL3\" \"TOKEN2\" 240 RULE_NAME3]]"
        self.terminal_derivation = lui.load_derivations(terminal_text)[0]
        self.unary_derivation = lui.load_derivations(unary_text)[0]
        self.binary_derivation = lui.load_derivations(binary_text)[0]

        mrs_text = '''avm 20 #D[mrs TOP: <0>=#D[h] INDEX: <2>=#D[e SF: "prop" TENSE: "pres" MOOD: "indicative" PROG: "-" PERF: "-"] RELS: #D[*cons* FIRST: #D[pron_rel LBL: <4>=#D[h] ARG0: <3>=#D[x PERS: "1" NUM: "sg" PRONTYPE: "std_pron"]] REST: #D[*cons* FIRST: #D[pronoun_q_rel LBL: <5>=#D[h] ARG0: <3>=#D[x PERS: "1" NUM: "sg" PRONTYPE: "std_pron"] RSTR: <6>=#D[h] BODY: <7>=#D[h]] REST: #D[*cons* FIRST: #D["_like_v_1_rel" LBL: <1>=#D[h] ARG0: <2>=#D[e SF: "prop" TENSE: "pres" MOOD: "indicative" PROG: "-" PERF: "-"] ARG1: <3>=#D[x PERS: "1" NUM: "sg" PRONTYPE: "std_pron"] ARG2: <8>=#D[x PERS: "3" NUM: "pl" IND: "+"]] REST: #D[*cons* FIRST: #D[udef_q_rel LBL: <9>=#D[h] ARG0: <8>=#D[x PERS: "3" NUM: "pl" IND: "+"] RSTR: <10>=#D[h] BODY: <11>=#D[h]] REST: #D[*cons* FIRST: #D["_dog_n_1_rel" LBL: <12>=#D[h] ARG0: <8>=#D[x PERS: "3" NUM: "pl" IND: "+"]] REST: #D[*null*] ] ] ] ] ] HCONS: #D[*cons* FIRST: #D[qeq HARG: <0>=#D[h] LARG: <1>=#D[h]] REST: #D[*cons* FIRST: #D[qeq HARG: <6>=#D[h] LARG: <4>=#D[h]] REST: #D[*cons* FIRST: #D[qeq HARG: <10>=#D[h] LARG: <12>=#D[h]] REST: #D[*null*] ] ] ]] "Simple MRS"'''
        self.mrs = lui.load_mrs(mrs_text)


    def testIgdeDerivationHtmlTerminal(self):
        expected = '''<div class="derivationTree"><ul><li class="terminal"><p id=2 title="2: RULE_NAME">LABEL</p><p>TOKEN</p></li></ul></div>'''
        self.assertEqual(IgdeDerivation(self.terminal_derivation).output_HTML(), expected)


    def testIgdeDerivationHtmlUnary(self):
        expected = '''<div class="derivationTree"><ul><li><p id=93 title="93: RULE_NAME">LABEL</p><ul><li class="terminal"><p id=39 title="39: RULE_NAME2">LABEL2</p><p>TOKEN</p></li></ul></li></ul></div>'''
        self.assertEqual(IgdeDerivation(self.unary_derivation).output_HTML(), expected)


    def testIgdeDerivationHtmlBinary(self):
        expected = '''<div class="derivationTree"><ul><li><p id=93 title="93: RULE_NAME">LABEL</p><ul><li class="terminal"><p id=39 title="39: RULE_NAME2">LABEL2</p><p>TOKEN</p></li><li class="terminal"><p id=240 title="240: RULE_NAME3">LABEL3</p><p>TOKEN2</p></li></ul></li></ul></div>'''
        self.assertEqual(IgdeDerivation(self.binary_derivation).output_HTML(), expected)

    def testIgdeXmrsOutputHTML(self):
        expected = '''<table class="mrsTable"><tbody><tr><td>TOP</td><td>h0</td></tr><tr><td>INDEX</td><td>e2</td></tr><tr><td>RELS</td><td><table><td class="bracket"><</td><td><ul><table class=mrsRelation><tr><td colspan="2">pronoun_q_rel</td></tr><tr><td>LBL</td><td>h5</td></tr><tr><td>ARG0</td><td>x3</td></tr><tr><td>RSTR</td><td>h6</td></tr><tr><td>BODY</td><td>h7</td></tr></table><table class=mrsRelation><tr><td colspan="2">udef_q_rel</td></tr><tr><td>LBL</td><td>h9</td></tr><tr><td>ARG0</td><td>x8</td></tr><tr><td>RSTR</td><td>h10</td></tr><tr><td>BODY</td><td>h11</td></tr></table><table class=mrsRelation><tr><td colspan="2">"_dog_n_1_rel"</td></tr><tr><td>LBL</td><td>h12</td></tr><tr><td>ARG0</td><td>x8</td></tr></table><table class=mrsRelation><tr><td colspan="2">"_like_v_1_rel"</td></tr><tr><td>LBL</td><td>h1</td></tr><tr><td>ARG0</td><td>e2</td></tr><tr><td>ARG1</td><td>x3</td></tr><tr><td>ARG2</td><td>x8</td></tr></table><table class=mrsRelation><tr><td colspan="2">pron_rel</td></tr><tr><td>LBL</td><td>h4</td></tr><tr><td>ARG0</td><td>x3</td></tr></table></ul></td><td class="bracket">></td></table></td></tr><tr><td>HCONS</td><td>h0 qeq h1h6 qeq h4h10 qeq h12</td></tr></tbody></table>'''
        self.assertEqual(IgdeXmrs(self.mrs).output_HTML(), expected)

    
    def testIgdeHandleConstraintString(self):
        expected = '''h0 qeq h1'''
        self.assertEqual(expected, str(IgdeHandleConstraint(self.mrs.hcons[0])))

    
    def testIgdeElementaryPredicationOutputHTML(self):
        expected = '''<table class=mrsRelation><tr><td colspan="2">pronoun_q_rel</td></tr><tr><td>LBL</td><td>h5</td></tr><tr><td>ARG0</td><td>x3</td></tr><tr><td>RSTR</td><td>h6</td></tr><tr><td>BODY</td><td>h7</td></tr></table>'''
        self.assertEqual(expected, IgdeElementaryPredication(self.mrs.eps[0]).output_HTML())
