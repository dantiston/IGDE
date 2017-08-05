"""
wxlui.py

a small library to convert ACE LUI results to HTML
"""

def fromTree(deriv):
    return "<p>{}</p>".format(deriv)

def fromMrs(mrs):
    return "<p>{}</p>".format(mrs)

def fromAvm(avm):
    return "<p>{}</p>".format(avm)
