var meso = meso || {};

meso.PollingRealTimeRawDataProvider = (function() {

    var DEFAULT_OPTIONS = {
        pollingInterval : 2000, // 2 seconds
        aggregateDataProvider : null
    }

    var PollingRealTimeRawDataProvider = function(options) {
        meso.AbstractRealTimeRawDataProvider.call(this); // call super

        options = meso.Util.applyDefaults(options, DEFAULT_OPTIONS);
        this._pollingInterval = options.pollingInterval;
        this._aggregateDataProvider = options.aggregateDataProvider;
        this._fieldIndex = {};
        this._dataToRetrieve = [];
        // get things started
        this._poll();
    };
    // extend AbstractRealTimeDataProvider
    var _super = meso.AbstractRealTimeRawDataProvider.prototype;
    PollingRealTimeRawDataProvider.prototype = Object.create( _super );

    PollingRealTimeRawDataProvider.prototype.subscribe = function(callback, desiredData) {
        // TODO need to do the opposite un an unsubscribe
        desiredData.forEach(function(fieldDef) {
            var fieldId = fieldDef.fieldId;
            if(!this._fieldIndex[fieldId]) {
                // create a copy of the FieldDef and ignore the decimals and aggregation
                // we will apply the rounding client-side and there is no aggregation being done
                var newLength = this._dataToRetrieve.push(new meso.FieldDef(fieldId, fieldDef.unit));
                this._fieldIndex[fieldId] = newLength-1;
            }
        }, this);
        return _super.subscribe.call(this, callback, desiredData);
    };

    PollingRealTimeRawDataProvider.prototype._schedulePoll = function(timeout) {
        setTimeout(meso.Util.bind(this, this._poll), timeout)
    };
    PollingRealTimeRawDataProvider.prototype._poll = function() {
        if(this._dataToRetrieve.length != 0) {
            this._aggregateDataProvider.getData({
                data: this._dataToRetrieve,
                order : 'desc',
                limit : 1,
                success : meso.Util.bind(this, this._handleData)
            });
        } else {
            // shorter wait assuming that we'll eventually get some subscribers
            this._schedulePoll(500);
        }
    };
    PollingRealTimeRawDataProvider.prototype._handleData = function(data) {
        this._schedulePoll(this._pollingInterval);
        this._notifySubscribers(data[0]);
    };
    PollingRealTimeRawDataProvider.prototype._adaptData = function(rawData, desiredData) {
        var adapted = desiredData.map(function(fieldDef, index) {
            var dataIndex = this._fieldIndex[fieldDef.fieldId];
            var meta = this._dataToRetrieve[dataIndex];
            var value = rawData[dataIndex];
            if( meta.unit !== fieldDef.unit ) {
                value = meta.unit.convert[fieldDef.unit](value);
            }
            return meso.Util.round(value, fieldDef.decimals);
        }, this);
        return adapted;
    };

    return PollingRealTimeRawDataProvider;

})();
