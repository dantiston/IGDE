/*
 * Integrated Grammar Development Environment
 * @author: T.J. Trimble
 *
 * mrs.js
 *
 * jQuery for styling and interacting with
 * IgdeMrs HTML representations
 *  
 */

// Constants
var mrsVarColorDefault = "#000000";
var mrsVarColorMainHover = "#FF0000";
var mrsVarColorSecondaryHover = "#33CC33";


// Highlight MRS variable
mrs_prefix = "mrsVar_";
function highlightMrsVar(domElement, color, secondaryColor) {
    var element = $(domElement);
    var className = getLastClassName(element);
    if (className.substring(0, mrs_prefix.length) == mrs_prefix) {
	var closest = element.closest(".mrsTable");
	closest.find("."+className).css("color", color);
	// Check for links
	if (secondaryColor != null) {
	    // Check for handle constraint links and highlight
	    if (closest.find(".hcons ."+className).siblings(".mrsVar").length > 0) {
		closest.find("."+(closest.find(".hcons ."+className).siblings(".mrsVar").slice(0).attr("class").split(" ").slice(-1)[0])).css("color", secondaryColor);
	    }
	    // Check for information constraint links and highlight
	}
    }
}

function getLastClassName(object) {
    return $(object).attr("class").split(" ").eq(-1);
}


// Page loader functions
$(document).ready(function() {

    // Show/hide properties on onclick
    $("#parses").on({
	click: function () {
	    $(this).children().eq(1).toggle();
	}
    }, ".mrsRelationProperties");
    

    // Assumes correct mrsVar_X class is the last class
    $("#parses").on({
	mouseenter: function () {
	    highlightMrsVar(this, mrsVarColorMainHover, mrsVarColorSecondaryHover);
	},
	mouseleave: function () {
	    highlightMrsVar(this, mrsVarColorDefault, mrsVarColorDefault);
	}
    }, ".mrsTable .mrsVar");
    
});
