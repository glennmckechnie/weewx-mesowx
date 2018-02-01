var mesowx = mesowx || {};

// @Deprecated Really don't like this class, will likely replace it with some UI framework at some point
mesowx.MesoWxConsole = (function() {

    var MesoWxConsole = function(options) {
        meso.MesoConsole.call(this, options); // call super
        this._outTempFieldId = options.outTempFieldId;
        this._heatIndexFieldId = options.heatIndexFieldId;
        this._windChillFieldId = options.windChillFieldId;
        this._rainRateFieldId = options.rainRateFieldId;
        // TODO allow these containers to be configured
        this._rainRateContainer = this._findElement("."+this._rainRateFieldId+'-container');
        this._feelsLikeContainer = this._findElement('.feels-like-container');
    };
    // extend MesoConsole
    var _super = meso.MesoConsole.prototype;
    MesoWxConsole.prototype = Object.create( _super );

    MesoWxConsole.prototype._updateFieldValues = function(fieldValues) {
        // show feels like container if in effect
        var outTemp = fieldValues[this._outTempFieldId];
        var heatIndex = fieldValues[this._heatIndexFieldId];
        var windChill = fieldValues[this._windChillFieldId];
        if(this._feelsLikeContainer) {
            var heatIndexInEffect = heatIndex != null && heatIndex != outTemp;
            var windChillInEffect = windChill != null && windChill != outTemp;
            if(heatIndexInEffect || windChillInEffect) {
                if(heatIndexInEffect) {
                    $(this._fieldValueElements[this._heatIndexFieldId]).show();
                    $(this._fieldValueElements[this._windChillFieldId]).hide();
                }
                if(windChillInEffect) {
                    $(this._fieldValueElements[this._heatIndexFieldId]).hide();
                    $(this._fieldValueElements[this._windChillFieldId]).show();
                }
                $(this._feelsLikeContainer).addClass('active')
            } else {
                $(this._feelsLikeContainer).removeClass('active')
            }
        }
        // hide rain rate when not raining
        if(this._rainRateContainer) {
            var rainRate = fieldValues[this._rainRateFieldId];
            if(rainRate == 0) {
                $(this._rainRateContainer).removeClass('active')
            } else {
                $(this._rainRateContainer).addClass('active');
            }
        }
        // update the values after showing or hiding them
        _super._updateFieldValues.call(this, fieldValues);
    }

    return MesoWxConsole;
})();
