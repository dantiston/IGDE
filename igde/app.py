import uuid
import html
import os

# Flask
from flask import Flask, request, render_template, session

# Flask extensions
from flask_session import Session
from flask_zurb_foundation import Foundation

# App
from . import secret
from . import wxlui

from .ace import InteractiveAce
from .constants import Constants as constants

from flask import Flask, session
from flask_session import Session # TODO: Remove this


SESSION_TYPE = 'redis'

# Initiate Flask
app = Flask(__name__)
app.config.from_object(__name__)
Foundation(app)

# Initiate session
app.secret_key = secret.load()
Session(app)

# This probably needs more functionality, but a simple dict is fine for now
instances = {}

def load_grammar():
    uuid = session[constants.uuid]
    grammar_path = session[constants.grammar_path]
    if (uuid, grammar_path) not in instances:
        instances[(uuid, grammar_path)] = InteractiveAce(grammar_path)


def gen_uuid():
    if constants.uuid not in session:
        session[constants.uuid] = uuid.uuid4()
        print("Created UUID: {}".format(session[constants.uuid]))


def init():
    session[constants.grammar_path] = os.getenv(constants.grammar_path)
    gen_uuid()
    load_grammar()


@app.route('/')
def index():
    # Return the index page
    init()
    # TODO: Index page should be generic ajax page with grammar name
    # TODO: Maybe this session.get can load the upload button on key miss?
    return render_template('index.html', grammar=session.get(constants.grammar_path, ""))


@app.route('/parse/<format>', methods=['POST'])
def parse_POST(text, format):
    # parse the given text
    text = request.data
    return parse(text, format)


@app.route('/parse/<format>/<text>', methods=['POST', 'GET'])
def parse_GET(text, format):
    # parse the given text
    text = html.unescape(text)
    return parse(text, format)


formats = {'text': (lambda x: str(x)), 'html': wxlui.fromTree }

def parse(sent, format):
    init()
    if format not in formats:
        return '\{"error": "illegal format: \"{}\""\}'.format(format)
    response = instances[(session[constants.uuid], session[constants.grammar_path])].interact(sent)
    print("Respone: {}".format(response))
    return "\n".join(formats[format](result[constants.tree]) for result in response.results())
    #return "\n".join(map(str, response.results()))


@app.route('/request/<sort>')
def request(sort):
    if response is not None:
        return response[sort]
    return "No result"


if __name__ == '__main__':
    app.run()
