/*
 * Integrated Grammar Development Environment
 * @author: T.J. Trimble
 *
 * igde.js
 *
 * jQuery for interacting with socket.io
 * Provides the following core functions:
 * 
 *     * requestParse: requests parse of the value in #comment
 *     * requestTfs: requests MRS or AVM
 *     * requestUnify: requests unification of two given tree_ID:edge_ID pairs
 *     * requestGenerate: requests generation of the given MRS
 *     * requestGrammarEntity: requests specified grammar entity
 *  
 */

// Tooltip
$(document).tooltip({
    items:".derivationTree p,.mrsRelationProperties",
    track: true,
    content: function() {
        var element = $(this);
        if (element.is("p")) {
            return element.attr("title");
        }
        else if (element.is(".mrsRelationProperties")) {
            return element.attr("title");
        }
    }
});

// Page loader
$(document).ready(function(){

    // Connect to server
    var socket = io.connect('localhost', {port: 4000});
    
    // Connection code
    socket.on('connect', function(){
        console.log("Successfully connected to server.");
    });

    // Get element
    var entry_element = $('#comment');
    var entry_button = $('button#analyze');

    /*** PARSING ***/
    function requestParse(entry_el) {
	var msg = entry_el.prop('value');
	if (msg) {
	    socket.emit('parse', msg, function(data) {
		console.log(data);
	    });
	    //Clear input value
	    entry_el.prop('value', '');
	}
    }

    entry_element.keypress(function(event) {
        if (event.keyCode != 13) return;
	requestParse(entry_element);
    });
    entry_button.click(function(event) {
	requestParse(entry_element);
    });


    /*** REQUESTING MRS/AVM ***/
    function requestTfs(tree_id, edge_id, what) {
	if (tree_id && edge_id && what) {
	    var msg = "request " + tree_id + " " + edge_id + " " + what;
	    console.log("Requesting " + msg);
	    socket.emit('request', msg, function(data) {
		console.log(data);
	    });
	}
    }

    // On click, request MRS/AVM from the server
    // TODO: make this happen on proper menu click
    $("#parses").on('click', ".derivationTree p", function() {
	//requestTfs($(this).closest(".derivationTree").attr('id'), this.id, "mrs simple");
	// TODO: Figure out the UX for requesting MRS vs AVM and implement here
	requestTfs($(this).closest(".derivationTree").attr('id'), this.id, "avm");
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
