var meso = meso || {};

meso.Util = {
    applyDefaults : function(options, defaults) {
        return $.extend(true, {}, defaults, options);
    },
    round : function(value, digits) {
        if(value===null) return null;
        var multiple = Math.pow(10, digits);
        return Math.round(value * multiple) / multiple;
    },
    bind : function(context, callback) {
        return function() {
            callback.apply(context, arguments);
        };
    },
    index : function(array, indexProperty) {
        var propertyIndex = {};
        array.forEach( function(item, index) {
            if( indexProperty ) {
                propertyIndex[item[indexProperty]] = index;
            } else {
                propertyIndex[item] = index;
            }
        });
        return propertyIndex;
    }
}

meso.Agg = {
    avg : "avg",
    min : "min",
    max : "max",
    sum : "sum"
};

meso.Stat = {
    min : "min",
    max : "max"
};

meso.FieldDef = (function() {
    var FieldDef = function(fieldId, unit, decimals, agg, label) {
        this.fieldId = fieldId;
        this.unit = unit;
        this.decimals = decimals;
        this.agg = agg;
        this.label = label;
    }

    FieldDef.prototype.toString = function() {
        return this.fieldId;
    }

    return FieldDef;
})();

meso.UnitDef = (function() {
    var UnitDef = function(urlParam, labelSuffix) {
        // TODO rename to unitId
        this.urlParam = urlParam;
        this.labelSuffix = labelSuffix;
        this.convert = null;
    }

    UnitDef.prototype.toString = function() {
        return this.urlParam;
    }

    return UnitDef;
})();

// core units
meso.Unit = (function() {

    var Unit = {
        s : new meso.UnitDef("s", 's'), // seconds
        ms : new meso.UnitDef("ms", 'ms') // milliseconds
    };

    // converstion functions
    Unit.s.convert = to = {};
    to[Unit.ms] = function(value) { return value * 1000; };

    return Unit;
})();
