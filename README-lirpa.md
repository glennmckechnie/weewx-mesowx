# MesoWx 

MesoWx is a real-time HTML front-end for visualizing personal weather station data. It provides a 
real-time graph and console display, and dynamic graphs of your weather station history allowing you 
to explore the details of any recorded time period in your data.

MesoWx displays data from a database and does not itself iterface with any weather station hardware
directly, however, being built upon [Meso] [1] it supports an HTTP API for remotely adding data, which 
allows integration with existing weather station software. Currently, MesoWx integrates well with 
[Weewx] [2] and should support any weather station that it supports. Included with MesoWx are several 
extensions for Weewx to integrate with MesoWx. Integrations with other weather station 
software is possible, but must be implemented. Or, depending upon your setup, you can simply
configure Meso to access existing database tables containing your data.

Please join the [meso-user] [3] forum to keep up on releases, get assistance, make suggestions, etc.

[1]: https://bitbucket.org/lirpa/meso
[2]: http://weewx.com
[3]: https://groups.google.com/forum/#!forum/meso-user

## Limitations ##

* A modern web browser is required for the out of the box front-end (Chrome, Firefox, Safari, IE10+)
* Extremely large archive databases likely won't perform very well at the moment (my archive 
  database contains 350,000+ records and has performed adequately), especially on a low power server

## Warnings ##

This software is in early stages of development and as such the code, configurations, and APIs are 
subject to drastic changes between versions. Because of this, it's recommended to do a fresh install
instead of attempting to upgrade to a newer version until version 1.0 is released (which is a long
way off :).

## Installation Guide

There are two primary ways that MesoWx can be setup. The configuration needed revolves around where
your weather station database resides:

1. Shared database
    * To be able to use this setup your web server must be able to access your weather station database,
      or you have done your own database synchronization using some other process
2. Remote database
    * In this setup, your web server has no access to your weather station database, so remote integration 
      and data synchronization is necessary.
    * For this setup, we'll assume that you'll be leveraging the HTTP APIs provided by Meso to synchronize
      your data to a local database.

These instructions will help guide the configuration for your needs. Please determine your desired/necessary
setup path and note the specific instructions for each below. The initial setup is all about getting
your data accessible for consumption by MesoWx.

### Install Prerequisites

MesoWx requires a web server with PHP and a database. You must first install the following:

1. A web server that supports PHP (e.g. Apache HTTP server, Nginx)
2. PHP 5.4+ w/MySQL PDO (PDO is typically installed by default) and JSON
3. MySQL 5+ (For remote database setup only)

How to install and manage these is outside the scope of these instructions.

### Database Setup

If your weather station database isn't available to your web server (remote database setup), you'll need to 
setup a database that it can access and where you will synchronize your remote data. If you web server
can access your weather station database, you may still want to create a separate database user for MesoWx 
to access your database.

To create a database to house your data (remote database setup only):

    mysql> create database mesowx;

To create a user with access to this database (replace <PASSWORD> with a password for the user):

    mysql> CREATE USER 'mesowx'@'localhost' IDENTIFIED BY '<PASSWORD>';

Grant access to your database (note: **only needed for remote database setup**):

    mysql> GRANT select, update, create, delete, insert ON mesowx.* TO mesowx@localhost;

Grant access to your database (note: **only needed for shared database setup**, replace <DATABASE> with your database name):

    mysql> GRANT select ON <DATABASE>.* TO mesowx@localhost;

### Install MesoWx

1. Expose the `web` folder via your web server
2. Once done, you can test by trying to access `/js/Config-example.js` in a browser.
3. Also make sure that the `/meso/include/.htaccess` file is being applied by
   trying to access the configuration file `/meso/include/config-example.json` in a browser.  If not using
   Apache, use a similar means to prevent access to the files in the include folder. 
   **This is extremely important for protecting your configuration file which includes your database 
   credentials**.

### Configure Meso

Meso is included in `meso` sub-directory within MesoWx's `web` directory and has it's own configuration
file. An example configuration file exists in `web/meso/include/` named `config-example.json` is stubbed
for a typical Weewx integration and includes documentation explaining the various options. The actual
configuration file must be named `config.json` and should be in the same directory. You can rename
or make a copy of the example file to use as a starting point. See the comments in the example file for 
further instructions on how to configure Meso for MesoWx, and refer to the Meso documentation
for further assistance.

