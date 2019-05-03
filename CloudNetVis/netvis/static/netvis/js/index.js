$(document).ready(function() {   
    select_pid(); 
});

function select_pid() {
    $.ajax({
        url: '/jsonet/',
        data: {},
        dataType: 'json',
        success: function (data) {    
            var traffic_matrix = JSON.parse(data.traffic_matrix);
            let graph = new StaticGraph(traffic_matrix, "#graph");  
        }
    });
}
 


