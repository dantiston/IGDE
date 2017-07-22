from flask import Flask, request
import html

from flask_session import Session

from delphin.interfaces.ace import AceParser

from .constants import Constants as constants

#from . import models

app = Flask(__name__)
app.config.from_object(__name__)
Session(app)

SESSION_TYPE = 'redis'
GRAMMAR = "/Users/admin/Downloads/erg.dat"

# TODO: Move these to session
#grammar = AceParser(GRAMMAR)
#response = None


@app.route('/')
def index():
    # Return the index page
    # TODO: Index page should be generic socket.io page with grammar name
    return "Hello world!"


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
    #if grammar is not None:
    #    result = grammar.interact(sent)
    #    return result[0]["MRS"]
    #return "Grammar not loaded"

    #with AceParser(GRAMMAR) as grammar:
    #    result = grammar.interact(sent)
    #    return result["RESULTS"][0][constants.tree]
    #return "No parse found"

    #results = grammar.interact(sent)
    #return results.results(0).tree()
    #return str(results)

    response = grammar.interact(sent)
    return str(response.result(0).tree())


@app.route('/request/<sort>')
def request(sort):
    if response is not None:
        return response[sort]
    return "No result"


if __name__ == '__main__':

    #with AceParser(GRAMMAR, 'r') as grammar:
    #    app.run()

    app.run()
