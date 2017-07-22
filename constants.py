"""
Integrated Grammar Development Environment
@author: T.J. Trimble

constants.py

Small constant snippets of HTML and other objects

"""

class MetaConstants(type):
    """
    Meta-class to make read-only Constants
    """

    @property
    def mrs(cls):
        return cls._mrs

    @property
    def tree(cls):
        return cls._tree

    @property
    def delete_button(cls):
        return cls._delete_button

    @property
    def collapse_button(cls):
        return cls._collapse_button


class Constants(metaclass=MetaConstants):
    """
    Constants stores a collection of unmutable strings and other objects
    for consumption by other classes
    """

    _mrs = "MRS"

    _tree = "DERIV"

    _delete_button = "<div type='button' class='deleteButton igdeButton secondary button'>X</div>"

    _collapse_button = "<div type='button' class='collapseButton igdeButton secondary button'>-</div>"
