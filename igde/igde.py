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


# Initiate Flask
app = Flask(__name__)
app.config.from_object(__name__)
Foundation(app)

# Initiate session
SESSION_TYPE = 'redis'
app.secret_key = secret.load()
Session(app)

GRAMMAR = "/Users/admin/Downloads/erg.dat" # TODO: Remove this

def load_grammar():
    # TODO: If grammar path not loaded, return error
    #if constants.grammar_path not in session:
    #    return "{\"error\":\"no grammar loaded\"}"

    if constants.grammar not in session:
        session[constants.grammar] = AceParser(GRAMMAR)


@app.route('/')
def index():
    # Return the index page
    load_grammar()
    # TODO: Index page should be generic ajax page with grammar name
    # TODO: Maybe this session.get can load the upload button on key miss?
    return render_template('index.html', grammar=session.get(constants.grammar, ""))


@app.route('/parse', methods=['POST'])
def parse_POST(text):
    # parse the given text
    text = request.data
    return parse(text)


@app.route('/parse/<text>', methods=['GET'])
def parse_GET(text):
    # parse the given text
    text = html.unescape(text)
    return parse(text)


def parse(sent):
    load_grammar()
    response = session[constants.grammar].interact(sent)
    return str(response.result(0).tree())


@app.route('/request/<sort>')
def request(sort):
    if response is not None:
        return response[sort]
    return "No result"


if __name__ == '__main__':
    app.run()
