var meso = meso || {};

meso.AbstractHighstockChart = (function() {

    var DEFAULT_OPTIONS = {
        // This defines the groupings that the data is will be potentially grouped into. The interval 
        // will be chosen dynamically based on the selected range, the available space, and the 
        // groupPixelWidth setting.
        // Note: this uses the same API and defaults as Highstock, see
        // http://api.highcharts.com/highstock#plotOptions.area.dataGrouping.units
        allowedGroupIntervals: {
            'millisecond' : [1, 2, 5, 10, 20, 25, 50, 100, 200, 500],
            'second' :      [1, 2, 5, 10, 15, 30],
            'minute' :      [1, 2, 5, 10, 15, 30],
            'hour' :        [1, 2, 3, 4, 6, 8, 12],
            'day' :         [1],
            'week' :        [1],
            'month' :       [1, 3, 6],
            'year' :        null
        },
        // The date time label formats to use when displaying the aggregated and non-aggregated
        // times of a point (e.g. the tooltip). Each interval defines an array of 3
        // formats, the first defining the format for when the data is either not aggregated
        // or the aggregated interval is 1, the second and third are the beginning and end
        // format when the point is aggregated (other than 1) and will be concatenated together.
        // Note: this uses the same API and defaults as Highstock, see 
        // http://api.highcharts.com/highstock#plotOptions.series.dataGrouping.dateTimeLabelFormats
        groupDateTimeLabelFormats: {
           millisecond: ['%A, %b %e, %H:%M:%S.%L', '%A, %b %e, %H:%M:%S.%L', '-%H:%M:%S.%L'],
           second: ['%A, %b %e, %H:%M:%S', '%A, %b %e, %H:%M:%S', '-%H:%M:%S'],
           minute: ['%A, %b %e, %H:%M', '%A, %b %e, %H:%M', '-%H:%M'],
           hour: ['%A, %b %e, %H:%M', '%A, %b %e, %H:%M', '-%H:%M'],
           day: ['%A, %b %e, %Y', '%A, %b %e', '-%A, %b %e, %Y'],
           week: ['Week from %A, %b %e, %Y', '%A, %b %e', '-%A, %b %e, %Y'],
           month: ['%B %Y', '%B', '-%B %Y'],
           year: ['%Y', '%Y', '-%Y']
        },
        // This controls the horizontal pixel density of the chart when aggregating. This value
        // divided from the number of available horizontal pixels in the chart render area will
        // be used to calculate the number of groups to request in the data.
        // Note: value doesn't need to be a whole number
        // Note: this is similar to the Highstock setting of the same name
        // http://api.highcharts.com/highstock#plotOptions.area.dataGrouping.groupPixelWidth
        groupPixelWidth: 1.5,
        // The approximate interval of the actual data in milliseconds. The value doesn't have to be 
        // exact if the data is irregular, but should be close otherwise it could result in loading 
        // more data than will fit on the chart, as this controls the point at which data will be 
        // requested in raw form instead of aggregated (i.e. when the chart has been zoomed
        // in far enough that there are less than two raw data points per group). Setting this
        // is optional, but if unset the data will never request the data in raw form (i.e. it will 
        // always be aggregated even if each group only consists of an aggregation of 1 row).
        // XXX don't love this solution to this problem, is there a better way?
        dataInterval: null,
        // The maximum range of the chart that stats will be loaded for in milliseconds. If unspecified/null 
        // there will be no limit. This parameter exists for larger data sets where calculating the stats
        // takes too long to be usable.
        // XXX don't like this parameter either, caching of stats on the server could help eliminate 
        // the need for this, or perhaps the total number of data points could be calculated ahead of time
        // along with the extremes query?
        maxStatRange: null
    };

    //////////////// constructor
    var AbstractHighstockChart = function(options) {
        this.options = this._applyDefaultOptions(options);
        this._lazy = this._isLazy(this.options);
        this._aggregateDataProvider = this.options.aggregateDataProvider;
        this._statsDataProvider = this.options.statsDataProvider;
        this._dataInterval = this.options.dataInterval;
        this._maxStatRange = this.options.maxStatRange;
        this._dateTimeField = this.options.xAxis.field;
        this._dateTimeFieldDef = new meso.FieldDef(this._dateTimeField, meso.Unit.ms, 0, null);
        this._groupDateTimeLabelFormats = this.options.groupDateTimeLabelFormats;
        // the series on each axis
        this.axisSeries = {};
        this.options.series.forEach(function(series, index) {
            var seriesAxisId = series.axis;
            if( !seriesAxisId ) {
                throw new Error("Series at index "+index+" has no 'axis' defined");
            }
            var axisSeriesList = this.axisSeries[seriesAxisId];
            if(!axisSeriesList) {
                axisSeriesList = [];
                this.axisSeries[seriesAxisId] = axisSeriesList;
            }
            axisSeriesList.push(series);
        }, this);
        // the fields that will be fetched in the data query
        this._fieldDefs = this._buildFieldDefs(this.options);
        this._fieldIds = [];
        // array of the field ID of each series (in order in field defs)
        this._fieldDefs.forEach(function(fieldDef) {
            if(fieldDef.fieldId != this._dateTimeField) {
                this._fieldIds.push(fieldDef.fieldId);
            }
        }, this);

        // build the stats query data parameter ahead of time as it won't ever change
        this._statsQueryDataParam = this._buildStatsQueryDataParam(this.options.series);

        this._groupIntervalsIndex = this._buildGroupIntervalsIndex(this.options.allowedGroupIntervals);

        this.chart = null;
        this._chartInitialized = false;
        this._dataLoading = false;
        this._chartData = {};
        this._runAfterDataLoadedQueue = [];
        // the grouping interval used when fetching the current data
        this._currentGroupingInterval = null;
        // the average data interval, calculated by dividing the number of points in the data
        // from the selected time range after each time new data is loaded
        this._calculatedDataInterval = null;
        // best guess as to whether or not the data is actually aggregated (i.e. matches the
        // requested/expected aggregation), note that this may or may not be entirely reliable
        // see _isDataAggregated() for details
        this._currentDataAggregated = null;
        // the currently selected/displayed range of the chart as an array with the first value 
        // the min time and the second value the max time in milliseconds
        this.currentDataRange = null;

        this._create();
    }

    /////////////// public
    AbstractHighstockChart.prototype.destroy = function() {
        if(this.chart) {
            this.chart.destroy();
        }
    };

    /////////////// protected
    AbstractHighstockChart.prototype._applyDefaultOptions = function(options) {
        return meso.Util.applyDefaults(options, DEFAULT_OPTIONS);
    };

    AbstractHighstockChart.prototype._fetchData = function(resultCallback, start, end, fieldDefs) {
        if(!fieldDefs) {
            fieldDefs = this._fieldDefs;
        }
        this._currentGroupingInterval = this._determineChartGroupingInterval(start, end);
        var query = this._buildFetchDataQuery(resultCallback, fieldDefs, start, end);
        this._aggregateDataProvider.getData(query);
    };

    // create an index of each of the allowed group intervals indexed by the milliseconds of each
    AbstractHighstockChart.prototype._buildGroupIntervalsIndex = function(groupIntervals) {
        var index = [];
        for(var unit in groupIntervals) {
            var intervals = groupIntervals[unit];
            if(intervals) {
                intervals.forEach(function(interval) {
                    var intervalUnitDef = INTERVAL[unit];
                    var intervalMs = interval * intervalUnitDef.ms;
                    var intervalMinMs = null;
                    var intervalMaxMs = null;
                    if(intervalUnitDef.minMs && intervalUnitDef.maxMs) {
                        intervalMinMs = interval * intervalUnitDef.minMs;
                        intervalMaxMs = interval * intervalUnitDef.maxMs;
                    }
                    index.push({ 
                        unit: unit, 
                        interval: interval,
                        ms: intervalMs, 
                        minMs: intervalMinMs,
                        maxMs: intervalMaxMs
                    });
                });
            }
        }
        return index;
    };

    AbstractHighstockChart.prototype._buildFetchDataQuery = function(resultCallback, fieldDefs, start, end) {
        var groupParam = null;
        if(this._lazy) {
            var groupParam = this._buildDataQueryGroupParamForGroupInterval(this._currentGroupingInterval); 
            // if the chart is lazy, but we're not grouping, add dateTime as the first field
            // this is because the dateTime field is only automatically added when grouping
            if(!groupParam) {
                fieldDefs = fieldDefs.slice()
                fieldDefs.splice(0, 0, this._dateTimeFieldDef);
            }
        }
        var query = {
            success: resultCallback,
            data: fieldDefs
        };
        if(groupParam) {
            query.group = groupParam;
        }
        if(start) {
            query.start = {
                value: Math.round(start / 1000),
                type: 'datetime'
            };
        }
        if(end) {
            query.end = {
                value: Math.round(end / 1000),
                type: 'datetime'
            };
        }
        return query;
    };

    AbstractHighstockChart.prototype._determineChartGroupingInterval = function(start, end) {

        if(this._lazy) {
            var range = end - start;
            var numGroups = this.chart.plotSizeX / this.options.groupPixelWidth;
            targetGroupIntervalMs = Math.round(range / numGroups);

            var groupInterval = this._findNearestAllowedGroupInterval(targetGroupIntervalMs);
            if(!groupInterval) {
                // if no allowed grouping interval found (either none configured or no interval large enough found)
                // just default to the target interval
                groupInterval = {
                    interval: targetGroupIntervalMs,
                    ms: targetGroupIntervalMs,
                    unit: "millisecond"
                };
            }

            if(groupInterval.ms > this._dataInterval) {
                return groupInterval;
            }
        }

        // returning null will result in no grouping
        return null;
    };

    AbstractHighstockChart.prototype._buildDataQueryGroupParamForGroupInterval = function(groupInterval) {
        var group = {
            unit: meso.Unit.ms
        }
        if(groupInterval.unit == 'millisecond') {
            // grouping by milliseconds isn't currently supported by the API, so converting
            // to seconds for now
            // TODO the API should be updated to support milliseconds
            // for now, just don't group
            group = null;
        } else if(groupInterval.unit == 'second') {
            group.type = 'seconds';
            group.value = groupInterval.interval;
        } else if(groupInterval.unit == 'second') {
            group.type = 'seconds';
            group.value = groupInterval.interval;
        } else if(groupInterval.unit == 'minute') {
            group.type = 'seconds';
            group.value = groupInterval.interval * 60;
        } else if(groupInterval.unit == 'hour') {
            group.type = 'seconds';
            group.value = groupInterval.interval * 3600;
        } else if(groupInterval.unit == 'day') {
            group.type = 'days';
            group.value = groupInterval.interval;
        } else if(groupInterval.unit == 'week') {
            group.type = 'days';
            group.value = groupInterval.interval * 7;
        } else if(groupInterval.unit == 'month') {
            group.type = 'months';
            group.value = groupInterval.interval;
        } else if(groupInterval.unit == 'year') {
            group.type = 'years';
            group.value = groupInterval.interval;
        }
        return group;
    };

    AbstractHighstockChart.prototype._findNearestAllowedGroupInterval = function(targetInterval) {
        for(var i=0; i<this._groupIntervalsIndex.length; i++) {
            var groupInterval = this._groupIntervalsIndex[i];
            if(groupInterval.ms >= targetGroupIntervalMs) {
                return groupInterval;
            }
        }
        return null;
    };

    // override to enable lazy mode
    AbstractHighstockChart.prototype._isLazy = function(options) {
        return false;
    };

    AbstractHighstockChart.prototype._buildFieldDefs = function(options) {
        var fieldDefs = [];
        if(!this._lazy) {
            // if the chart isn't lazy (i.e. not grouping), then the dateTime field must be added as the first returned column
            fieldDefs.push(this._dateTimeFieldDef);
        }
        options.yAxes.forEach(function(axis) {
            var axisUnit = axis.unit;
            // each seires on the axis
            this.axisSeries[axis.axisId].forEach(function(series) {
                fieldDefs.push(
                    meso.Util.applyDefaults({
                        unit: axisUnit // ignore the unit and use the axis unit, since they must match
                    }, series.fieldDef)
                );
            }, this);
        }, this);
        return fieldDefs;
    }

    AbstractHighstockChart.prototype._create = function() {
        this._loadInitialDataAndCreate();
    };

    AbstractHighstockChart.prototype._loadInitialDataAndCreate = function() {
        // if lazy, there's an additional step to load the chart extremes first, otherwise we just load the chart data
        if( this._lazy ) {
            var query = this._buildFetchExtremesQuery();
            this._aggregateDataProvider.getData(query);
        } else {
            this._fetchData(meso.Util.bind(this, this._handleInitialLoad));
        }
    }

    // fetch the min and max datetime for the entire chart, then create the chart with these two points, 
    // and finally load the default selected range; this prevents the need to load the full chart data
    // initially
    AbstractHighstockChart.prototype._buildFetchExtremesQuery = function() {
        var query = {
            success: meso.Util.bind(this, this._handleExtremesLoad),
            data: [{
               fieldId: this._dateTimeField,
               agg: meso.Agg.min,
               unit: meso.Unit.ms
            }, {
               fieldId: this._dateTimeField,
               agg: meso.Agg.max,
               unit: meso.Unit.ms
            }],
            group: {
                value: 1,
                type: 'groups'
            }
        };
        return query;
    };

    AbstractHighstockChart.prototype._handleExtremesLoad = function(data) {
        var min = data[0][0];
        var max = data[0][1];
        // reshape the response into two "rows"
        this._handleInitialLoad([[min], [max]]);
        // this triggers the actual data load for the default selected range
        this._triggerInitialLoad();
        // also load the navigator series data, otherwise it'll always be empty
        this._loadNavigatorData(min, max);
    };

    AbstractHighstockChart.prototype._loadNavigatorData = function(min, max) {
        // TODO make this configurable - try to determine from the highcharts navigator options?
        var navigatorFieldDef = this.options.series[0].fieldDef;
        fieldDefs = [
            navigatorFieldDef
        ];
        this._fetchData(meso.Util.bind(this, this._handleNavigatorDataLoad), min, max, fieldDefs);
    };

    AbstractHighstockChart.prototype._fetchStatsData = function(resultCallback, start, end) {
        if(this._statsDataProvider) {
            var query = this._buildStatsQuery(resultCallback, start, end);
            this._statsDataProvider.getStats(query);
        }
    };

    AbstractHighstockChart.prototype._buildStatsQuery = function(resultCallback, start, end) {
        var query = {
            success: resultCallback,
            timeUnit: meso.Unit.ms.urlParam,
            start: start,
            end: end,
            data: this._statsQueryDataParam
        };
        return query;
    }

    AbstractHighstockChart.prototype._buildStatsQueryDataParam = function(allSeries) {
        var dataParam = [];
        allSeries.forEach(function(series) {
            if(series.stats && series.stats.length !== 0) {
                dataParam.push({
                    fieldId: series.fieldDef.fieldId,
                    unit: series.fieldDef.unit.urlParam,
                    decimals: series.fieldDef.decimals,
                    stats: series.stats
                });
            }
        })
        return dataParam;
    };

    AbstractHighstockChart.prototype._handleInitialLoad = function(data) {
        this._loadChartData(data);
        this._createChart();
    };

    AbstractHighstockChart.prototype._loadChartData = function(data, append) {
        // initialize the data
        if(!append) {
            this._fieldIds.forEach(function(fieldId, index) {
                this._chartData[fieldId] = [];
            }, this);
        }
        // load the data
        var row, dateTime, point, series;
        data.forEach(function(row) {
            dateTime = row[DATE_TIME_INDEX];
            this._fieldIds.forEach(function(fieldId, index) {
                var value = row[index+1]; // values index starts after the dateTime index
                // default the value to null if not included in the data
                if(typeof value === 'undefined') value = null;
                point = [dateTime, value];
                if(!append) {
                    this._chartData[fieldId].push(point);
                } else {
                    this.chart.get(fieldId).addPoint(point, 
                            false, // don't redraw
                            true,  // shift series data
                            false); // don't animate
                }
            }, this);
        }, this);
        // if the chart has been initialized then we need to reset the data on each series
        if(this._chartInitialized) {
            this._fieldIds.forEach(function(fieldId, index) {
                this.chart.get(fieldId).setData(
                        this._chartData[fieldId], 
                        false); // false = don't redraw
            }, this);
            // clear the stats flags - this prevents the chart from not shifting if there are stats flags on the far edge
            // XXX is there a better solution? perhaps just remove the flags on the far edge? or wait to update both the series data and flags at the same time
            this._clearStatsFlags(); 
        }
        // redraw the chart at the end if it has been created
        if(this.chart) {
            this.chart.redraw();
        }
    };

    AbstractHighstockChart.prototype._analyzeData = function(data) {
        this._calculatedDataInterval = this._calculateDataInterval(data);
        this._currentDataAggregated = this._isDataAggregated(data);
    };

    AbstractHighstockChart.prototype._calculateDataInterval = function(data) {
        var dataInterval = null;
        if(data && data.length > 1) {
            var startIndex = 0;
            var endIndex = data.length-1;
            var minX = data[startIndex][DATE_TIME_INDEX];
            var maxX = data[endIndex][DATE_TIME_INDEX];
            var range = maxX - minX;
            dataInterval = range / (endIndex-startIndex);
        }
        return dataInterval;
    }

    AbstractHighstockChart.prototype._createChart = function() {
        var chartOptions = this._buildChartOptions();
        this.chart = new Highcharts.StockChart(chartOptions);
    };

    AbstractHighstockChart.prototype.getXAxisExtremes = function() {
        return this.chart.xAxis[0].getExtremes();
    };

    AbstractHighstockChart.prototype._triggerInitialLoad = function() {
        var currentExtremes = this.getXAxisExtremes();
        // min & max will be the currently selected range
        this._loadData(currentExtremes.min, currentExtremes.max);
    };
    
    AbstractHighstockChart.prototype._handleNavigatorDataLoad = function(data) {
        this.chart.get('__NAVIGATOR__').setData(data);
    };

    AbstractHighstockChart.prototype._chartReady = function() {
        this._chartInitialized = true;
    };

    AbstractHighstockChart.prototype._onSetExtremes = function(e) {
        var min = e.min;
        var max = e.max;
        // XXX not sure if this is highcharts bug or not, but if a zoom selection is made on a chart
        // where there is no data point or to the edge of the chart, the min/max value could be 
        // undefined. so for now if this occurs, just default to the values to the current extreme 
        // values of the axis. this could be fixed in a future Highcharts version making this unecessary
        if(typeof min === 'undefined') {
            min = this.getXAxisExtremes().min;
        }
        if(typeof max === 'undefined') {
            max = this.getXAxisExtremes().max;
        }
        this._loadData(min, max);
    };

    AbstractHighstockChart.prototype._loadData = function(min, max) {
        this.currentDataRange = [min, max];
        if(this._lazy) {
            this._loadDataLazy(min, max);
        }
        // TODO implement stats calculation client-side for non-lazy charts, until then always load lazily
        this._loadStatsDataLazy(min, max);
    };
    
    AbstractHighstockChart.prototype._loadStatsDataLazy = function(min, max) {
        // don't load the stats if the range exceeds the max
        if(this._maxStatRange && (max - min) > this._maxStatRange) {
            return;
        }
        var startRange = this.currentDataRange;
        // wrap the handler to create a closure around the current data range to make sure that the rnage 
        // hadn't changed in the time that it took for the stats to return; if this does occur, simply
        // ignore it
        var handleStatsLoadWrapper = function(data) {
            if(startRange === this.currentDataRange) {
                this._handleStatsLoad(data);
            }
        };
        this._fetchStatsData(meso.Util.bind(this, handleStatsLoadWrapper), min, max);
    };

    AbstractHighstockChart.prototype._loadDataLazy = function(min, max) {
        this._dataLoading = true;
        this.chart.showLoading('Loading...');
        this._fetchData( meso.Util.bind(this, this._handleLazyLoad), min, max );
    };

    AbstractHighstockChart.prototype._handleLazyLoad = function(data) {
        this._loadChartData(data);
        this._loadComplete();
        this._analyzeData(data);
    };

    AbstractHighstockChart.prototype._loadComplete = function() {
        this.chart.hideLoading();
        this._dataLoading = false;
        if(this._runAfterDataLoadedQueue.length != 0) {
            var callback;
            while(callback = this._runAfterDataLoadedQueue.pop()) {
                callback();
            }
            this.chart.redraw();
        }
    };

    // add to a queue that will be executed after the chart data has been loaded into the chart
    // via _loadComplete()
    AbstractHighstockChart.prototype._runAfterDataLoaded = function(callback) {
        this._runAfterDataLoadedQueue.push(callback);
    };

    AbstractHighstockChart.prototype._handleStatsLoad = function(data) {
        // hate doing this, but there's a race condition when the selected range is changed between
        // the main chart data and stats data updating the chart - if the stats data is loaded first,
        // it won't display the flags. this queues up the stats flag update until the main chart data 
        // has been loaded
        if(this._dataLoading) {
            this._runAfterDataLoaded(meso.Util.bind(this, function() {
                this._updateStats(data);
            }));
        } else {
            this._updateStats(data);
            this.chart.redraw();
        }
    };

    AbstractHighstockChart.prototype._updateStats = function(data) {
        for(var fieldId in data) {
            this.updateFieldStats(fieldId, data[fieldId]);
        }
    };

    AbstractHighstockChart.prototype._clearStatsFlags = function() {
        this._fieldIds.forEach(function(fieldId) {
            this.updateFieldStats(fieldId, null);
        }, this);
    };

    AbstractHighstockChart.prototype.updateFieldStats = function(fieldId, data) {
        var flagSeries = this.chart.get(fieldId+'_stats');
        if(!flagSeries) return;

        var series = this.chart.get(flagSeries.options.onSeries);
        //if(!series.visible) return;
        var valueSuffix = series.options.tooltip.valueSuffix;

        var flagData = [];
        if(data) {
            if(typeof data.min != "undefined") {
                flagData.push({
                    x: data.min[1],
                    title: data.min[0] + valueSuffix,
                    text: "Min "+series.options.name+": "+data.min[0] + valueSuffix
                });
            }
            if(typeof data.max != "undefined") {
                flagData.push({
                    x: data.max[1],
                    title: data.max[0] + valueSuffix,
                    text: "Max "+series.options.name+": "+data.max[0] + valueSuffix
                });
            }
        }

        // highcharts requires the data be sorted
        flagData.sort(function(a,b) {
            // sort by x ascending
            return a.x - b.x;
        });

        if(flagSeries) flagSeries.setData(flagData, false);
    }

    AbstractHighstockChart.prototype._buildChartOptions = function() {
        var chartOptions = {};
        chartOptions.chart = {
            events: {
                load: meso.Util.bind(this, this._chartReady ),
            },
            alignTicks: true,
            animation: false
        };
        chartOptions.rangeSelector = {
            enabled: false
        };
        chartOptions.navigator = {
            enabled : true,
            adaptToUpdatedData : !this._lazy,
            series : {
                id : '__NAVIGATOR__' // used when the chart is lazy loaded to populate the navigator series
            }
        };
        // if chart is lazy, need to override the tooltip to display the aggregation period
        if(this._lazy) {
            chartOptions.tooltip = {
                useHTML : true,
                formatter: this._createTooltipFormatter()
            };
        };
        chartOptions.plotOptions = {
            line: {
                lineWidth: 2,
                marker: {
                    enabled: false,
                    states: {
                        hover: {
                            enabled: true,
                            radius: 5
                        }
                    }
                },
                shadow: false,
                states: {
                    hover: {
                        lineWidth: 2
                    }
                }
            }
        };
        // x-axis
        var xAxisOptions = {
            events: {
                setExtremes: meso.Util.bind(this, this._onSetExtremes)
            },
            ordinal: false,
        };
        chartOptions.xAxis = $.extend(true, xAxisOptions, this.options.xAxis.highstockAxisOptions);
        // y-axes & series
        chartOptions.yAxis = [];
        chartOptions.series = [];

        this.options.yAxes.forEach(function(axisDef, axisIndex) {
            
            var axisId = axisDef.axisId;
            if( !axisId ) {
                throw new Error("Axis at index "+axisIndex+" has no 'axisId' defined");
            }

            // create the highstock axis options
            var axis = $.extend(true, {}, axisDef.highstockAxisOptions);
            if( !axis.labels ) {
                axis.labels = {
                    formatter : this._suffixFormatter(axisDef.unit.labelSuffix)
                };
            }
            axis.id = axisId;
            chartOptions.yAxis.push( axis );

            // create the highstock series options of this axis
            this.axisSeries[axisId].forEach(function(seriesDef) {

                // create the primary series
                var seriesOptions = this._buildSeriesChartOptions(seriesDef, axisDef);
                chartOptions.series.push(seriesOptions);

                // create stat flag series (if configured)
                if(seriesDef.stats) {
                    var statsSeriesDefaultOptions = {
                        onSeries: seriesOptions.id,
                        yAxis: axisIndex, // this is undocumented in the API, but necessary to get it to render in the correct axis
                        tooltip: {
                            xDateFormat: "%A, %b %e, %l:%M:%S%P"
                        },
                        showInLegend: false,
                        zIndex: 100 // display above the series lines
                    };
                    var flagSeriesOptions = meso.Util.applyDefaults(seriesDef.statsFlagsHighstockSeriesOptions, statsSeriesDefaultOptions); 
                    // these settings can't be overridden
                    flagSeriesOptions.id = seriesDef.fieldDef.fieldId + '_stats';
                    flagSeriesOptions.type = 'flags';
                    flagSeriesOptions.data = [];

                    chartOptions.series.push(flagSeriesOptions);
                }
            }, this);

        }, this);

        chartOptions = meso.Util.applyDefaults(this.options.highstockChartOptions, chartOptions);

        return chartOptions;
    };

    /*
        Highcharts defaults:
            plotOptions.series.dataGrouping.dateTimeLabelFormats:
                {
                   millisecond: ['%A, %b %e, %H:%M:%S.%L', '%A, %b %e, %H:%M:%S.%L', '-%H:%M:%S.%L'],
                   second: ['%A, %b %e, %H:%M:%S', '%A, %b %e, %H:%M:%S', '-%H:%M:%S'],
                   minute: ['%A, %b %e, %H:%M', '%A, %b %e, %H:%M', '-%H:%M'],
                   hour: ['%A, %b %e, %H:%M', '%A, %b %e, %H:%M', '-%H:%M'],
                   day: ['%A, %b %e, %Y', '%A, %b %e', '-%A, %b %e, %Y'],
                   week: ['Week from %A, %b %e, %Y', '%A, %b %e', '-%A, %b %e, %Y'],
                   month: ['%B %Y', '%B', '-%B %Y'],
                   year: ['%Y', '%Y', '-%Y']
                }
    */
    AbstractHighstockChart.prototype._createTooltipFormatter = function() {
        var self = this;
        return function() {
            // flags
            if(this.point && this.series.options.type == 'flags') {
                var s = Highcharts.dateFormat(this.series.options.tooltip.xDateFormat, this.x);
                // TODO style the text a bit more (text is set when created)
                s += '<br/>' + this.point.text;
                return s;
            } else if(this.points && this.points.length) {
                var s = '';
                if(self._currentDataAggregated) {
                    var unitDateTimeLabelFormats = self._groupDateTimeLabelFormats[self._currentGroupingInterval.unit];
                    if(self._currentGroupingInterval.interval == 1) {
                        s += Highcharts.dateFormat(unitDateTimeLabelFormats[0], this.x);
                    } else {
                        s += Highcharts.dateFormat(unitDateTimeLabelFormats[1], this.x);
                        s += Highcharts.dateFormat(unitDateTimeLabelFormats[2], this.x + self._currentGroupingInterval.ms);
                    }
                } else {
                    var unit = self._determineDateTimeLabelUnit(this.x);
                    var format = self._groupDateTimeLabelFormats[unit][0];
                    s += Highcharts.dateFormat(format, this.x);
                }
                s += '<table>';
                this.points.forEach(function(point, index) {
                    s += '<tr><td style="color:' + point.series.color + '">' + point.series.name + '</td>' + 
                         '<td><b>' + point.y + '</b><small>' + point.series.tooltipOptions.valueSuffix + '</small></td></tr>';
                });
                s += '</table>';
                return s;
            }
        }
    };

    // attempt to determine if the currently loaded chart data was actually aggregated.
    // this is generally known ahead of time, but if a dataInterval wasn't specified
    // then the data might appear aggregated, but not actually be; this is assumed to be
    // thse case if the data doesn't match the expected grouping interval. note that in
    // this scenario the dateTime values themselves may not be accurate; thus specifying
    // a dataInterval is advised, if possible.
    // XXX data provider implementations may not always necessarily honor the request 
    // grouping to the T, however, the response should generally not be smaller than what 
    // was requested unless the data isn't aggregated - would this be a better/more flexible 
    // approach?
    AbstractHighstockChart.prototype._isDataAggregated = function(data) {
        if(!this._lazy || !this._currentGroupingInterval) return false;
        // this algorithm inspects the data and compares the difference of consecutive
        // dataTime values; if it finds one that is equal to the current grouping interval (or
        // within the min/max), then the data is considered to have been aggregated (i.e.
        // the data matches the expected grouping interval)
        var hasMinMax = this._currentGroupingInterval.minMs && this._currentGroupingInterval.maxMs;
        if(data.length > 1) {
            for(var i=0; i<data.length-1; i++) {
                var xDiff = data[i+1][DATE_TIME_INDEX] - data[i][DATE_TIME_INDEX];
                if(xDiff == this._currentGroupingInterval.ms || (hasMinMax && 
                        xDiff >= this._currentGroupingInterval.minMs && xDiff <= this._currentGroupingInterval.maxMs)) {
                    return true;
                }
            }
        }
        return false;
    };

    // attempt to determine the significance of a dateTime value to display when the data
    // is in raw form (i.e. not aggregated). If a _dataInterval has been specified, then
    // this is preferred, but if not then we attempt to deduce it based on the calculated
    // average interval of the data and the dateTime value itself.
    // Note: this method has only been tested with data in 2 second and 5 minute intervals.
    AbstractHighstockChart.prototype._determineDateTimeLabelUnit = function(x) {
        // attempt to determine the unit based on the x (dateTime) value
        var pointUnit = INTERVAL.day; // XXX the default for now, could add others
        if(x % 1000 != 0) pointUnit = INTERVAL.millisecond;
        else if(x % 60000 != 0) pointUnit = INTERVAL.second;
        else if(x % 3600000 != 0) pointUnit = INTERVAL.minute;
        else if(x % 86400000 != 0) pointUnit = INTERVAL.hour;
        else if(x % 604800000 != 0) pointUnit = INTERVAL.day;
        // attempt to determine the unit based on the data interval
        var dataInterval = this._dataInterval;
        if(!dataInterval) {
            dataInterval = this._calculatedDataInterval;
        }
        var intervalUnit = INTERVAL.day; // XXX the default for now, could add others
        if(dataInterval) {
            if(dataInterval < 1000) intervalUnit = INTERVAL.millisecond;
            else if(dataInterval < 60000) intervalUnit = INTERVAL.second;
            else if(dataInterval < 3600000) intervalUnit = INTERVAL.minute;
            else if(dataInterval < 86400000) intervalUnit = INTERVAL.hour;
            else if(dataInterval < 604800000) intervalUnit = INTERVAL.day;
        }
        // return the most significant interval unit
        if(intervalUnit.significance > pointUnit.significance) {
            return intervalUnit.unit;
        }
        return pointUnit.unit;
    }

    AbstractHighstockChart.prototype._buildSeriesChartOptions = function(seriesDef, axisDef) {
        var fieldDef = seriesDef.fieldDef;
        var fieldId = fieldDef.fieldId;
        var seriesDefaultOptions = {
            name: fieldDef.label
        };
        // override the defaults
        var seriesOptions = $.extend(true, seriesDefaultOptions, seriesDef.highstockSeriesOptions);
        seriesOptions.id = fieldId;
        seriesOptions.yAxis = axisDef.axisId;
        seriesOptions.data = this._chartData[fieldId];
        // always disable data grouping if lazy
        seriesOptions.dataGrouping = this._lazy ?  DATA_GROUPING_DISABLED : this._buildSeriesDataGroupingOption(fieldDef);
        seriesOptions.tooltip = {
            valueDecimals: fieldDef.decimals,
            valueSuffix: axisDef.unit.labelSuffix
        };
        return seriesOptions;
    }

    // highcharts value formatter
    AbstractHighstockChart.prototype._suffixFormatter = function(suffix) {
        return function() {
            return this.value + suffix;
        };
    };

    /**
     * Subclass may override to tweak the Highcharts series data grouping option (units
     * in particular). Defaults to matching the approximation to the field agg 
     * definition.
     */
    AbstractHighstockChart.prototype._buildSeriesDataGroupingOption = function(fieldDef) {
        return {
            units: null, // will use highcarts defaults
            approximation: AGG_TO_GROUP_APPROXIMATION[fieldDef.agg]
        };
    };

    var DATE_TIME_INDEX = 0; // always 0

    var AGG_TO_GROUP_APPROXIMATION = (function() {
        var map = {};
        map[meso.Agg.avg] = 'average';
        map[meso.Agg.min] = 'low';
        map[meso.Agg.max] = 'high';
        map[meso.Agg.sum] = 'sum';
        return map;
    })();

    var DATA_GROUPING_DISABLED = {
        enabled : false
    };

    var DAYS_MS = 86400000;

    // the milliseconds of each interval, plus a min and max, if the unit interval isn't fixed
    // each interval is assigned a significance based on the interval (i.e. greater signficance = smaller 
    // interval)
    // intervals are indexed by both their significance and unit name
    // XXX should this live outside of this class, in meso.Util perhaps?
    var INTERVAL = (function() {
        var intervals = [
            { unit: 'year', ms: 31556900000 },
            { unit: 'month', ms: 2630000000, minMs: 28*DAYS_MS, maxMs: 31*DAYS_MS },
            { unit: 'week', ms: 604800000 },
            { unit: 'day', ms: 86400000 },
            { unit: 'hour', ms: 3600000 },
            { unit: 'minute', ms: 60000 },
            { unit: 'second', ms: 1000 },
            { unit: 'millisecond', ms: 1 },
        ].sort(function(a,b) { // sort by ms descending
            return a.ms < b.ms; 
        });
        var INTERVAL = {};
        intervals.forEach(function(interval, index) {
            interval.significance = index;
            INTERVAL[index] = INTERVAL[interval.unit] = interval;
        });
        return INTERVAL;
    })();

    return AbstractHighstockChart;
})();