### Configure MesoWx

An example MesoWx configuration is defined in `/web/js/Config-example.js`. The actual configuration file
must be named `Config.js` and live in the same directly. You can rename or make a copy of this file
to use as a starting point. See the comments in the example file for further explainations of the
various configuration options.

Next, either rename or make a copy of the `/web/index-example.html` and call it `index.html`. This file
contains the HTML markup and core containers for the user interface and can be customized, if desired, but
knowledge of HTML and CSS is necessary. See the comments in the file for some easy tweaks that could be 
made depending on your weather station. If you're wanting to customize the CSS style, it's recommended 
to create a new CSS file rather than editing `mesowx.css`, so that future updates don't overwrite your
changes.

### Weewx Plugins ###

_Note: if you're not integrating with Weewx, this section can be skipped._

Included with MesoWx are several plugins/extensions for Weewx that help provide the weather station data 
for use by MesoWx:

* **raw.py** - Allows Weewx to store raw/LOOP data from the weather station into a database, something that Weewx 
  doesn't provide out of the box. If you're doing a shared database setup such that MesoWx and Weewx are
  able to access the same database, this plugin should be installed to provide the real-time data from your 
  station to MesoWx.
* **sync.py** - Supports the remote database setup and allows both archive and raw/LOOP data from Weewx to 
  be sent to a remote database over HTTP via Meso. Archive data is synchronized such that the records are kept 
  in sync even if one or both of the servers are down for a period of time. This plugin is intended for setups 
  where Weewx isn't being run on the same server or network as your web server that is hosting MesoWx.
* **retain.py** - This plugin is for Weewx station drivers that don't emit complete raw/LOOP data with each
  update. It retains prior values and fills in the gaps of future packets with these values to mimic a complete
  packet of data. Unless you know your driver won't emit partial packets (e.g. vantagepro), this plugin should 
  be installed, and even if it does it won't hurt to install it.

Usually either the raw or sync plugins will be installed depending on your setup; both plugins don't need to
be run, but they can be, if desired. The retain plugin is intended to be used in conjuction with the other 
two plugins.

See the instructions below for how to install and configure these plugins.

#### Weewx Raw/LOOP Data Plugin (raw.py) ####

1. Stop Weewx
2. Copy the `extra/plugins/weewx/raw.py` file into `$WEEWX_HOME/bin/user/`
3. Edit your `weewx.conf`
    1. Add the following section:

            ############################################################################################
            
            [Raw]
                
                #
                # This section is for configuration of the raw plugin. This plugin stores the raw
                # data off of the station, and can also push that data to a redis pub/sub
                # database.
                #
                
                # The database to persist the raw data. 
                # This should match a section under the [Databases] section.
                raw_database = raw_mysql

                # The max amount of raw data to retain specified in hours (set to 0 to retain all data)
                # This will in effect keep a rolling window of the data removing old data based on 
                # the time of the most recent record. It is recommended to set this to at least 24.
                #
                # NOTE: if increasing this value (or setting to unlimited), keep in mind that raw data 
                #       may consume VERY large amounts of space!
                data_limit = 24

            ############################################################################################

    2. If necessary, add a new database under the `[Databases]` section that should corresponds with the 
       `raw_database` property value that you specified in step #2. (Note that as of Weewx 2.2, it is 
       possible to use the same database as your archive database if using MySQL).
    3. Tweak the `raw_database` setting under `[Raw]` to point to the database
    4. Add `user.raw.RawService` to the `archive_services` setting list found under `[Engines] [[WxEngine]]`

4. Restart Weewx
    * Check syslog for errors if it doesn't start up (see the Troubleshooting section below)

5. Edit `web/meso/include/config.json` file of your MesoWx install

    1. Specify the configuration for your archive and raw databases as configured in Weewx
        * Note that if you are using a different database user that you may need to update the 
          grants of the user to access the new raw table.

#### Weewx Remote Synchronization Plugin (sync.py) ####

MesoWx also provides a solution to synchronize both the archive and raw/LOOP data directly to MesoWx via
a Meso's HTTP-based API. This allows Weewx to be run on a completely separate server and network from your
web server, and stil allow you to view your data through MesoWx with near real-time updates. All it
requires is the ability to connect to the internet. To install this Weewx plugin:

