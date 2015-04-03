"""
Integrated Grammar Development Environment
@author: T.J. Trimble

views.py
"""

# General imports
import logging
import redis

from collections import defaultdict

# App imports
from core.models import Comments, User
from core.models import IgdeDerivation, IgdeXmrs

# PyDelphin imports
from delphin.interfaces import lui
from delphin.interfaces.ace import InteractiveAce

# Django imports    
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.models import Session
from django.contrib.auth.decorators import login_required


# Initiate ACE
# TODO: Move this to being attached to a user
ace = InteractiveAce("/home/dantiston/delphin/erg.dat")

logger = logging.getLogger(__name__)

# TODO: Home shouldn't have login required. Need to keep track of sessions
# and attach the parser instance to them. The parser should open and close
# with the browser connection.
@login_required
def home(request):
    comments = Comments.objects.select_related().all()[0:100]
    return render(request, 'index.html', locals())

@csrf_exempt # TODO: consider removing this?
def parse(request):
    try:
        # Get User from sessionid
        # TODO: Somehow get the user's ACE process
        #session = Session.objects.get(session_key=request.POST.get('sessionid'))
        #user_id = session.get_decoded().get('_auth_user_id')
        #user = User.objects.get(id=user_id)

        # Parse text
        text = request.POST.get('comment')
        results = lui.parse(ace, text)['RESULTS']
        html = (IgdeDerivation(lui.load_derivations(item)[0]).output_HTML()
                    for item in results)

        result = "<h3>{}</h3><h5>  ({} parses)</h5>".format(text, len(results))
        resultFormat = "<li>{}</li>"
        result += "<ul>{}</ul>".format("".join(resultFormat.format(item) for item in html))

        # Once datum has been parsed, send it back to user
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        r.publish('chat', result)

        return HttpResponse("Everything worked :)")

    except Exception as e:
        logger.debug(str(e))
        return HttpResponseServerError(str(e))


@csrf_exempt # TODO: consider removing this?
def request(request):
    error = ValueError("Request values should be in the form \"request X Y what\"")
    legal_commands = ("mrs simple", "avm")
    simple_names = {"mrs simple":"mrs"}
    try:
        text = request.POST.get('comment')
        try:
            sort, tree_ID, edge_ID, command = text.split(None, 3)
            tree_ID, edge_ID = int(tree_ID), int(edge_ID)
        except ValueError:
            raise error
        # Request should be in the form of "request X Y what"
        if sort != "request":
            raise error
        if command not in legal_commands:
            raise ValueError("Request must be one of \"{!r}\", not \"{!r}\"".format(legal_commands, command))
        if tree_ID < 0 or edge_ID < 0:
            raise error

        # Get User from sessionid
        # TODO: Somehow get the user's ACE process
        #session = Session.objects.get(session_key=request.POST.get('sessionid'))
        #user_id = session.get_decoded().get('_auth_user_id')
        #user = User.objects.get(id=user_id)

        # Send request to parser
        lui.request_mrs(ace, 1, 1)
        mrs = lui.load_mrs(lui.receive_mrs(ace))

        # mrs = lui.receive_mrs(ace)        
        # r = redis.StrictRedis(host='localhost', port=6379, db=0)
        # r.publish('chat', mrs)
        # return HttpResponse("Everything worked :)")

        html = IgdeXmrs(mrs).output_HTML()

        result = "<h5>({} for tree {})</h5><ul><li>{}</li></ul>".format(command, tree_ID, html)

        # Once datum has been parsed, send it back to user
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        r.publish('chat', result)

        return HttpResponse("Everything worked :)")

    except Exception as e:
        logger.debug(str(e))
        return HttpResponseServerError(str(e))
