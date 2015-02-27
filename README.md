# IGDE
Integrated Grammar Development Environment: A online web interface for the high performance [ACE](http://sweaglesw.org/linguistics/ace/) for working with [DELPH-IN](http://www.delph-in.net) style [HPSG](https://en.wikipedia.org/wiki/Head-driven_phrase_structure_grammar) natural language grammars, including parsing, generating, and exploring grammars (viewing lexical entries & rules, interactive unification, etc.).

The IGDE is built with [Django](https://www.djangoproject.com), combining Django's templating system with the responsive web design tools of [Foundation](http://foundation.zurb.com) using the [Django-zurb-foundation app](https://pypi.python.org/pypi/django-zurb-foundation/5.0.2). The system uses a live server-client connection through [Socket.io](http://socket.io) to interact with ACE on the client and processes the requests on the server.

Processing with ACE is handled through [PyDelphin](https://github.com/goodmami/pydelphin).

# VERSION HISTORY
v0.1: basic UI, parsing.
