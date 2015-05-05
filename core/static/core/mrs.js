/*
 * Integrated Grammar Development Environment
 * @author: T.J. Trimble
 *
 * mrs.js
 *
 * jQuery for styling and interacting with IgdeMrs HTML representations
 *  
 */

// Constants
var mrsVarColorDefault = "#000000";
var mrsVarColorMainHover = "#FF0000";
var mrsVarColorSecondaryHover = "#33CC33";

// Highlight MRS variable
prefix = "mrsVar_";
function highlightMrsVar(className, color, secondaryColor) {
    if (className.substring(0, prefix.length) == prefix) {
	$("."+className).css("color", color);
	// Check for links
	if (secondaryColor != null) {
	    // Check for handle constraint links and highlight
	    if ($(".hcons ."+ className).siblings(".mrsVar").length > 0) {
		highlightMrsVar($(".hcons ."+ className).siblings(".mrsVar").slice(0).attr("class").split(" ").slice(-1)[0], secondaryColor);
	    }
	    // Check for information constraint links and highlight
	}
    }
}


// Page loader functions
$(document).ready(function() {

    // Assumes correct mrsVar_X class is the last class
    $("#parses").on({
	mouseenter: function () {
	    highlightMrsVar($(this).attr("class").split(" ").slice(-1)[0], mrsVarColorMainHover, mrsVarColorSecondaryHover);
	},
	mouseleave: function () {
	    highlightMrsVar($(this).attr("class").split(" ").slice(-1)[0], mrsVarColorDefault, mrsVarColorDefault);
	}
    }, ".mrsTable p");
    
});