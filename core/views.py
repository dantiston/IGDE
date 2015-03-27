from core.models import Comments, User
    
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.models import Session
from django.contrib.auth.decorators import login_required

import logging
    
import redis

from delphin.interfaces.ace import InteractiveAce
from delphin.derivation import Derivation

# Initiate ACE
# TODO: Move this to being attached to a user
ace = InteractiveAce("/home/dantiston/delphin/erg.dat")

logger = logging.getLogger(__name__)

@login_required
def home(request):
    comments = Comments.objects.select_related().all()[0:100]
    return render(request, 'index.html', locals())

@csrf_exempt
def node_api(request):
    try:
        # Get User from sessionid
        session = Session.objects.get(session_key=request.POST.get('sessionid'))
        user_id = session.get_decoded().get('_auth_user_id')
        user = User.objects.get(id=user_id)

        # Parse text
        text = request.POST.get('comment')
        results = ace.parse(text)['RESULTS']
        html = (Derivation(item).output_HTML() for item in results)

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
