window.ChangeIndicatedValue = (function() {

    var DEFAULT_OPTIONS = {
        container : null,
        decimals : null,
        valueUpCssClass : 'value-up',
        valueDownCssClass : 'value-down',
    };

    var ChangeIndicatedValue = function(options) {
        options = meso.Util.applyDefaults(options, DEFAULT_OPTIONS);

        this._$ = $(options.container);
        this._decimals = options.decimals;
        this._valueUpCssClass = options.valueUpCssClass;
        this._valueDownCssClass = options.valueDownCssClass;
    };
    ChangeIndicatedValue.prototype.setValue = function(newValue) {
        var currValue = this._value;
        if( currValue != newValue ) {
            this._value = newValue;
            var differenceIndex = this._findDifference(currValue, newValue);
            this._updateParts(newValue, differenceIndex, newValue > currValue);
        }
    };
    // find the starting index of the difference
    ChangeIndicatedValue.prototype._findDifference = function(currValue, newValue) {
        if( typeof currValue === 'undefined' ) return -1;
        currValue = this._stringValue(currValue);
        newValue = this._stringValue(newValue);
        var currParts = currValue.split('.');
        var newParts = newValue.split('.');
        // the whole number changed
        if( currParts[0].length != newParts[0].length ) {
            return 0;
        }
        for( var i=0; i<newValue.length; i++ ) {
            if( newValue.charAt(i) !== currValue.charAt(i) ) {
                return i;
            }
        }
    };
    ChangeIndicatedValue.prototype._updateParts = function(value, differenceIndex, valueUp) {
        var valueString = this._stringValue(value);
        // inital value, no indication
        if( differenceIndex === -1 ) {
            this._$.html(valueString);
            return;
        }
        // value update
        this._$.empty();
        var unchanged = valueString.substring(0, differenceIndex);
        var changed = valueString.substring(differenceIndex);
        var text, span;
        // unchanged part
        if( unchanged ) {
            text = document.createTextNode(unchanged);
            span = document.createElement('span');
            span.appendChild(text);
            this._$.append(span);
        }
        // changed part
        text = document.createTextNode(changed);
        span = document.createElement('span');
        span.appendChild(text);
        span.className = valueUp ? this._valueUpCssClass : this._valueDownCssClass;
        this._$.append(span);
    };
    ChangeIndicatedValue.prototype._stringValue = function(value) {
        if(value===null) {
            return "";
        }
        if(this._decimals) {
            return value.toFixed(this._decimals);
        }
        return value.toString();
    };

    return ChangeIndicatedValue;
})();
