from flask import Flask, request, render_template, session
import html

from flask_session import Session
from flask_zurb_foundation import Foundation

from delphin.interfaces.ace import AceParser

from .constants import Constants as constants

#from . import models

app = Flask(__name__)
app.config.from_object(__name__)
Session(app)
Foundation(app)

SESSION_TYPE = 'redis'
GRAMMAR = "/Users/admin/Downloads/erg.dat"


@app.route('/')
def index():
    # Return the index page
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
