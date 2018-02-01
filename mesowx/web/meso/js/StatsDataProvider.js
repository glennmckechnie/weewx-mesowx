var meso = meso || {};

meso.StatsDataProvider = (function() {

    var StatsDataProvider = function(options) {
        this._url = options.url;
        this._entityId = options.entityId;
    };

    StatsDataProvider.prototype.getStats = function(query) {
        if( !query.success ) throw new Error("Must supply a success function");
        if( !query.data ) throw new Error("Must supply the data to return");
        var request = this._buildRequestBody(query);
        $.ajax({
            url: this._url, 
            type: 'POST',
            data: JSON.stringify(this._buildRequestBody(query)),
            processData: false,
            contentType: 'application/json',
            dataType: 'json'
        }).done(query.success);
    };
    StatsDataProvider.prototype._buildRequestBody = function(query) {
        var request = {
            entityId: this._entityId,
            data: query.data
        };
        if(query.timeUnit) request.timeUnit = query.timeUnit;
        if(query.start) request.start = query.start;
        if(query.end) request.end = query.end;
        return request;
    };

    return StatsDataProvider;

})();
