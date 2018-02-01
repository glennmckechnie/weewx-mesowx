var mesowx = mesowx || {};

// keeping this simple for now
mesowx.MesoWxApp = (function() {

    var MesoWxApp = function(config) {

        Highcharts.setOptions( config.highchartsOptions );

        // this exists because for some reason sometimes HTTP request have silently 
        // failed with no error is reported (at least in Chrome)
        $.ajaxSetup({
            "error": function() {
                console.error('An unexpected error occurred during and HTTP request', arguments);
            }
        });

        this.start = function() {

            var mesowxConsole = new mesowx.MesoWxConsole(config.consoleOptions);

            if(config.windCompassOptions) {
                var windCompass = new mesowx.MesoWxWindCompass(config.windCompassOptions);
            }

            // chart selection
            var currentChart = null;
            selectChart(createTodayChart);

            $('#real-time-selector').click(function(event) {
                selectChart(createRealTimeChart);
                return false;
            });
            $('#today-selector').click(function(event) {
                selectChart(createTodayChart);
                return false;
            });
            $('#archive-selector').click(function(event) {
                selectChart(createArchiveChart);
                return false;
            });

            function selectChart(createFunction) {
                if( currentChart ) currentChart.destroy();
                currentChart = createFunction();
            }

            function createRealTimeChart() {
                return new mesowx.RealTimeChart(config.realTimeChartOptions);
            }
            function createTodayChart() {
                return new mesowx.RawChart(config.rawChartOptions);
            }
            function createArchiveChart() {
                return new mesowx.ArchiveChart(config.archiveChartOptions);
            }
        }
    }

    return MesoWxApp;
})();
