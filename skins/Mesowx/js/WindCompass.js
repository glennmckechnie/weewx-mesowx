// TODO switch methods to be on the prototype
// TODO namespace?
function WindCompass(config) {

    var VIEW_PORT = 100;
    var RADIUS = 90;

    var ORDINAL_TEXT = ["N","NNE", "NE","ENE",
                            "E","ESE","SE","SSE",
                            "S","SSW","SW","WSW",
                            "W","WNW","NW","NNW"];

    function defaultWindDirToCardinalConverter(dir) {
        var ordinal = Math.round(dir / 22.5);
        if( ordinal == 16 ) ordinal = 0;
        return ORDINAL_TEXT[ordinal];
    }

    var DEFAULT_CONFIG = {
        containerId : 'windCompass',
        ticksPerQuad : 8,
        size : null,
        animateDirDuration : 1000,
        maxPrevDirs : 100,
        maxPrevDirOpacity : 1,
        prevDirOpacityEase: d3.ease('sin'),
        tickLength : 10,
        keyFunction : function(d){ return d[0]; },
        dirValueFunction : function(d){ return d[1]; },
        speedValueFunction : function(d){ return d[2]; },
        windSpeedUnitLabel : "mph",
        windDirToCardinalLabelConverterFunction : defaultWindDirToCardinalConverter
    };

    if( !config ) config = DEFAULT_CONFIG;
    else applyDefaults(config, DEFAULT_CONFIG);

    var tickInterval = generateTickPositions(config.ticksPerQuad);
    var prevDirs = [];

    var container = (typeof config.containerId === 'string') ? "#"+config.containerId : config.containerId;

    // default size to the width of the parent container XXX it's not ideal that this is the only need for jquery
    if(!config.size) config.size = $(container).parent().width();

    var compass = d3.select(container)
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
    // speed display
    var speedDisplay = compass.append("text")
        .attr("class", "speedDisplay")
        .attr("dx", "50%") 
        .attr("dy", "50%");
        // speed readout
        speedDisplay
            .append("tspan").attr("class", "speedReadout")
            .text("0");
        // speed suffix
        speedDisplay
            .append("tspan").attr("class", "speedSuffix")
            .text(config.windSpeedUnitLabel);

    var ticks = compass.selectAll(".tick").data(tickInterval)
    ticks.enter().append("path")
        .attr("class", function(d){ 
            var classes = ["tick"];
            if( d%90 == 0 ) classes.push("tick90");
            if( d%45 == 0 ) classes.push("tick45");
            return classes.join(" ");
        })
        .transition().duration(1000)
        .attr("d", "M100 "+(VIEW_PORT-RADIUS)+" L100 "+(VIEW_PORT-RADIUS+config.tickLength))
        // variable length ticks
        /*.attr("d", function(d) {
            var tickLen = 3;
            tickLen *= (d%90==0 ? 2 : 1);
            tickLen *= (d%45==0 ? 2 : 1);
            return "M100 6 L100 "+(6+tickLen)
        })*/
        .attr("transform", function(d){ return "rotate("+d+" 100 100)";});

    this.updateWind = function(val) {

        var data = [val];

        // current direction pointer
        var currDir = compass.selectAll(".currDir")
            .data(data);
        currDir.enter().append("path")
            .attr("class", "currDir")
            .attr("d", "M91 0 L100 9 L109 0 Z");
        currDir
            .transition().duration(config.animateDirDuration)
            .attrTween("transform", function(d,i,a) { 
                return interpolateRotate( a, "rotate("+config.dirValueFunction(d)+" 100 100)" );
            })
            .each(function() {
                // transition ordinal display in tandem
                d3.transition(compass.selectAll(".ordinalDisplay"))
                    .tween("ordinal", function(d,i) {
                        var i = interpolateDegrees(this.getAttribute("rawValue"), config.dirValueFunction(d));
                        return function(t) {
                            var v = i(t);
                            this.setAttribute("rawValue", v);
                            this.textContent = config.windDirToCardinalLabelConverterFunction(v);
                            //this.textContent = Math.round(v);
                        }
                    });
            }) 
            .each('end', function() {
                if( config.maxPrevDirs ) {
                    // update previous dirs
                    prevDirs.push(val);
                    if( prevDirs.length > config.maxPrevDirs ) prevDirs.shift();
                    updatePrevDirs();
                }
            });

        // wind speed display
        var speedReadout = compass.selectAll(".speedReadout")
            .data(data);
        speedReadout
            /*.style("fill", function(d) { 
                var oldVal = this.textContent;
                var newVal = config.speedValueFunction(d);
                if( newVal != oldVal ) return ( newVal > oldVal ? "#00C90D" : "#E00000");
                return null;
            })*/
            .text(function(d){ return Math.round(config.speedValueFunction(d)); });
            /*.classed('value-up', function(d) { 
                var oldVal = this.textContent;
                var newVal = config.speedValueFunction(d);
                return newVal > oldVal;
            })
            .classed('value-down', function(d) { 
                var oldVal = this.textContent;
                var newVal = config.speedValueFunction(d);
                return newVal < oldVal;
            });*/
            /*.transition()
            .duration(1500)
            .style("fill", "#616161");*/

        // ordinal display
        var degreeDisplay = compass.selectAll(".ordinalDisplay")
            .data(data);
        degreeDisplay.enter().append("text")
            .attr("class", "ordinalDisplay")
            .attr("dx", "50%") 
            .attr("dy", "75%")
            .text(function(d){ return config.windDirToCardinalLabelConverterFunction(config.dirValueFunction(d)); });
    }

    this.loadInitialPrevDirs = function(initialPrevDirs) {
        if( !config.maxPrevDirs ) return;
        prevDirs = initialPrevDirs;
        updatePrevDirs();
    }

    function updatePrevDirs() {
        var prevDir = compass.selectAll(".prevDir")
            .data(prevDirs, config.keyFunction);

        prevDir.enter().insert("path", ".currDir")
            .attr("class", "prevDir")
            .attr("d", "M91 0 L100 9 L109 0 Z");

        prevDir
            .attr("transform", function(d,i) { 
                return "rotate("+config.dirValueFunction(d)+" 100 100)";
            })
            .style("fill-opacity", calculatePrevDirOpacity)
            .style("stroke-opacity", calculatePrevDirOpacity);

        prevDir.exit()
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

    var ROTATE_REGEX = /rotate\((\d+\.?\d*)(.*)\)/;

    function interpolateRotate(a, b) {
        var ma = ROTATE_REGEX.exec(a);
        var mb = ROTATE_REGEX.exec(b);
        da = 0;
        db = 0;
        if( ma ) da = ma[1];
        if( mb ) db = mb[1];
        if( da == 0 ) da = 0.000001;
        if( db == 0 ) db = 0.000001;
        return function(t) {
            return "rotate(" + interpolateDegrees(da, db)(t) + mb[2] + ")";
        }
    }
    
    function interpolateDegrees(a, b) {
        if( a==null ) a = 0;
        if( b==null ) b = 0;
        a = parseFloat(a);
        b = parseFloat(b);
        if(a>=0 && a<360 && b>=0 && b<360) {
            if( Math.abs(b-a) > 180 ) {
                return function(t) {
                    var ax, bx;
                    var shift;
                    if( a>b ) {
                        shift = 360 - a;
                        ax = 0;
                        bx = b + shift;
                    } else {
                        shift = 360 - b;
                        bx = 0;
                        ax = a + shift;
                    }
                    var v = d3.interpolateNumber(ax, bx)(t) - shift;
                    if( v < 0 ) v += 360;
                    return v;
                }
            }
            return d3.interpolateNumber(a, b);
        }
    }

    function applyDefaults(config, defaults) {
        for( var prop in defaults ) {
            if( !config.hasOwnProperty(prop) ) config[prop] = defaults[prop];
        }
    }
}
