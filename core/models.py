"""
Integrated Grammar Development Environment
@author: T.J. Trimble

models.py
"""

from django.db import models
from django.contrib.auth.models import User

from delphin.derivation import Derivation
from delphin.mrs import Xmrs
from delphin.mrs.components import HandleConstraint, ElementaryPredication, Argument

    
class Comments(models.Model):
    user = models.ForeignKey(User)
    text = models.CharField(max_length=255)
    parse = models.CharField(max_length=8192, default="")
    mrs = models.CharField(max_length=8192, default="")


class IgdeDerivation(Derivation):
    """
    Loads a PyDelphin.delphin.derivation.Derivation object and adds
    additional output methods, specifically output_HTML()
    """

    def __init__(self, other):
        """
        For creating copies of Derivation objects
        """
        # Convert children to this class
        self.children = [IgdeDerivation(child) for child in other.children]
        self.edge_ID = other.edge_ID
        self.label = other.label
        self.token = other.token
        self.chart_ID = other.chart_ID
        self.rule_name = other.rule_name
        self.tree_ID = other.tree_ID
    
    def output_HTML(self, top=True, title_text=True):
        """
        Returns HTML representation of tree in the following format:
            
            <div class="derivationTree" id={TREE_ID}>
                <ul>
                    <li>
                        <p id={EDGE_ID}{TITLE}>{PARENT_LABEL}</p>
                        <ul>
                            <li class="terminal">
                                <p id={EDGE_ID} title="{EDGE_ID}: {RULE_NAME}">{LABEL}</p>
                                <p>{TOKEN}</p>
                            </li>
                        </ul>
                    </li>
                    <li class="terminal">
                        <p id={EDGE_ID} title="{EDGE_ID}: {RULE_NAME}">{LABEL}</p>
                        <p>{TOKEN}</p>
                    </li>
                </ul>
            </div>


        See http://thecodeplayer.com/walkthrough/css3-family-tree
        
        By default, this method returns HTML styled with the HTML's title
        attribute set to the rule used and the parse chart ID. Pass
        title_text=False to disable this.
        """
        top_formatter = "<div class=\"derivationTree\"{tree_ID}><ul>{values}</ul></div>"
        formatter = "<li{CLASS}><p{EDGE_ID}{TITLE}>{LABEL}</p>{TOKEN}{CHILDREN}</li>"
        # Add token if applicable
        values = {
            "CLASS": " class=\"terminal\"" if not self.children else "",
            "EDGE_ID": " id={}".format(self.edge_ID),
            "TITLE": " title=\"{}: {}\"".format(self.edge_ID, self.rule_name) if title_text else "",
            "LABEL": self.label,
            "TOKEN": "<p>{}</p>".format(self.token) if self.token else "",
            "CHILDREN": "<ul>{}</ul>".format("".join(child.output_HTML(top=False, title_text=title_text) for child in self.children)) if self.children else ""
        }
        # Return result
        result = formatter.format(**values)
        if top:
            tree_ID = " id=\"{}\"".format(self.tree_ID) if self.tree_ID else ""
            result = top_formatter.format(tree_ID=tree_ID, values=result)
        return result


class IgdeXmrs(Xmrs):
    """
    Loads a PyDelphin.delphin.mrs.Xmrs object and adds
    additional output methods, specifically output_HTML()
    """

    formatter = "<table class=\"mrsTable\"><tbody><tr><td>TOP</td><td>{TOP}</td></tr><tr><td>INDEX</td><td>{INDEX}</td></tr>{RELS}{HCONS}{ICONS}</tbody></table>"
    bracket_formatter = "<tr><td>{}</td><td><table class=\"mrsInnerTable {}\"><td class=\"bracket\"><</td><td><ul>{}</ul></td><td class=\"bracket\">></td></table></td></tr>"

    list_delimiter = "<p>, </p>"


    def __init__(self, other):
        """
        For creating copies of Xmrs objects
        """
        self._graph = other._graph
        self.hook = other.hook
        self.lnk = other.lnk
        self.surface = other.surface
        self.identifier = other.identifier
            
    def output_HTML(self):
        """
        Returns HTML representation of MRS in the following format:

        <table class="mrsTable">
            <tbody>
                <tr>
                    <td>TOP</td>
                    <td>{TOP}</td> 
		</tr>
		<tr>
                    <td>INDEX</td>
		    <td>{INDEX}</td> 
		</tr>
		<tr>
		    <td>RELS</td>
		    <td>
		        <table>
			    <td class="bracket"><</td>
			    <td><ul>{RELS}</ul></td>
			    <td class="bracket">></td>
			</table>
		    </td> 
		</tr>
		<tr>
		    <td>HCONS</td>
		    <td>
		        <table>
			    <td class="bracket"><</td>
			    <td><ul>{HCONS}</ul></td>
			    <td class="bracket">></td>
			</table>
		    </td> 
		</tr>
		<tr>
		    <td>ICONS</td>
		    <td>
		        <table>
			    <td class="bracket"><</td>
			    <td><ul>{ICONS}</ul></td>
			    <td class="bracket">></td>
			</table>
		    </td> 
		</tr>
	    </tbody>
        </table>
        """
        
        # Add token if applicable
        # TODO: Move conversions to init
        values = {
            "TOP":IgdeArgument(self.ltop, "ltop").output_HTML(),
            "INDEX":IgdeArgument(self.index, "index").output_HTML(),
            "RELS":IgdeXmrs.bracket_formatter.format("RELS", "rels", "".join(IgdeElementaryPredication(ep).output_HTML() for ep in self.eps)),
            "HCONS":IgdeXmrs.bracket_formatter.format("HCONS", "hcons", IgdeXmrs.list_delimiter.join(str(IgdeHandleConstraint(hc).output_HTML()) for hc in self.hcons)),
            "ICONS":IgdeXmrs.bracket_formatter.format("ICONS", "icons", IgdeXmrs.list_delimiter.join(str(IgdeInformationConstraint(ic).output_HTML()) for ic in self.icons)) if self.icons else "",
        }
        # Return result
        return IgdeXmrs.formatter.format(**values)


