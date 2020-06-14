var meso = meso || {};

meso.MesoConsole = (function() {

    var MesoConsole = function(options) {
        options = meso.Util.applyDefaults(options, DEFAULT_OPTIONS);
        this._$ = options.containerId ? $('#'+options.containerId) : $(document);
        this._defaultValueDisplayManagerFactory = options.defaultValueDisplayManagerFactory;
        this._realTimeDataProvider = options.realTimeDataProvider;
        this._fields = options.fields;
        this._fieldDefs = [];
        this._fieldIdIndex = [];
        this._fieldValueDisplayManagers = {};
        this._fieldValueFormatters = {}; // retain the value elements, can be used by subtypes
        this._fieldValueElements = {};
        this._fields.forEach(function(field) {
            var fieldId = field.id || field.fieldDef.fieldId;
            var fieldValueDisplayMananger = this._initializeFieldValueDisplayManager(fieldId, field);
            this._setUnitLabel(fieldId, field);
            if(fieldValueDisplayMananger) {
                this._fieldDefs.push(field.fieldDef);
                this._fieldIdIndex.push(fieldId);
                this._fieldValueDisplayManagers[fieldId] = fieldValueDisplayMananger;
                if(field.valueFormatter) {
                    this._fieldValueFormatters[fieldId] = field.valueFormatter;
                }
            }
        }, this);
        this._dataSubscription = this._realTimeDataProvider.subscribe(
                meso.Util.bind(this, this._onNewData), this._fieldDefs);
    };
    MesoConsole.prototype._onNewData = function(data) {
        // convert to fieldId -> value structure
        var fieldId;
        var fieldValues = {};
        data.forEach(function(value, index) {
            fieldId = this._fieldIdIndex[index];
            fieldValues[fieldId] = value;
        }, this);
        this._updateFieldValues(fieldValues);
    };
    MesoConsole.prototype._updateFieldValues = function(fieldValues) {
        // call each display manager
        var value, formatter;
        for(fieldId in fieldValues) {
            value = fieldValues[fieldId];
            valueFormatter = this._fieldValueFormatters[fieldId];
            if(valueFormatter) {
                value = valueFormatter(value);
            }
            this._fieldValueDisplayManagers[fieldId].updateValue(value, fieldValues);
        }
    };
    MesoConsole.prototype._setUnitLabel = function(fieldId, field) {
        var unitElement = this._findUnitElement(fieldId, field);
        // no problem if not found, may be intentionally hard coded
        if(unitElement) {
            $(unitElement).html(field.fieldDef.unit.labelSuffix);
        }
    };
    MesoConsole.prototype._initializeFieldValueDisplayManager = function(fieldId, field) {
        var element = this._findValueElement(fieldId, field);
        if(element) {
            this._fieldValueElements[fieldId] = element;
            var displayManagerFactory = field.valueDisplayManagerFactory;
            if(!displayManagerFactory) displayManagerFactory = this._defaultValueDisplayManagerFactory;
            return displayManagerFactory(element, field.fieldDef, fieldId);
        }
        console.warn("Element could not be found for fieldId: "+fieldId);
        return null;
    };
    MesoConsole.prototype._findValueElement = function(fieldId, field) {
        // first check for a ID defined directly
        if(field.valueElementId) {
            return this._findElement("#"+field.valueElementId);
        }
        // then class defined directly
        if(field.valueElementClass) {
            return this._findElement("."+field.valueElementClass);
        }
        // then by class convention
        var nameConvention = fieldId+'-value';
        return this._findElement('.'+nameConvention);
    };
    MesoConsole.prototype._findUnitElement = function(fieldId, field) {
        // first check for a ID defined directly
        if(field.unitElementId) {
            return this._findElement("#"+field.unitElementId);
        }
        // then class defined directly
        if(field.unitElementClass) {
            return this._findElement("."+field.unitElementClass);
        }
        // then by class convention
        var nameConvention = fieldId+'-unit';
        return this._findElement('.'+nameConvention);
    };
    MesoConsole.prototype._findElement = function(selector) {
        return this._$.find(selector).get(0); // XXX warn if more than one returned?
    };

    // Display manager implementation that will just update the value, nothing fancy
    MesoConsole.SimpleValueDisplayManager = (function() {
        var SimpleValueDisplayManager = function(valueElement) {
            this._$ = $(valueElement);
            this._currentValue = null;
        };
        SimpleValueDisplayManager.prototype.updateValue = function(newValue, data) {
            if(newValue != this._currentValue) this._$.html(newValue);
            this._currentValue = newValue;
        };
        return SimpleValueDisplayManager;
    })();

    // Display manager implementation that wraps a ChangeIndicatedValue instance
    MesoConsole.ChangeIndicatedValueDisplayManager = (function() {
        var ChangeIndicatedValueDisplayManager = function(changeIndicatedValue) {
            this._value = changeIndicatedValue;
        };
        ChangeIndicatedValueDisplayManager.prototype.updateValue = function(newValue, data) {
            this._value.setValue(newValue);
        };
        return ChangeIndicatedValueDisplayManager;
    })();

    // standard factory implementations
    MesoConsole.SimpleValueDisplayManagerFactory = function(valueElement, fieldDef, fieldId) {
        return new MesoConsole.SimpleValueDisplayManager(valueElement);
    };
    MesoConsole.ChangeIndicatedValueDisplayManagerFactory = function(valueElement, fieldDef, fieldId) {
        var value = new ChangeIndicatedValue({
            container: valueElement,
            decimals: fieldDef.decimals
        });
        return new MesoConsole.ChangeIndicatedValueDisplayManager(value);
    };

    var DEFAULT_OPTIONS = {
        defaultValueDisplayManagerFactory: MesoConsole.ChangeIndicatedValueDisplayManagerFactory
    };

    return MesoConsole;

})();
