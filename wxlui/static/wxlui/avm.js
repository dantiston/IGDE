/*
 * Integrated Grammar Development Environment
 * @author: T.J. Trimble
 *
 * avm.js
 *
 * jQuery for styling and interacting with
 * IgdeTypedFeatureStructure HTML representations
 *
 */

$(document).ready(function() {

    // AVM values toggle when clicking key
    $("#parses").on({
	click: function() {
	    var target = $(this).parent().children().eq(-1);
	    var visibleStyle = "block"; // Default to block for sub-avms
	    if (!$(target).parent().hasClass("IgdeCoreferenceTag")) {
		if ($(target).prop("tagName").toLowerCase() == "p" || target.hasClass("IgdeCoreferenceTag")) {
		    visibleStyle = "inline-block";
		}
		if (target.css('display') == 'none') {
		    target.css('display', visibleStyle);
		} else {
		    target.css('display','none');
		}
	    }
	}
    }, ".typedFeatureStructure div > p");

});
