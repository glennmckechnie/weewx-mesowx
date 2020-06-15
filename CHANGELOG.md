# MesoWx Change Log #

## 0.5.2 (2020-06-15) ##

* Add loop_polling_interval to [Mesowx] section. Default is 60 seconds (converts to
    60000 milliseconds for insertion into Config.js) This sets the refresh rate of the
    dashboard (right hand panel on index.html)

    From Config.js
    // the polling interval in milliseconds for the raw real-time data provider
    // this controls how frequently to fetch new data, it should be·
    // set to the frequency that your station generates "LOOP" packets
    Config.realTimePollingInterval = 60000;
* Tidy up / finish unit and format auto configurations from v0.5.1

## 0.5.1 (2020-06-15) ##

* Auto set units according to the configuration found in weewx.conf - US, METRICWX or METRIC

## 0.5.0 (2020-06-14) ##

### Simplify / Automate the install
* Combine the 3 scripts into the one - mesowx.py
* Works with weewx4 and python 3, also with python2.7
* Use the wee_extension installer to perform a (mostly) hands off install of the local setup,
    and minimize the interaction required for the remote install.
* Adjust the script, add tmpl's, use randompassword generator for security key insertion.
* Remote install works with archive and raw, Local works with raw database and weewx database,
    RetainLoopValues remains untested.

## 0.4.0 (2014-05-09) ##

### Features
* Meso version bump to 0.4.0
* Charts
    * Charts will now display minimum/maximum flags for the given time range
    * The aggregation periods are now deterministic and can be configured
    * Tooltip will now display the time range of the point if the data has been aggregated
    * Highstock version bump to 1.3.10
* No longer displaying the dayRain field by default in the console or charts since the majority
  of stations don't include this field
* Adding hPa and kPa units
* Weewx Plugins
    * retain.py
        * Can now be configured to exclude fields from being retained
    * sync.py 
        * Will now take advantage of HTTP keep-alive if your web server supports it
        * Will now keep trying if an HTTP request returns a 500 status instead of failing

### Bug Fixes
* Increasing the height of the chart to give room in case the legend wraps to two rows
* Attempting to prevent the wind speed axis scale from being needlessly large by setting it's
  maxPadding to 0

### Breaking Changes
* PHP 5.3 is no longer supported, 5.4+ is now required
* No longer support SQLite, use MySQL instead
* The sync.py weewx plugin is now dependent upon the urllib3 python library
* The chart 'numGroups' configuration parameter is no longer supported


## 0.3.4 (2014-02-19) ##

### Bug Fixes
* Fixing issue with retain.py plugin that wasn't making a copy of the retained packet
* Fixing the labels of the rain fields in Config-example.js


## 0.3.3 (2014-02-16) ##

### Features
* Real-time data provider polling interval now defaulted to 60 seconds instead of 2
* Better support for stations that don't emit complete LOOP packets via a new "retain" weewx plugin 
* Meso version bump to 0.3.3


## 0.3.2 (2014-02-09) ##
* Meso version bump to 0.3.2


## 0.3.1 (2014-01-29) ##
* Meso version bump to 0.3.1


## 0.3.0 (2014-01-28) ##

### Features
* MesoWx is now a separate project from the core data services and chart components that are now Meso
* Much more configurable front-end
    * Aditional fields can be added/removed
    * Charts can be completely customized
    * Compass unit can now be changed
    * Much more
* Version bumps of Highstock and D3 libs (also now using minimized versions of libs)

### Bug Fixes
* Handling socket.error in sync.py


## 0.2.1 (2013-09-09) ##

* Changing some JS libs to be directly included instead remotely referenced
* Version bumps of jQuery, Highstock, D3 libs


### Version 0.2 (2013-04-27) ###

* Remote synchronization plugin for Weewx
* Abstraction of HTTP APIs (can be used for any data, not just Weewx)
* HTTP API for updating data


## 0.1 (2012-11-18) ##

* Initial release
* Raw Weewx plugin for persisting raw/LOOP data
* Aggregate data HTTP API
* Console dynamically updated in real-time
* Three charts:
    * 24 hours of raw data (lazy loaded, zoomable)
    * Dynamically updated real-time raw data
    * Archive data (lazy loaded, zoomable)

