var mesowx = mesowx || {};

mesowx.RealTimeChart = (function() {

    var RealTimeChart = function(options) {
        this._realTimeDataProvider = options.realTimeDataProvider;
        this._dataSubscription = null;
        meso.AbstractHighstockChart.call(this, options); // call super
    }
    // extend AbstractHighstockChart
    var _super = meso.AbstractHighstockChart.prototype;
    RealTimeChart.prototype = Object.create( _super );

    RealTimeChart.prototype.destroy = function() {
        // unsubscribe from the subscription
        this._dataSubscription.unsubscribe(); 
        _super.destroy.call(this);
    };

    RealTimeChart.prototype._chartReady = function() {
        _super._chartReady.call(this);
        // waiting until chart ready to subscribe to new data
        // XXX this could be improved to gather new data while the chart is loading then add the points here
        // FIXME order of fields is inconsistent betwen providers
        this._dataSubscription = this._realTimeDataProvider.subscribe(
                meso.Util.bind(this, this._onNewData), this._fieldDefs);
    };
    // data is only load once and is not grouped
    RealTimeChart.prototype._buildFetchDataQuery = function(successCallback, fieldDefs, start, end) {
        var query = _super._buildFetchDataQuery.call(this, successCallback, fieldDefs, start, end);
        query.start = {
            value: 1200, // 20 minutes
            type: 'ago'
        };
        return query;
    };
    RealTimeChart.prototype._onNewData = function(data) {
        this._loadChartData([data], true);
    };
    RealTimeChart.prototype._buildChartOptions = function() {
        var chartOptions = _super._buildChartOptions.call(this);
        // these options can't be overriden
        var coreOptions = {
            navigator : {
                // enabling navigator because otherwise chart doesn't redraw when new points are added
                // http://highslide.com/forum/viewtopic.php?uid=12580&f=12&t=16506&start=0
                enabled: true 
            }
        };
        return meso.Util.applyDefaults(coreOptions, chartOptions);
    }

    return RealTimeChart;

})();
