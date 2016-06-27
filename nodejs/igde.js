/*
 * igde.js
 *
 * Serverside nodejs for socket.io requests
 *
 * Serves the following socket.io requests:
 *     parse: Receives a sentence to parse and requests parse from PyDelphin, returns HTML representation
 *     request: Receives a command and related IDs to retrieve MRS and AVMs
 *
 */

// Global variables // TODO: Move to a constants file somewhere
const webhost = 'localhost';
const webport = 3000;
// var webport = 8000;
const socketport = 4000;

// Instantiations
const http = require('http');
const server = http.createServer().listen(socketport);
const io = require('socket.io').listen(server);
const cookie_reader = require('cookie');
const querystring = require('querystring');

const legal_commands = new Set(['request','parse']);


function djangoAction(message, socket, command) {

    if (!legal_commands.has(command)) {
	console.log("igde#djangoAction(): Illegal command " + command + " passed");
	return;
    }

    values = querystring.stringify({
        comment: message,
	sessionid: socket.handshake.cookie['sessionid'],
    });

    // Set up message to connect to Django view at /parse
    var options = {
	host: webhost,
	port: webport,
	path: '/'+command,
	method: 'POST',
	headers: {
	    'Content-Type': 'application/x-www-form-urlencoded',
	    'Content-Length': values.length
	}
    };

    // Send message to server
    var req = http.get(options, function(res){
	res.setEncoding('utf8');
	res.on('data', function(message) {
	    // TODO: Improve error handling!
	    // socket.emit('message', message, function(data) {
	    io.emit('message', message, function(data) {
		console.log(data);
	    });
        });
    });
    req.write(values);
    req.end();
}


//Configure socket.io to store cookie set by Django
io.configure(function(){
    io.set('authorization', function(data, accept){
	if(data.headers.cookie){
	    data.cookie = cookie_reader.parse(data.headers.cookie);
	    return accept(null, true);
	}
	return accept('error', false);
    });
    io.set('log level', 1);
});


io.sockets.on('connection', function (socket) {
    // TODO: Set up for parse, request, generate, and unify commands

    // Client is sending message through socket.io
    /*** PARSE ***/
    socket.on('parse', function(message) {restAndEmit(message, socket, "parse")});


    /*** REQUEST ***/
    socket.on('request', function(message) {restAndEmit(message, socket, "request")});

});
