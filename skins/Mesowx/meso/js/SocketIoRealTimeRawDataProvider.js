var meso = meso || {};

meso.SocketIoRealTimeRawDataProvider = (function() {

    var SocketIoRealTimeRawDataProvider = function(options) {
        meso.AbstractRealTimeRawDataProvider.call(this); // call super

        this._providedFields = options.providedFields;
        for(var field in this._providedFields) {
            var providedField = this._providedFields[field];
            if(!providedField.index) providedField.index = field;
        }
        this._socket = options.socketioConnection;
        this._socket.on(options.messageName, meso.Util.bind(this, this._handleIoData));
    };
    // extend AbstractRealTimeDataProvider
    var _super = meso.AbstractRealTimeRawDataProvider.prototype;
    SocketIoRealTimeRawDataProvider.prototype = Object.create( _super );

    SocketIoRealTimeRawDataProvider.prototype._handleIoData = function(ioData) {
        this._notifySubscribers(ioData);
    };
    SocketIoRealTimeRawDataProvider.prototype._adaptData = function(rawData, desiredData) {
        var adapted = desiredData.map(function(fieldDef) {
            var meta = this._providedFields[fieldDef.fieldId];
            var value = rawData[meta.index];
            if( meta.unit !== fieldDef.unit ) {
                value = meta.unit.convert[fieldDef.unit](value);
            }
            return meso.Util.round(value, fieldDef.decimals);
        }, this);
        return adapted;
    };

    return SocketIoRealTimeRawDataProvider;

})();

// example configuration

    /*Config.realTimeDataProvider = new meso.SocketIoRealTimeRawDataProvider({
        socketioConnection : io.connect('http://wx.ruskers.com:8888/'),
        messageName : "rawwx",
        providedFields: {
            "dateTime" : { index: "dateTime", unit: wx.Unit.s },
            "outTemp" : { index: "outTemp", unit: wx.Unit.f },
            "dewpoint" : { index: "dewpoint", unit: wx.Unit.f },
            "rainRate" : { index: "rainRate", unit: wx.Unit.inHr },
            "dayRain" : { index: "dayRain", unit: wx.Unit.in },
            "windSpeed" : { index: "windSpeed", unit: wx.Unit.mph },
            "windDir" : { index: "windDir", unit: wx.Unit.deg },
            "outHumidity" : { index: "outHumidity", unit: wx.Unit.perc },
            "barometer" : { index: "barometer", unit: wx.Unit.inHg },
            "windchill" : { index: "windchill", unit: wx.Unit.f },
            "heatindex" : { index: "heatindex", unit: wx.Unit.f },
            "inTemp" : { index: "inTemp", unit: wx.Unit.f },
            "inHumidity" : { index: "inHumidity", unit: wx.Unit.perc },
        }
    });*/