1. Stop Weewx
2. Copy the `extra/plugins/weewx/sync.py` file into `$WEEWX_HOME/bin/user/`
3. Edit your `weewx.conf`:
    1. Add the following section:

            ############################################################################################
            
            [RemoteSync]

                #
                # This section is for configuration of the MesoWx remote sync service/plugin. This service
                # will synchronize archive and/or raw/LOOP data to a Meso web server instance over HTTP. 
                #

                # The base URL of your Meso instance
                remote_server_url = http://<YOUR.MESOWX.WEB.SERVER>/meso/

                # The Meso entity ID for archive data
                archive_entity_id = weewx_archive
                # The Meso security required to update the archive data entity
                archive_security_key = 

                # The Meso entity ID for raw data
                raw_entity_id = weewx_raw
                # The Meso security key required to update the raw data entity
                raw_security_key = 
            
            ############################################################################################

        1. Update the `remote_server_url` to your MesoWx web server base URL
        2. Update the entity IDs and security keys to correspond to the values specified in your 
           MesoWx `web/meso/include/config.json` for each entity

    2. Add `user.sync.SyncService` to the `restful_services` setting list found under `[Engines] [[WxEngine]]`

4. Restart Weewx
    * Check syslog for errors if it doesn't start up (see the Troubleshooting section below)

#### Weewx Retain Raw/LOOP Values Plugin (retain.py) ####

1. Stop Weewx
2. Copy the `extra/plugins/weewx/retain.py` file into `$WEEWX_HOME/bin/user/`
3. Edit your `weewx.conf`:
    1. Add the following section:

            ############################################################################################
            
            [RetainLoopValues]

                # The exclude_fields parameter optionally specifies a list (comma-separated) of fields to 
                # exclude from retention, this is useful for fields that may have meaning at each interval 
                # even when not present (e.g. rain).
                exclude_fields = rain
            
            ############################################################################################

        1. Add/remove any applicable fields to the list

    2. Add `user.retain.RetainLoopValues` to the `archive_services` setting list found under 
       `[Engines] [[WxEngine]]`
        * Note: If only using the SyncService plugin, you can add it to the `restful_services` list
        * **Important Note: make sure to add it just _before_ the SyncService or RawService and 
          _after_ the weewx StdArchive service.**

4. Restart Weewx
    * Check syslog for errors if it doesn't start up (see the Troubleshooting section below)

### Testing ###

At this point it should now be possible to view your weather station data in MesoWx in your browser by
visiting your site. If all is successful you should see a the current 
readings of your station console that should be updating regularly (in close to real-time) and a (likely
sparsely populated) graph of your data (it will take time to fully populate). View the 'Real-time' chart
(the links below the chart) and see the chart dynamically update as the time progresses. View the 'Archive'
chart and see your archive data (if you are using the remote sync plugin, it will take some time to 
synchronize all of your data, but over time it should fill up). See the troubleshooting section below if
any issues are encoutnered.

## Upgrading ##

As mentioned in the warning, upgrading is not supported at this time as the project take shape and works
toward a more stable 1.0 release. Until then it's recommended to completely re-install newer versions.

## Troubleshooting ##

Check your web server/PHP logs for errors. Make sure that logging is enabled in your `php.ini`. To confirm, 
check your `php.ini` for the following diretives:

* [log_errors] [4] enabled
* [error_log] [5] (where to look for logs)
* [error_reporting] [6] should be set to `E_ALL & ~E_NOTICE & ~E_STRICT & ~E_DEPRECATED`

To help pinpoint the issues, it can be helpful to inspect the browser network traffic using a development tool 
such as Firebug, and keep an eye out for javascript errors. Using these tools you can inspect the HTTP responses 
for more details about what the root cause may be.

If using the Weewx plugins, errors will be logged to syslog. Try putting Weewx in debug mode (set `debug=1` in your
weewx.conf) to gather more information.

If you're unable to figure out the issue, post a message on the [meso-user group] [3] along with as much information 
as you can supply to help track down the issue (e.g. your setup, any error messages, your syslog, etc). And
once you've solved your issue, feel free to help others out who encounter similar issues! :)

[4]: http://www.php.net/manual/en/errorfunc.configuration.php#ini.log-errors
[5]: http://www.php.net/manual/en/errorfunc.configuration.php#ini.error-log
[6]: http://www.php.net/manual/en/errorfunc.configuration.php#ini.error-reporting
