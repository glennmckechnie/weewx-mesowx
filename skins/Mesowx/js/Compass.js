function Compass(containerId, config) {

    var ORDINAL_TEXT = ["N","NNE", "NE","ENE",
                            "E","ESE","SE","SSE",
                            "S","SSW","SW","WSW",
                            "W","WNW","NW","NNW"];

    var VIEW_PORT = 100;
    var RADIUS = 90;

    var DEFAULT_CONFIG = {
        ticksPerQuad : 8,
        size : 100,
        initialPrevDirs : [],
        animateDirDuration : 1200,
        maxPrevDirs : 100,
        maxPrevDirOpacity : 1,
        prevDirOpacityEase: d3.ease('sin'),
        tickLength : 10,
        keyFunction : function(d){ return d[0]; },
        valueFunction : function(d){ return d[1]; }
    };

    if( !config ) config = DEFAULT_CONFIG;
    else applyDefaults(config, DEFAULT_CONFIG);

    console.log(config);

    var tickInterval = generateTickPositions(config.ticksPerQuad);
    var prevDirs = config.initialPrevDirs;//.slice(0);

    var compass = d3.select("#"+containerId)
        .append("svg:svg")
        .attr("width", config.size)
        .attr("height", config.size)
        .attr("viewBox", "0 0 200 200");
    // compass edge
    compass.append("svg:circle")
        .attr("class", "edge")
        .attr("cx", "50%")
        .attr("cy", "50%")
        .attr("r", RADIUS);

    var ticks = compass.selectAll("#"+containerId+" .tick").data(tickInterval)
    ticks.enter().append("path")
        .attr("class", function(d){ 
            var classes = ["tick"];
            if( d%90 == 0 ) classes.push("tick90");
            if( d%45 == 0 ) classes.push("tick45");
            return classes.join(" ");
        })
        .transition().duration(1000)
        .attr("d", "M100 "+(VIEW_PORT-RADIUS)+" L100 "+(VIEW_PORT-RADIUS+config.tickLength))
        /*.attr("d", function(d) {
            var tickLen = 3;
            tickLen *= (d%90==0 ? 2 : 1);
            tickLen *= (d%45==0 ? 2 : 1);
            return "M100 6 L100 "+(6+tickLen)
        })*/
        .attr("transform", function(d){ return "rotate("+d+" 100 100)";});

    this.updateDir = function(val) {

        var data = [val];

        // current direction pointer
        var currDir = compass.selectAll("#"+containerId+" .currDir")
            .data(data);
        currDir.enter().append("path")
            .attr("class", "currDir")
            .attr("d", "M91 0 L100 9 L109 0 Z");
        currDir.transition()
            .duration(config.animateDirDuration)
            .attrTween("transform", function(d,i,a) { 
                return d3.interpolateString( a, "rotate("+config.valueFunction(d)+" 100 100)" );
            })
            .each(function() {
                // transition ordinal display in tandem
                d3.transition(compass.selectAll("#"+containerId+" .ordinalDisplay"))
                    .tween("ordinal", function(d,i) {
                        var i = d3.interpolate(this.getAttribute("rawValue"), config.valueFunction(d));
                        return function(t) {
                            var v = i(t);
                            this.setAttribute("rawValue", v);
                            this.textContent = windDirToCardinal(v);
                        }
                    });
                    //.text(function(d){ return windcurrDirToCardinal(d); });
                // transition degree display in tandem
                d3.transition(compass.selectAll("#"+containerId+" .degreeDisplay"))
                    .tween("degree", function(d,i) {
                        var i = d3.interpolate(this.textContent, config.valueFunction(d));
                        return function(t) {
                            var v = i(t);
                            this.textContent = Math.round(v) + "°";
                        }
                    });
            }) 
            .each('end', function() {
                // update previous dirs
                prevDirs.push(val);
                if( prevDirs.length > config.maxPrevDirs ) prevDirs.shift();
                updatePrevDirs();
            });

        // ordinal display
        var ordinalDisplay = compass.selectAll("#"+containerId+" .ordinalDisplay")
            .data(data);
        ordinalDisplay.enter().append("text")
            .attr("class", "ordinalDisplay")
            .attr("dx", "50%") 
            .attr("dy", "50%")
            .text(function(d){ return windDirToCardinal(config.valueFunction(d)); });

        // degree display
        var degreeDisplay = compass.selectAll("#"+containerId+" .degreeDisplay")
            .data(data);
        degreeDisplay.enter().append("text")
            .attr("class", "degreeDisplay")
            .attr("dx", "50%") 
            .attr("dy", "75%")
            .text(function(d){ return Math.round(config.valueFunction(d)) + "°"; });
    }

    // initialize
    if( prevDirs.length ) {
        var latestDir = prevDirs.pop();
        this.updateDir(latestDir);
        updatePrevDirs();
    }

    function updatePrevDirs() {
        var prevDir = compass.selectAll("#"+containerId+" .prevDir")
            .data(prevDirs, config.keyFunction);

        prevDir.enter().insert("path", ".currDir")
            .attr("class", "prevDir")
            .attr("d", "M91 0 L100 9 L109 0 Z");

        prevDir
            .attr("transform", function(d,i) { 
                return "rotate("+config.valueFunction(d)+" 100 100)";
            })
            .transition().duration(config.animateDirDuration)
            .style("fill-opacity", calculatePrevDirOpacity)
            .style("stroke-opacity", calculatePrevDirOpacity);

        prevDir.exit()
            .transition().duration(config.animateDirDuration)
            .style("fill-opacity", 0)
            .style("stroke-opacity", 0)
            .remove();
    }

    function calculatePrevDirOpacity(d,i) {
        return config.prevDirOpacityEase((i+1)/prevDirs.length) * config.maxPrevDirOpacity;
    }

    function generateTickPositions(ticksPerQuad) {
        var positions = [];
        var tickInterval = 360 / 4 / ticksPerQuad;
        for( var q=0; q<360; q+=tickInterval ) {
            positions.push(q);
        }
        return positions;
    }

    function windDirToCardinal(dir) {
        var ordinal = Math.round(dir / 22.5);
        if( ordinal > 15 ) ordinal = 15;
        return ORDINAL_TEXT[ordinal];
    }

    function applyDefaults(config, defaults) {
        for( var prop in defaults ) {
            if( !config.hasOwnProperty(prop) ) config[prop] = defaults[prop];
        }
    }
}
