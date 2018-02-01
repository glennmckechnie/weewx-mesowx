var meso = meso || {};

meso.AbstractRealTimeRawDataProvider = (function() {

    var subscriptionId = 1;

    var AbstractRealTimeRawDataProvider = function() {
        this._subscriptions = [];
    };

    AbstractRealTimeRawDataProvider.prototype.subscribe = function(callback, desiredData) {
        var subscription = new Subscription(this, callback, desiredData);
        this._subscriptions.push(subscription);
        return subscription;
    };

    AbstractRealTimeRawDataProvider.prototype.unsubscribe = function(subscription) {
        var index = this._subscriptions.indexOf(subscription);
        if( index !== -1 ) {
            this._subscriptions.splice(index, 1);
        }
    };

    AbstractRealTimeRawDataProvider.prototype._notifySubscribers = function(rawData) {
        if( !rawData ) return;
        var subscription;
        for(var i=0; i<this._subscriptions.length; i++) {
            subscription = this._subscriptions[i];
            subscription.callback( this._adaptData(rawData, subscription.desiredData) );
        }
    }

    // abstract
    AbstractRealTimeRawDataProvider.prototype._adaptData = function(rawData, desiredData) {
        throw new Error("Subclass must implement");
    }

    // Subscription
    function Subscription(provider, callback, desiredData) {
        this.callback = callback;
        this.desiredData = desiredData;
        this._provider = provider;
    }
    Subscription.prototype.unsubscribe = function() {
        this._provider.unsubscribe(this);
    };

    return AbstractRealTimeRawDataProvider;
})();
