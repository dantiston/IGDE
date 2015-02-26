/*
 * Integrated Grammar Development Environment
 * 
 * On load:
 *     Connect to socket.io server
 *     Listen for message
 *     
 * On message:
 *     Sanitize message
 *     Prepend to list
 * 
 * On send:
 *     Send message to server
 *     Clear input box
 * 
 */

// Page loader
$(document).ready(function(){
    // Connect to server
    var socket = io.connect('localhost', {port: 4000});
    
    socket.on('connect', function(){
        console.log("connect");
    });
    
    // Get element
    var entry_el = $('#comment');

    // On submit, send message to server
    entry_el.keypress(function(event) {

        //When enter is pressed send input value to node server
        if (event.keyCode != 13) return;
	
        var msg = entry_el.prop('value');
        if (msg) {
            socket.emit('send_message', msg, function(data){
                console.log(data);
            });
            //Clear input value
            entry_el.attr('value', '');
        }
    });

    // On message from server, add message to list
    socket.on('message', function(message) {
        // Escape HTML characters
        var data = message.replace(/&/g,"&amp;")
	
        // Append message to the bottom of the list
        $('#parses').prepend(data);
        window.scrollBy(0, -10000000000);
        entry_el.focus();
    });
});
