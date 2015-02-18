from core.models import Comments, User
    
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.models import Session
from django.contrib.auth.decorators import login_required

import logging
    
import redis

from delphin.interfaces.ace import InteractiveAce

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
        logger.debug("TEXT: %s" % text)
        parse = ace.parse(text)
        logger.debug("PARSE: {}".format(str(parse)))
        results = parse['RESULTS']
        html = []
        for result in results:
            tree = result['DERIV']
            mrs = result['MRS']
            html.append((tree, mrs))

        result = "<h3>{}</h3>".format(text)
        resultFormat = "<li><ul><li>%s</li><li>%s</li></ul></li>"
        result += "<ul>{}</ul>".format("".join(resultFormat % pair for pair in html))

        # Once datum has been parsed, send it back to user
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        r.publish('chat', result)

        return HttpResponse("Everything worked :)")
    except Exception as e:
        logger.debug(str(e))
        return HttpResponseServerError(str(e))
