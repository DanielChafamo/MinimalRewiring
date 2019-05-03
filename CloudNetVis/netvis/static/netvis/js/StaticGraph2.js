class StaticGraph {
    constructor(graph, div_id) { 
        var SG = this;
        this.graph = graph; 
        this.width = $(div_id).width();
        this.height = $(div_id).height(); 
        this.count = 0;
        this.limit = 500;
        this.node_size = 10;
        this.link_length = 20;
        this.link_width = 2;
        this.node_color = 'white';
        this.link_color = 'blue';
        this.spread_strength = -300; 

        // compute host location
        var bottom = this.height/2 - 140,
            left = -this.width/2 + 40,  
            spacing = [.8,1.5, 1.5, 2];
        // fix 
        for (let node of this.graph.nodes) {  
            node.ffx = (node.horiz - this.graph.counts[node.vert]/2 +.5)*70*spacing[node.vert];
            node.ffy = bottom - node.vert*node.vert*50;
            console.log(node.ffx, node.ffy); 
        };
        this.svg = d3.select(div_id).append("svg")
            .attr("id", 'svg'+div_id)
            .attr("width", this.width)
            .attr("height", this.height);  

        var g = this.svg.append("g")
            .attr("transform", "translate(" + this.width / 2 + "," + this.height / 2 + ")");

        this.link = g.append("g") 
            .selectAll(".link")
            .data(this.graph.links, function(d) { return d.source.id + "-" + d.target.id; })
            .enter().append("line") 
            .style("stroke", function (d) { return SG.link_color;})
            .style("stroke-width", function (d) { return SG.link_width*d.weight*d.weight;}); 

        this.node = g.append("g")
            .attr("stroke", "black")
            .attr("stroke-width", 3)
            .selectAll(".node")
            .data(this.graph.nodes) //.filter(n=>n.vert > 0))
            .enter().append("circle")
            .style("fill", function (d) { return SG.node_color;})
            .style("r", function (d) { return SG.node_size;});

        this.simulation = d3.forceSimulation(this.graph.nodes)
            .force("charge", d3.forceManyBody().strength(SG.spread_strength))
            .force("link", d3.forceLink(this.graph.links).distance(SG.link_length))
            .force("x", d3.forceX())
            .force("y", d3.forceY())
            .alphaTarget(0.4)
            .alphaDecay(0.05)
            .on("tick", function () {this.ticked();}.bind(this));
    } 

    ticked() {
        if (this.count >= this.limit) { return; }
        else {this.count += 1;} 

        this.node.attr("r", function(d) {if (d.vert!=5) {d.x=d.ffx; d.y=d.ffy;}}); 

        this.node.attr("cx", function(d) { return d.x; })
                 .attr("cy", function(d) { return d.y; });

        this.link.attr("x1", function(d) { return d.source.x; })
                 .attr("y1", function(d) { return d.source.y; })
                 .attr("x2", function(d) { return d.target.x; })
                 .attr("y2", function(d) { return d.target.y; });
    }


}