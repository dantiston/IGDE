/*
 * Integrated Grammar Development Environment
 * @author: T.J. Trimble
 *
 */

// Page loader
$(document).ready(function(){

    // Connect to server
    var socket = io.connect('localhost', {port: 4000});
    
    // Connection code
    socket.on('connect', function(){
        console.log("connect");
    });
    
    /*** PARSING ***/
    function sendParse(entry_el) {
        var msg = entry_el.prop('value');
        if (msg) {
            socket.emit('parse', msg, function(data) {
                console.log(data);
            });
            //Clear input value
            entry_el.prop('value', '');
        }
    }

    // Get element
    var entry_element = $('#comment');
    var entry_button = $('button');

    // On submit, request parse from the server
    // TODO: add button, add this function to onclick for that button
    entry_element.keypress(function(event) {
        if (event.keyCode != 13) return;
	sendParse(entry_element);
    });
    entry_button.click(function(event) {
	sendParse(entry_element);
    });


    /*** REQUESTING MRS/AVM ***/
    // On click, request MRS/AVM from the server
    $("#parses").on('click', ".derivationTree p", function() {
	var tree_id = $(this).closest(".derivationTree").attr('id');
	var edge_id = this.id;
	if (tree_id && edge_id) {
	    var msg = "request " + tree_id + " " + edge_id + " mrs simple";
	    socket.emit('request', msg, function(data) {
		console.log(data);
	    });
	}
    });

    /*** UNIFICATION ***/
    // On drag and drop, request AVM of unification from the server
    // TODO: This


    /*** GENERATION ***/
    // On context-menu button click, request generation of sentences from MRS
    // TODO: This


    /*** REQUESTING GRAMMAR ENTITY ***/
    // On menu button click, request grammar entity
    // TODO: This


    /*** RESULTS ***/
    // On message from server, add message to list
    socket.on('message', function(message) {
        // Escape HTML characters
        var data = message.replace(/&/g,"&amp;")
	
        // Append message to the top of the list
        $('#parses').prepend(data);
        window.scrollTo(0, 0);
        entry_element.focus();
    });
});
