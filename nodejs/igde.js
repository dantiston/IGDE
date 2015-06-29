/*
 * igde.js
 * 
 * Serverside nodejs for socket.io requests
 *  
 */

// Global variables
var webhost = 'localhost';
var webport = 3000;
var socketport = 4000;

// Instantiations
var http = require('http');
var server = http.createServer().listen(socketport);
var io = require('socket.io').listen(server);
var cookie_reader = require('cookie');
var querystring = require('querystring');

var legal_commands = ['request','parse'];


//var redis = require('socket.io/node_modules/redis');
//var sub = redis.createClient();

//Subscribe to the Redis chat channel
//sub.subscribe('chat');

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
    // Grab message from Redis and send to client
    //sub.on('message', function(channel, message){
    //	socket.send(message);
    //});

    // TODO: Set up for parse, request, generate, and unify commands

    // Client is sending message through socket.io
    /*** PARSE ***/
    socket.on('parse', function (message) {
	// message should be something like "I like dogs."
	values = querystring.stringify({
	    comment: message,
	    sessionid: socket.handshake.cookie['sessionid'],
	});

	// Set up message to connect to Django view at /parse
	var options = {
	    host: webhost,
	    port: webport,
	    path: '/parse',
	    method: 'POST',
	    headers: {
		'Content-Type': 'application/x-www-form-urlencoded',
		'Content-Length': values.length
	    }
	};

	// Send message to Django server
	var req = http.get(options, function(res){
	    res.setEncoding('utf8');
	    res.on('data', function(message){
		    // TODO: Improve error handling!
		    socket.emit('message', message, function(data) {
			console.log(data);
		    });
	    });
	});
	req.write(values);
	req.end();
    });


    /*** REQUEST ***/
    socket.on('request', function (message) {
	// message should be something like "browse 1 1 mrs simple"
	values = querystring.stringify({
	    comment: message,
	    sessionid: socket.handshake.cookie['sessionid'],
	});

	// Set up message to connect to Django view at /request
	var options = {
	    host: webhost,
	    port: webport,
	    path: '/request',
	    method: 'POST',
	    headers: {
		'Content-Type': 'application/x-www-form-urlencoded',
		'Content-Length': values.length
	    }
	};

	// Send message to Django server
	var req = http.get(options, function(res) {
	    res.setEncoding('utf8');
	    res.on('data', function(message){
	        // TODO: Improve error handling
	        socket.emit('message', message, function(data) {
	            console.log(data);
		});
	    });
	});
	req.write(values);
	req.end();
    });
});
