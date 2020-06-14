var mesowx = mesowx || {};

mesowx.RawChart = (function() {

    var DEFAULT_OPTIONS = {
        lazy : true
    };

    var NON_LAZY_DATA_GROUPING_OPTION = {
        units : [[
            'second',
            [2, 4, 8, 10, 30]
        ], [
            'minute',
            [1, 2]
        ], [
            'hour',
            [1]
        ], [
            'day',
            null
        ]]
    };

    var RawChart = function(options) {
        options = meso.Util.applyDefaults(options, DEFAULT_OPTIONS);
        this._lazy = options.lazy;
        this.numGroups = options.numGroups;
        meso.AbstractHighstockChart.call(this, options); // call super
    }
    // extend AbstractHighstockChart
    var _super = meso.AbstractHighstockChart.prototype;
    RawChart.prototype = Object.create( _super );

    RawChart.prototype._isLazy = function(options) {
        return options.lazy;
    };
    RawChart.prototype._buildSeriesDataGroupingOption = function(readingDef) {
        var groupingOption = _super._buildSeriesDataGroupingOption.call(this, readingDef);
        return meso.Util.applyDefaults(NON_LAZY_DATA_GROUPING_OPTION, groupingOption);
    };
    RawChart.prototype._buildFetchExtremesQuery = function() {
        var query = _super._buildFetchExtremesQuery.call(this);
        query.start = {
            value: 86400,
            type: 'ago'
        };
        return query;
    }
    RawChart.prototype._buildChartOptions = function() {
        var chartOptions = _super._buildChartOptions.call(this);
        // these options can't be overriden
        var coreOptions = {
            chart : {
                zoomType : 'x'
            },
            navigator : {
                enabled: true, // can't get it to work properly without this enabled, zooming out/panning in particular
                adaptToUpdatedData : false
            }
        }
        return meso.Util.applyDefaults(coreOptions, chartOptions);
    }

    return RawChart;

})();
