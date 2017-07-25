/*
 * Integrated Grammar Development Environment
 * @author: T.J. Trimble
 *
 * igde.js
 *
 * * Basic functionality for interacting with Python
 * * Page level functionality
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
        if (element.is("p") || element.is(".mrsRelationProperties")) {
            return element.attr("title");
        }
    }
});


// Page loader
$(document).ready(function(){

    // Get element
    var entry_element = $('#comment');
    var entry_button = $('button#analyze');

    /*** PARSING ***/
    function requestParse(entry_el) {
	const msg = entry_el.prop('value');
	if (msg) {
	    console.log("Requesting parse for \"" + msg + "\"");
	    $.get('/parse/html/' + msg, function(data) {
	        $("#parses").prepend(data);
		console.log(data);
	    });
	    entry_el.prop('value', ''); // Clear input value
	    return true;
	}
	return false;
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
	console.log(tree_id + "; " + edge_id)
	if (tree_id && edge_id && what) {
	    var msg = "request " + tree_id + " " + edge_id + " " + what;
	    console.log("Sending \"" + msg + "\"");
	    $.post('/request/', msg, function(data) {
		$("#parses").prepend(data);
		console.log(data);
	    });
	}
    }

    // On click, request MRS/AVM from the server
    $("#parses").on('click', ".derivationTree p", function() {
	requestTfs($(this).closest(".derivationTree").attr('id'), this.id, "avm");
    });


    $("#parses").on('click', ".mrsButton", function() {
	requestTfs($(this).siblings('li').eq(-1).children(".derivationTree").eq(0).attr('id'),
		   $(this).siblings('li').eq(-1).children(".derivationTree").eq(0).children().eq(0).children().eq(0).children().eq(0).attr('id'),
		   "mrs simple");
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


    /*** Item management ***/
    // Delete button
    $('#parses').on('click', '.deleteButton', function() {
	    $(this).parent().remove();
	});

    // Collapse button
    $('#parses').on('click', '.collapseButton', function() {
	    $(this).parent().children().eq(-2).toggle();
	});
});
