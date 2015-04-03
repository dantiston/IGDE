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
    // Get element
    var entry_el = $('#comment');

    // On submit, request parse from the server
    // TODO: add button, add this function to onclick for that button
    entry_el.keypress(function(event) {

        //When enter is pressed send input value to node server
        if (event.keyCode != 13) return;
	
        var msg = entry_el.prop('value');
        if (msg) {
            socket.emit('parse', msg, function(data) {
                console.log(data);
            });
            //Clear input value
            entry_el.prop('value', '');
        }
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
        entry_el.focus();
    });
});
