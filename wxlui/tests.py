#Django imports
from django.test import TestCase

# pyDelphin imports
from delphin.interfaces import lui
from delphin.derivation import Derivation
from delphin.mrs import Xmrs

# App imports
from .models import IgdeDerivation, IgdeXmrs, IgdeHandleConstraint, IgdeElementaryPredication, IgdeArgument


class IgdeViewsTests(TestCase):
    
    def testParse(self):
        """
        Test that the parse method returns the proper HTML for parse requests
        """
        pass


    def testBrowseAvm(self):
        """
        Test that the browse method returns the proper HTML for AVM requests
        """
        pass


    def testBrowseMrs(self):
        """
        Test that the browse method returns the proper HTML for MRS requests
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
        expected = '''<div class="derivationTree"><ul><li class="terminal"><p id=1 title="1: RULE_NAME">LABEL</p><p>TOKEN</p></li></ul></div>'''
        self.assertEqual(IgdeDerivation(self.terminal_derivation).output_HTML(), expected)


    def testIgdeDerivationHtmlUnary(self):
        expected = '''<div class="derivationTree"><ul><li><p id=9 title="9: RULE_NAME">LABEL</p><ul><li class="terminal"><p id=10 title="10: RULE_NAME2">LABEL2</p><p>TOKEN</p></li></ul></li></ul></div>'''
        self.assertEqual(IgdeDerivation(self.unary_derivation).output_HTML(), expected)


    def testIgdeDerivationHtmlBinary(self):
        expected = '''<div class="derivationTree"><ul><li><p id=9 title="9: RULE_NAME">LABEL</p><ul><li class="terminal"><p id=10 title="10: RULE_NAME2">LABEL2</p><p>TOKEN</p></li><li class="terminal"><p id=11 title="11: RULE_NAME3">LABEL3</p><p>TOKEN2</p></li></ul></li></ul></div>'''
        self.assertEqual(IgdeDerivation(self.binary_derivation).output_HTML(), expected)


    def testIgdeXmrsOutputHTML(self):
        expected = '''<table class="mrsTable"><tbody><tr><td>TOP</td><td><p id="h0" class="mrsVar mrsVar_h0">h0</p></td></tr><tr><td>INDEX</td><td><p id="e2" class="mrsVar mrsVar_e2">e2</p></td></tr><tr><td>RELS</td><td><table class="mrsInnerTable rels"><td class="bracket"><</td><td><ul><table class="mrsRelation"><tr><td colspan="3">pronoun_q_rel</td></tr><tr><td>LBL</td><td><p id="h5" class="mrsVar mrsVar_h5">h5</p><td></td></td></tr><tr><td>ARG0</td><td><p id="x3" class="mrsVar mrsVar_x3">x3</p></td><td><div class="mrsRelationProperties" title="PERS: 1,<br/>NUM: sg,<br/>PRONTYPE: std_pron"><div class="mrsPropertiesBracket">[</div><div class="mrsPropertiesValues">PERS: 1,<br/>NUM: sg,<br/>PRONTYPE: std_pron</div><div class="mrsPropertiesBracket">]</div></div></td></tr><tr><td>RSTR</td><td><p id="h6" class="mrsVar mrsVar_h6">h6</p></td><td></td></tr><tr><td>BODY</td><td><p id="h7" class="mrsVar mrsVar_h7">h7</p></td><td></td></tr></table><table class="mrsRelation"><tr><td colspan="3">udef_q_rel</td></tr><tr><td>LBL</td><td><p id="h9" class="mrsVar mrsVar_h9">h9</p><td></td></td></tr><tr><td>ARG0</td><td><p id="x8" class="mrsVar mrsVar_x8">x8</p></td><td><div class="mrsRelationProperties" title="PERS: 3,<br/>NUM: pl,<br/>IND: +"><div class="mrsPropertiesBracket">[</div><div class="mrsPropertiesValues">PERS: 3,<br/>NUM: pl,<br/>IND: +</div><div class="mrsPropertiesBracket">]</div></div></td></tr><tr><td>RSTR</td><td><p id="h10" class="mrsVar mrsVar_h10">h10</p></td><td></td></tr><tr><td>BODY</td><td><p id="h11" class="mrsVar mrsVar_h11">h11</p></td><td></td></tr></table><table class="mrsRelation"><tr><td colspan="3">"_dog_n_1_rel"</td></tr><tr><td>LBL</td><td><p id="h12" class="mrsVar mrsVar_h12">h12</p><td></td></td></tr><tr><td>ARG0</td><td><p id="x8" class="mrsVar mrsVar_x8">x8</p></td><td><div class="mrsRelationProperties" title="PERS: 3,<br/>NUM: pl,<br/>IND: +"><div class="mrsPropertiesBracket">[</div><div class="mrsPropertiesValues">PERS: 3,<br/>NUM: pl,<br/>IND: +</div><div class="mrsPropertiesBracket">]</div></div></td></tr></table><table class="mrsRelation"><tr><td colspan="3">"_like_v_1_rel"</td></tr><tr><td>LBL</td><td><p id="h1" class="mrsVar mrsVar_h1">h1</p><td></td></td></tr><tr><td>ARG0</td><td><p id="e2" class="mrsVar mrsVar_e2">e2</p></td><td><div class="mrsRelationProperties" title="SF: prop,<br/>TENSE: pres,<br/>MOOD: indicative,<br/>PROG: -,<br/>PERF: -"><div class="mrsPropertiesBracket">[</div><div class="mrsPropertiesValues">SF: prop,<br/>TENSE: pres,<br/>MOOD: indicative,<br/>PROG: -,<br/>PERF: -</div><div class="mrsPropertiesBracket">]</div></div></td></tr><tr><td>ARG1</td><td><p id="x3" class="mrsVar mrsVar_x3">x3</p></td><td><div class="mrsRelationProperties" title="PERS: 1,<br/>NUM: sg,<br/>PRONTYPE: std_pron"><div class="mrsPropertiesBracket">[</div><div class="mrsPropertiesValues">PERS: 1,<br/>NUM: sg,<br/>PRONTYPE: std_pron</div><div class="mrsPropertiesBracket">]</div></div></td></tr><tr><td>ARG2</td><td><p id="x8" class="mrsVar mrsVar_x8">x8</p></td><td><div class="mrsRelationProperties" title="PERS: 3,<br/>NUM: pl,<br/>IND: +"><div class="mrsPropertiesBracket">[</div><div class="mrsPropertiesValues">PERS: 3,<br/>NUM: pl,<br/>IND: +</div><div class="mrsPropertiesBracket">]</div></div></td></tr></table><table class="mrsRelation"><tr><td colspan="3">pron_rel</td></tr><tr><td>LBL</td><td><p id="h4" class="mrsVar mrsVar_h4">h4</p><td></td></td></tr><tr><td>ARG0</td><td><p id="x3" class="mrsVar mrsVar_x3">x3</p></td><td><div class="mrsRelationProperties" title="PERS: 1,<br/>NUM: sg,<br/>PRONTYPE: std_pron"><div class="mrsPropertiesBracket">[</div><div class="mrsPropertiesValues">PERS: 1,<br/>NUM: sg,<br/>PRONTYPE: std_pron</div><div class="mrsPropertiesBracket">]</div></div></td></tr></table></ul></td><td class="bracket">></td></table></td></tr><tr><td>HCONS</td><td><table class="mrsInnerTable hcons"><td class="bracket"><</td><td><ul><div class="mrsHandleConstraint"><p id="h0" class="mrsVar mrsVar_h0">h0</p><p class="mrsHandleConstraintRelation"> qeq </p><p id="h1" class="mrsVar mrsVar_h1">h1</p></div><p>, </p><div class="mrsHandleConstraint"><p id="h6" class="mrsVar mrsVar_h6">h6</p><p class="mrsHandleConstraintRelation"> qeq </p><p id="h4" class="mrsVar mrsVar_h4">h4</p></div><p>, </p><div class="mrsHandleConstraint"><p id="h10" class="mrsVar mrsVar_h10">h10</p><p class="mrsHandleConstraintRelation"> qeq </p><p id="h12" class="mrsVar mrsVar_h12">h12</p></div></ul></td><td class="bracket">></td></table></td></tr></tbody></table>'''
        self.assertEqual(IgdeXmrs(self.mrs).output_HTML(), expected)

    
    def testIgdeHandleConstraintString(self):
        expected = '''h0 qeq h1'''
        self.assertEqual(expected, str(IgdeHandleConstraint(self.mrs.hcons[0])))


    def testIgdeHandleConstraintOutputHTML(self):
        expected = '''<div class="mrsHandleConstraint"><p id="h0" class="mrsVar mrsVar_h0">h0</p><p class="mrsHandleConstraintRelation"> qeq </p><p id="h1" class="mrsVar mrsVar_h1">h1</p></div>'''
        self.assertEqual(expected, IgdeHandleConstraint(self.mrs.hcons[0]).output_HTML())
    

    def testIgdeElementaryPredicationOutputHTML(self):
        expected = '''<table class="mrsRelation"><tr><td colspan="3">pronoun_q_rel</td></tr><tr><td>LBL</td><td><p id="h5" class="mrsVar mrsVar_h5">h5</p><td></td></td></tr><tr><td>ARG0</td><td><p id="x3" class="mrsVar mrsVar_x3">x3</p></td><td><div class="mrsRelationProperties" title="PERS: 1,<br/>NUM: sg,<br/>PRONTYPE: std_pron"><div class="mrsPropertiesBracket">[</div><div class="mrsPropertiesValues">PERS: 1,<br/>NUM: sg,<br/>PRONTYPE: std_pron</div><div class="mrsPropertiesBracket">]</div></div></td></tr><tr><td>RSTR</td><td><p id="h6" class="mrsVar mrsVar_h6">h6</p></td><td></td></tr><tr><td>BODY</td><td><p id="h7" class="mrsVar mrsVar_h7">h7</p></td><td></td></tr></table>'''
        self.assertEqual(expected, IgdeElementaryPredication(self.mrs.eps[0]).output_HTML())


    def testIgdeArgumentOutputHTML(self):
        expect = '''<p id="h0" class="mrsVar mrsVar_h0">h0</p>'''
        self.assertEqual(expect, IgdeArgument(self.mrs.hcons[0].hi, "hi").output_HTML())
