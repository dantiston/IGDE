from core.models import Comments, User
    
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.models import Session
from django.contrib.auth.decorators import login_required
    
import redis

from delphin.interfaces import ace

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
        parse = ace.parse("/home/dantiston/delphin/erg.dat", text)
        results = parse['RESULTS']
        html = []
        for result in results:
            tree = result['DERIV']
            mrs = result['MRS']
            html.append((tree, mrs))
        #     Comments.objects.create(user=user, text=text, tree=tree, mrs=mrs)
        #Comments.objects.create(user=user, text=str(parse))

        resultFormat = "<ul><li>%s</li><li>%s</li></ul>"
        result = "<ul>%s</ul>" % "".join(resultFormat % pair for pair in html)

        # Once comment has been created post it to the chat channel
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        #r.publish('chat', request.POST.get('comment'))
        r.publish('chat', result)

        return HttpResponse("Everything worked :)")
    except Exception as e:
        return HttpResponseServerError(str(e))
