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

// Constants
var coreferenceColorDefault = "#0000FF";
var coreferenceColorHover = "#00CCFF";


// Highlight coreference
coref_prefix = "coref_";
function highlightCoreference(domElement, color) {
    var element = $(domElement);
    if (typeof element.attr("class") !== "undefined") {
	var className = getLastClassName(element);
	if (className.substring(0, coref_prefix.length) == coref_prefix) {
	    var closest = element.closest(".typedFeatureStructure");
	    closest.find("."+className).css("color", color);
	}
    }
}


function getLastClassName(object) {
    return object.attr("class").split(" ").slice(-1)[0];
}


$(document).ready(function() {

    // AVM values toggle when clicking key
    $("#parses").on({
	click: function() {
	    var target = $(this).parent().children().eq(-1);
	    if (!($(target).parent().hasClass("IgdeCoreferenceTag") ||
		  $(target).hasClass("IgdeCoreferenceTag") ||
		  $(target).prop("tagName").toLowerCase() == "p" ||
		  $(target).parent().children().eq(-1).hasClass("terminal"))) {
		target.toggle();
	    }
	}
    }, ".typedFeatureStructure div > p");


    // Highlight coreference tags
    // Assumes the last class is in the form coref_X
    $("#parses").on({
	    mouseenter: function () {
		highlightCoreference($(this).parent(), coreferenceColorHover);
	    },
	    mouseleave: function () {
		highlightCoreference($(this).parent(), coreferenceColorDefault);
	    }
	}, ".IgdeCoreferenceTag p");


    // Click through coreference tags
    $("#parses").on({
	    click: function() {
		alert("Not implemented yet!")
	    }
	}, ".typedFeatureStructure div > li > .IgdeCoreferenceTag");

});