class IgdeHandleConstraint(HandleConstraint):

    format = """<div class="mrsHandleConstraint">{hi}<p class="mrsHandleConstraintRelation"> {relation} </p>{lo}</div>"""
    
    def __init__(self, other):
        """
        For creating copies of HandleConstraint objects
        """
        if not isinstance(other, HandleConstraint):
            raise TypeError("{} constructor passed object of type {}, must be of type HandleConstraint".format(__class__.__name__, other.__class__.__name__))
        self.hi = other.hi
        self.relation = other.relation
        self.lo = other.lo

    def __str__(self):
        """
        Format:
            hi relation lo
        """
        return " ".join(map(str, (self.hi, self.relation, self.lo)))

    def __repr__(self):
        return "<{}: {} at {}>".format(self.__class__.__name__, str(self), id(self))

    def output_HTML(self):
        """
        Format:
            <div><p id="{hi}" class="hi">{hi}</p><p> {relation} </p><p id="{lo}" class="lo">{lo}</p></div>
        """
        return IgdeHandleConstraint.format.format(
            hi=IgdeArgument(self.hi, "hi").output_HTML(),
            relation=self.relation,
            lo=IgdeArgument(self.lo, "lo").output_HTML())


class IgdeInformationConstraint(object):

    def __init__(self, other):
        """
        For creating copies of InformationConstraint objects
        TODO: this!
        """
        self = other



class IgdeElementaryPredication(ElementaryPredication):
    
    def __init__(self, other):
        """
        For creating copies of ElementaryPredication objects
        """
        if not isinstance(other, ElementaryPredication):
            raise TypeError("{} constructor passed object of type {}, must be of type HandleConstraint".format(__class__.__name__, other.__class__.__name__))
        self._node = other._node
        self.label = IgdeArgument(other.label, "label")
        self.pred = other.pred
        self.argdict = other.argdict

    def output_HTML(self, htmlClass="mrsRelation", propertiesClass="mrsRelationProperties"):
        """
        Returns HTML representation of ElementaryPredication in the following format:

        <table class={CLASS}>
            <tr>
                <td colspan="3">{PREDICATE}</td>
            </tr>
            <tr>
                <td>LBL</td>
                <td>{LABEL}</td>
                <td/>
            </tr>
            (<tr>
                <td>{ARGnName}</td>
                <td>{ARGnVariable}</td>
                <td>{ARGnProperties}</td>
            </tr>)*
        </table>
        """
        formatter = '''<table{CLASS}><tr><td colspan="3">{PREDICATE}</td></tr><tr><td>LBL</td><td>{LABEL}</td></tr>{ARGUMENTS}</table>'''
        argFormatter = '''<tr><td>{ARGNAME!s}</td><td>{ARGVALUE}</td><td{CLASS}>{ARGPROPERTIES}</td></tr>'''
        empty = '''<tr></tr>'''
        propertiesClassFormatter = ''' class={}'''
        
        values = {
            "CLASS":" class={}".format(htmlClass) if htmlClass else "",
            "PREDICATE":self.pred,
            "LABEL":"".join((self.label.output_HTML(), "<td></td>")),
            #"ARGUMENTS":"".join(argFormatter.format(ARGNAME=name, ARGVALUE=IgdeArgument(argument.value, name).output_HTML(), ARGPROPERTIES=propertiesFormatter.format(",<br/>".join(": ".join(map(str, entry)) for entry in argument.value.properties.items())) if argument.value.properties else "", CLASS=propertiesClass if argument.value.properties else "") for name, argument in self.argdict.items()) if self.argdict else empty,
            "ARGUMENTS":"".join(argFormatter.format(ARGNAME=name, ARGVALUE=IgdeArgument(argument.value, name).output_HTML(), ARGPROPERTIES=IgdeArgument(argument.value, name).output_properties_HTML(), CLASS=propertiesClassFormatter.format(propertiesClass)) for name, argument in self.argdict.items()) if self.argdict else empty,
            #"ARGUMENTS":"".join(argFormatter.format(ARGNAME=name, ARGVALUE=IgdeArgument(argument.value, name).output_HTML(), ARGPROPERTIES="", CLASS=propertiesClass if argument.value.properties else "") for name, argument in self.argdict.items()) if self.argdict else empty,
        }

        return formatter.format(**values)


class IgdeArgument(Argument):

    format = """<p id="{value}" class="mrsVar mrsVar_{value}">{value}</p>"""

    propertiesFormatter = "<div class=\"{bracketsClass}\">[</div><div class=\"{propertiesClass}\">{}</div><div class=\"{bracketsClass}\">]</div>"


    def __init__(self, value, sort, properties=None):
        self.value = value
        self.sort = sort
        self.properties = properties # OrderedDict

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "<{}: {} at {}>".format(self.__class__.__name__, str(self), id(self))

    def output_HTML(self):
        return self.__class__.format.format(value=self.value)

    def output_properties_HTML(self, propertiesValuesClass="mrsPropertiesValues", propertiesBracketsClass="mrsPropertiesBracket"):
        if not self.value.properties:
            return ""
        else:
            return IgdeArgument.propertiesFormatter.format(",<br/>".join(": ".join(map(str, entry)) for entry in self.value.properties.items()), bracketsClass=propertiesBracketsClass, propertiesClass=propertiesValuesClass)
