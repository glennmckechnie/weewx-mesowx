# MesoWx Change Log #

## 0.6.5 (2023-07-27) ##

* Playing Catchup..
* Untested fix (by me - I'm still running python 3.7)
   Adjust mesowx.py according to Issue #8
   https://github.com/glennmckechnie/weewx-mesowx/issues/8
   It seems that Thread.isAlive() was deprecated in Python 3.7 in favor of is_alive()
   (which has been around since Python v2.6), and removed in Python v3.9.
* Also an older fix which I apparently uploaded, but didn't note here...
   rejig to stop backfill but retry on data

## 0.6.4 (2020-06-27) ##

* text labels are now configurable to accept alternate names or languages.
    mesowx.py, index.html.tmpl, skin.conf and Config.js.tmpl have been tweaked to
    1.) retain a set of english defaults
    2.) read values from the [Language] sections in skin.conf
    skins/mesowx/*.inc files will still need to be hand edited as they are intended
    to be user configurable anyway


## 0.6.3 (2020-06-23) ##

* split unit configuration into database (auto via weewx.conf) **and** display
    (manual via skin.conf)
* issues ref #2 : change displayed unit inHg for barometer to 'inHg' instead of 'in'
* flag (stats - min/max) colors are now the same as the line colors. They should also be
    visible when near the boundaries (clip : false)
* add optional inTemp and inHumidity sections to mesowx console. We have the room, if we
    have the fields...
* re-add rain to charts. Make dayRain a configurable option from skin.conf (untested, don't
    have one, feed back welcomed!)
* Ratchet up the user configuration in skin.con - 2 default pallets and the previous user
    configurable one
* add chart visibility options to skin.conf. All but inTemp are 'on' to start with.
    outTemp is always on (otherwise the chart generation errors and we get nowhere)
* add modules/exporting.js to add print menu (top right hamburger style)
* there's still an issue with the Humidity flags when the lines are hidden ??
* tweak dayRain config option (untested)

## 0.6.2 (2020-06-18) ##

* Add colors to skin.conf, match them to Config.js
* Update old highcharts options to match 8.1.1, or close enough too.

## 0.6.1 (2020-06-17) ##

* modify css, index.html, and Config.js files to allow for dynamic resizing and better use of
    screen space.
    Scales well under Opera, Firefox, Chrome and a Samsung phone. Trust that it works for others
    as well!

## 0.6.0 (2020-06-16) ##

* update to d3-v3.5.17.min.js (last of the v3 line) : highstock-v8.1.1.js : jquery-3.5.1.min.js
    libraries.
  This gives better reloads for the local version, it was stalling on the archive page for me
  There is a slight change in appearance (the navigator bar for one)
* add marker symbols etc supplied by user "laki1" back in 2017 ! ...
    https://groups.google.com/d/msg/weewx-user/eAUsTqR8yYQ/qCtf7IGaBwAJ
* for readability: split labels between left and right sides of charts

## 0.5.3 (2020-06-16) ##

* Add skip_loop as an option to skip loop (raw) records if they come too quickly for your liking
* Allow the 24-Hour display to span a longer range when specified by data_limit, assuming that
    becomes greater than the default value of 24 hour
* Set the archive graphs to load 1 months as the default. Faster initial loads

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

