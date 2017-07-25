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
    def grammar(cls):
        return cls._grammar

    @property
    def grammar_path(cls):
        return cls._grammar_path

    @property
    def response(cls):
        return cls._response

    @property
    def grammar_not_loaded_error(cls):
        return cls._grammar_not_loaded_error

    @property
    def igde_json(cls):
        return cls._igde_json

    @property
    def mrs(cls):
        return cls._mrs

    @property
    def tree(cls):
        return cls._tree

    @property
    def secret_key(cls):
        return cls._secret_key

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

    # Keys
    _grammar = "grammar"

    _grammar_path = "grammar_path"

    _response = "response"

    _mrs = "MRS"

    _tree = "DERIV"

    _secret_key = "secret_key"


    # File names
    _igde_json = "igde.json"

    # Errors
    __error = "{{\"error\":\"{}\"}}"

    _grammar_not_loaded_error = __error.format("grammar not loaded")

    # HTML
    _delete_button = "<div type='button' class='deleteButton igdeButton secondary button'>X</div>"

    _collapse_button = "<div type='button' class='collapseButton igdeButton secondary button'>-</div>"
