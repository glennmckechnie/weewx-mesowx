var mesowx = mesowx || {};

mesowx.MesoWxWindCompass = (function() {

    var MesoWxWindCompass = function(options) {
        var windCompassConfig = options.windCompassConfig || {};
        windCompassConfig.windSpeedUnitLabel = options.windSpeedFieldDef.unit.labelSuffix;
        this._windCompass = new WindCompass(windCompassConfig);
        // subscribe for data
        options.realTimeDataProvider.subscribe(
            meso.Util.bind(this, this._updateValues),
            [
                options.dateTimeFieldDef,
                options.windDirFieldDef,
                options.windSpeedFieldDef
            ]
        );
    };

    MesoWxWindCompass.prototype._updateValues = function(data) {
        this._windCompass.updateWind(data);
    };

    return MesoWxWindCompass;

})();
