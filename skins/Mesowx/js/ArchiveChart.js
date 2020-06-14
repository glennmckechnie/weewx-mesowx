var mesowx = mesowx || {};

mesowx.ArchiveChart = (function() {

    var DEFAULT_OPTIONS = {
        lazy : true
    };

    var NON_LAZY_DATA_GROUPING_OPTION = {
        units : [[
            'minute',
            [30]
        ], [
            'hour',
            [1]
        ], [
            'day',
            [1]
        ], [
            'month',
            [1]
        ], [
            'year',
            null
        ]]
    };

    var ArchiveChart = function(options) {
        options = meso.Util.applyDefaults(options, DEFAULT_OPTIONS);
        meso.AbstractHighstockChart.call(this, options); // call super
    }
    // extend WxChart
    var _super = meso.AbstractHighstockChart.prototype;
    ArchiveChart.prototype = Object.create( _super );

    ArchiveChart.prototype._isLazy = function(options) {
        return options.lazy;
    };
    ArchiveChart.prototype._buildSeriesDataGroupingOption = function(readingDef) {
        var groupingOption = _super._buildSeriesDataGroupingOption.call(this, readingDef);
        return meso.Util.applyDefaults(NON_LAZY_DATA_GROUPING_OPTION, groupingOption);
    };
    ArchiveChart.prototype._buildChartOptions = function() {
        var chartOptions = _super._buildChartOptions.call(this);
        // tweak the default options
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

    return ArchiveChart;

})();
