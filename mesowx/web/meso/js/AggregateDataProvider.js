var meso = meso || {};

meso.AggregateDataProvider = (function() {

    var AggregateDataProvider = function(options) {
        this._baseUrl = options.baseUrl;
    };

    AggregateDataProvider.prototype.getData = function(query) {
        if( !query.success ) throw new Error("Must supply a success function");
        if( !query.data ) throw new Error("Must supply the data to return");
        var url = this._buildUrl(query);
        $.getJSON(url, query.success);
    };
    AggregateDataProvider.prototype._buildUrl = function(query) {
        var url = this._baseUrl;
        // build the data param
        url += url.indexOf('?') == -1 ? '?' : '&';
        url += this._buildDataUrlParam(query.data);
        url += '&';
        // optional parameters
        if( query.start ) {
            url += 'start='+Math.round(query.start.value)+':';
            url += query.start.type === 'ago' ? 'ago' : 'datetime';
            url += '&';
        }
        if( query.end ) {
            url += 'end='+Math.round(query.end.value)+':';
            url += query.end.type === 'ago' ? 'ago' : 'datetime';
            url += '&';
        }
        if( query.group ) {
            url += 'group='+query.group.value+':'+query.group.type;
            if(query.group.unit) {
                url += ':'+query.group.unit;
            }
            url += '&';
        }
        if( query.order ) {
            url += "order="+query.order+"&";
        }
        if( query.limit ) {
            url += "limit="+query.limit+"&";
        }
        // strip the last &
        url = url.substring(0,url.length-1);
        return url;
    };
    AggregateDataProvider.prototype._buildDataUrlParam = function(data) {
        var paramValue = "";
        data.forEach( function(item, index) {
            paramValue += [item.fieldId, item.agg, item.unit.urlParam, item.decimals].join(':') + ',';
        });
        return "data=" + encodeURIComponent(paramValue);
    };

    return AggregateDataProvider;

})();
