// realtime.js
"use strict";

function append_to_dom(data) {
    $("#jewel_list").empty();
    $("#jewel_list").attr("modified", Date.now());
    var data = JSON.parse(data)
    console.log(data)
    if (data.length == 0) {
        return
    }
    var blocks = data.map(function (jewel) {
        var block = "<div class=nine_columns>";
        block += "<div class='row'><div><span><h5>" + jewel.name + "</h5></span></a></div>";
        block += "<div class='row'><div><span><h5>" + jewel.description + "</h5></span></a></div>";
        const socket_id = jewel.socket_id;
        block += "<div class=focus_mod>" + jewel.focused_mod + "</div>";
        block += "<p>Socketed at " + socket_id + " where it scored " + Number((jewel.score).toFixed(1)) + "</p>";
        block +=  "<div><small>";
        block += jewel.socket_nodes.sort(function(n1, n2){
            return (n1.name[0] < n2.name[0] ) ? -1 : (n1.name[0] > n2.name[0] ) ? 1 : 0;}).map(
              function (node) {
                var node_block = "<div class = node_box>";
                var collapse_div_id = "collapse_" + node.location[0] + node.location[1];

                node_block += "<b><a data-toggle=collapse data-target=#" + collapse_div_id + ">";
                node_block += node.name[0] + "</a></b>";
                node_block += "<div id=" + collapse_div_id + " class=collapse>"
                node_block += node.mods.map(function (mod) {
                            var mod_block = "<div>" + mod + "</div>";

                            return mod_block
                          }).join('');

                node_block += "</div></div>"
                return node_block;
              }).join('');
        block += "</small></div>";
        block += "<div><small>" + "</small></div>";
        var d = new Date(jewel.created.$date);
        block += '<div><small>Reported by ' + jewel.reporter + ' at ' + d + "</small></div>";
        block += '</div></div></div>';
        return block;
    }).join('');
    $("#jewel_list").append(blocks).hide().fadeIn();
    $("#jewel_list").attr("modified", Date.now());
}

function search() {
    $.ajax({
        url: "search",
        data: {
            "search_term": document.getElementById("kw_input").value
        }
    }).done(function (data) {
        append_to_dom(data);
    })
}
