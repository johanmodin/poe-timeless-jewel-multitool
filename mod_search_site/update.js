"use strict";

function append_to_dom(data) {
    $("#jewel_list").empty();
    $("#jewel_list").attr("modified", Date.now());
    var data = JSON.parse(data)
    if (data.length == 0) {
        return
    }
    var blocks = data.map(function (jewel) {
        var block = "<div class=nine_columns>";
        block += "<div class='row'><div><span><h5>" + jewel.name + "</h5></span></a></div>";
        block += "<div class='row'><div><span><h5>" + jewel.description + "</h5></span></a></div>";
        const socket_id = jewel.socket_id;
        block += jewel.searched_mods.map(function (searched_mod) {
                    return "<div class=focus_mod>" + searched_mod + "</div>";
                  }).join('');
        block += "<p>Socketed at " + socket_id + " with a mod sum of " + jewel.sum + "</p>";
        block +=  "<div><small>";
        block += jewel.socket_nodes.sort(function(n1, n2){
            return (n1.name[0] < n2.name[0] ) ? -1 : (n1.name[0] > n2.name[0] ) ? 1 : 0;}).map(
              function (node) {
                var node_block = "<div class = node_box>";
                var collapse_div_id = "collapse_" + node.location[0] + node.location[1];

                node_block += "<b><a " + collapse_div_id + ">";
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
  var form_struct = $("form#modForm input[type=text]");
  var search_terms = {};
  for (var i=0; i < form_struct.length; i++){
    var term = form_struct[i].value;
    var modID = form_struct[i].id.substring(3, form_struct[i].id.length);

    if (term.length > 0) {
      search_terms[term] = document.getElementById('weight' + modID).value;
    }
  }

    $.ajax({
        url: "search",
        data: {
            "search_terms": JSON.stringify(search_terms)
        }
    }).done(function (data) {
        append_to_dom(data);
    });
}


var counter = 0;
function addInput(divName){
          var newdiv = document.createElement('div');
          newdiv.id = counter;
          newdiv.innerHTML = "<input id='weight" + counter + "'value='1' title='Weight' style='width: 70px' type='number'>\n";
          newdiv.innerHTML += "<input id='mod" + counter + "' type='text' placeholder='Enter mod..' style='width: 435px'><span onClick=removeInput(" + counter + ")>&#9746;</span>";
          document.getElementById(divName).appendChild(newdiv);
          counter++;
}

function removeInput(childName){
  var elem = document.getElementById(childName);
  elem.parentNode.removeChild(elem);
}
