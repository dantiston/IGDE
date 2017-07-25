import uuid

# Flask
from flask import Flask, request, render_template, session
import html

# Flask extensions
from flask_session import Session
from flask_zurb_foundation import Foundation

# Delphin
from delphin.interfaces.ace import AceParser

# App
from . import secret
#from . import models

from .constants import Constants as constants

from flask import Flask, session
from flask_session import Session


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
    if constants.grammar_path not in session:
        return "{\"error\":\"no grammar loaded\"}"

    uuid = session['uuid']
    grammar = session[constants.grammar_path]
    if uuid not in instances:
        instances[(uuid, grammar)] = AceParser(grammar)


def gen_uuid():
    if 'uuid' not in session:
        session['uuid'] = uuid.uuid4()


def init():
    session[constants.grammar_path] = "/Users/admin/Downloads/erg.dat" # TODO: Change this
    session[constants.grammar] = "erg-1214.dat"
    gen_uuid()
    load_grammar()


@app.route('/')
def index():
    # Return the index page
    init()
    # TODO: Index page should be generic ajax page with grammar name
    # TODO: Maybe this session.get can load the upload button on key miss?
    return render_template('index.html', grammar=session.get(constants.grammar, ""))


@app.route('/parse/<format>', methods=['POST'])
def parse_POST(text, format):
    # parse the given text
    text = request.data
    return parse(text, format)


@app.route('/parse/<format>/<text>', methods=['GET'])
def parse_GET(text, format):
    # parse the given text
    text = html.unescape(text)
    return parse(text, format)

formats = {'text': (lambda x: str(x)), 'html': (lambda x: str(x)) }

def parse(sent, format):
    init()
    if format not in formats:
        return '\{"error": "illegal format: \"{}\""\}'.format(format)
    response = instances[(session['uuid'], session[constants.grammar_path])].interact(sent)
    return formats[format](response.result(0).tree())


@app.route('/request/<sort>')
def request(sort):
    if response is not None:
        return response[sort]
    return "No result"


if __name__ == '__main__':
    app.run()
