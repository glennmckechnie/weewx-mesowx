var mesowx = mesowx || {};

mesowx.Util = {
    createDegreeToCardinalTextConverter : function(labels) {
        var numValues = labels.length;
        var interval = 360 / numValues;
        return function(dir) {
            var ordinal = Math.round(dir / interval);
            if(ordinal == numValues) ordinal = 0;
            return labels[ordinal];
        }
    }
};

mesowx.Unit = (function() {

    var Unit = {
        f : new meso.UnitDef('f', '°F'), // fahrenheit
        c : new meso.UnitDef("c", '°C'), // celsius

        inHg : new meso.UnitDef('inHg', 'in'), // inches of mercury
        mb : new meso.UnitDef('mb', 'mb'), // millibar
        hPa : new meso.UnitDef('hPa', 'hPa'), // hectopascal
        kPa : new meso.UnitDef('kPa', 'kPa'), // kilopascal

        in : new meso.UnitDef('in', 'in'), // inches
        mm : new meso.UnitDef("mm", 'mm'), // millimeters
        cm : new meso.UnitDef("cm", 'cm'), // centimeters

        inHr : new meso.UnitDef("inHr", 'in/hr'), // inches per hour
        mmHr : new meso.UnitDef("mmHr", 'mm/hr'), // millimeters per hour
        cmHr : new meso.UnitDef("cmHr", 'cm/hr'), // centimeters per hour

        mph : new meso.UnitDef("mph", 'mph'), // miles per hour
        kph : new meso.UnitDef("kph", 'kph'), // killometers per hour
        knot : new meso.UnitDef("knot", 'knots'),
        mps : new meso.UnitDef("mps", 'mps'), // meters per second

        deg : new meso.UnitDef("deg", '°'), // degrees

        perc : new meso.UnitDef("perc", '%') // percent
    };

    // conversion functions
    Unit.f.convert = to = {};
    to[Unit.c] = function(value) { return 5.0/9.0 * (value-32); };

    Unit.inHg.convert = to = {};
    to[Unit.mb] = function(value) { return value * 33.8637526; };

    Unit.in.convert = to = {};
    to[Unit.mm] = function(value) { return value * 25.4; };
    to[Unit.cm] = function(value) { return value * 2.54; };

    Unit.inHr.convert = to = {};
    to[Unit.mmHr] = function(value) { return value * 25.4; };
    to[Unit.cmHr] = function(value) { return value * 2.54; };

    Unit.mph.convert = to = {};
    to[Unit.kph] = function(value) { return value * 1.609344; };
    to[Unit.knot] = function(value) { return value * 0.868976242; };
    to[Unit.mps] = function(value) { return value * 0.44704; };

    return Unit;
})();
