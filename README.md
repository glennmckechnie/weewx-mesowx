
# weewx-MesoWx

This repo is a fork of MesoWx as originally implemented at https://bitbucket.org/lirpa/mesowx 

It starts with the 0.4.0 version which was the latest available on the 1st February 2018. It has been copied here to enable integration with Luc's raw.py and sync.py scripts
No license was available at the time of upload but Peter Finley (MesoWx author) has indicated that it is free to distribute, specifically ...
From https://groups.google.com/d/msg/meso-user/ebs6sOhNqsg/iNeqnVarEgAJ

The extras directory now contains the updated scripts as written by Luc Heijst and were rewritten to keep pace with either the changes in weewx versions, or issues that arose and were reported by weewx users.
Some of those scripts are available in various posts on the weewx-users group. The versions that Luc passed on have been uploaded here as individual commits so viewing the commit history of the files will show those provided. Not all commits are working versions, the latest should be okay though.

The aim is to incorporate the scripts and MesoWx into a skin that is installable using wee_extension.
This repo is not intended to replace the original Lirpa (bitbucket) repo, rather it's an opportunity to keep it (or at least MesoWx) alive

The following description came directly from the MesoWx site at Lirpa, some changes have been made to suit the integration weewx.

############################################

# MesoWx

MesoWx is a real-time HTML front-end for visualizing personal weather station data. It provides a real-time graph and console display, and dynamic graphs of your weather station history allowing you to explore the details of any recorded time period in your data.

MesoWx displays data from a database and does not itself iterface with any weather station hardware directly, however, being built upon Meso it supports an HTTP API for remotely adding data, which allows integration with existing weather station software. Currently, MesoWx integrates well with Weewx and should support any weather station that it supports. Included with MesoWx are several extensions for Weewx to integrate with MesoWx. Integrations with other weather station software is possible, but must be implemented. Or, depending upon your setup, you can simply configure Meso to access existing database tables containing your data.

Please join the meso-user forum to keep up on releases, get assistance, make suggestions, etc.
## Limitations

 1. A modern web browser is required for the out of the box front-end (Chrome, Firefox, Safari, IE10+)
 2. Extremely large archive databases likely won't perform very well at the moment (my archive database contains 350,000+ records and has performed adequately), especially on a low power server

## Warnings

This software is in early stages of development and as such the code, configurations, and APIs are subject to drastic changes between versions. Because of this, it's recommended to do a fresh install instead of attempting to upgrade to a newer version until version 1.0 is released (which is a long way off :).
Installation Guide

There are two primary ways that MesoWx can be setup. The configuration needed revolves around where your weather station database resides:

### Shared database
To be able to use this setup your web server must be able to access your weather station database, or you have done your own database synchronization using some other process
### Remote database
 In this setup, your web server has no access to your weather station database, so remote integration and data synchronization is necessary.
 For this setup, we'll assume that you'll be leveraging the HTTP APIs provided by Meso to synchronize your data to a local database.

These instructions will help guide the configuration for your needs. Please determine your desired/necessary setup path and note the specific instructions for each below. The initial setup is all about getting your data accessible for consumption by MesoWx.
Install Prerequisites

MesoWx requires a web server with PHP and a database. You must first install the following:

 1.   A web server that supports PHP (e.g. Apache HTTP server, Nginx)
 2.   PHP 5.4+ w/MySQL PDO (PDO is typically installed by default) and JSON
 3.   MySQL 5+ (For remote database setup only)

How to install and manage these is outside the scope of these instructions.

# Database Setup

If your weather station database isn't available to your web server (remote database setup), you'll need to setup a database that it can access and where you will synchronize your remote data. If you web server can access your weather station database, you may still want to create a separate database user for MesoWx to access your database.

To create a database to house your data (remote database setup only):

    mysql -uroot -p
    mysql> create database mesowx;

To create a user with access to this database (this example reuses the weewx user and password):

    mysql> CREATE USER 'mesowx'@'localhost' IDENTIFIED BY 'mesowx';

Grant full access to your remote database (if you are using a remote database setup, which will be with sync.py):

    mysql> GRANT select, update, create, delete, insert ON mesowx.* TO mesowx@localhost;

Grant read only access to your local database (note: only needed for shared database setup, replace <DATABASE> with your database name. raw.py will be the script used here):

    mysql> GRANT select ON <DATABASE>.* TO mesowx@localhost;

# Install MesoWx

  1.  Expose the web folder via your web server
  2.  Once done, you can test by trying to access /js/Config-example.js in a browser.
  3.  Also make sure that the /meso/include/.htaccess file is being applied by trying to access the configuration file /meso/include/config-example.json in a browser. If not using Apache, use a similar means to prevent access to the files in the include folder. This is extremely important for protecting your configuration file which includes your database credentials.

 # Configure Meso

Meso is included in meso sub-directory within MesoWx's web directory and has it's own configuration file. An example configuration file exists in web/meso/include/ named config-example.json. It is stubbed for a typical Weewx integration and includes documentation explaining the various options. The actual configuration file must be named config.json and should be in the same directory. You can rename or make a copy of the example file to use as a starting point. See the comments in the example file for further instructions on how to configure Meso for MesoWx, and refer to the Meso documentation for further assistance.
# Configure MesoWx

An example MesoWx configuration is defined in /web/js/Config-example.js. The actual configuration file must be named Config.js and live in the same directly. You can rename or make a copy of this file to use as a starting point. See the comments in the example file for further explainations of the various configuration options.

Next, either rename or make a copy of the /web/index-example.html and call it index.html. This file contains the HTML markup and core containers for the user interface and can be customized, if desired, but knowledge of HTML and CSS is necessary. See the comments in the file for some easy tweaks that could be made depending on your weather station. If you're wanting to customize the CSS style, it's recommended to create a new CSS file rather than editing mesowx.css, so that future updates don't overwrite your changes.


# Weewx Plugins

# What follows is definitely a work in progress - treat with caution feb 2018 #

The following notes are taken from [Lucs instructions on weewx-user](https://groups.google.com/d/msg/weewx-user/eAUsTqR8yYQ/UVMxAAtgAAAJ) for the raw.py script

The [sync plugin](https://groups.google.com/d/msg/weewx-user/DnaWsMpC9vE/RfcC5KwQAgAJ) notes for later inclusion.

# Raw

## For weewx
Edit weewx.conf 
The addition of a raw section which will read as follows

    ##############################################################################

    [Raw]

        #
        # This section is for configuration of the raw plugin. This plugin stores the raw
        # data off of the station.
        #
        # The database binding to persist the raw data. 
        # This should match a section under the [DataBindings] section.
        data_binding = raw_binding
        #
        # The max amount of raw data to retain specified in hours (set to None to retain all data)
        # This will in effect keep a rolling window of the data removing old data based on 
        # the time of the most recent record. It is recommended to set this to at least 24.
        #
        # NOTE: if increasing this value (or use None to keep forever), 
        # keep in mind that raw data may consume VERY large amounts of space!
        data_limit = 24
    
    ##############################################################################  


Add a section [[raw_binding]] to the [DataBindings] section


    [DataBindings]  
         [[raw_binding]]
            database = raw_mysql
            table_name = raw
            manager = weewx.manager.Manager
            schema = user.raw.schema

Add a section [[raw_mysql]] to the [Databases] section
        
    [Databases]        
        [[raw_mysql]]
            database_type = MySQL
            database_name = meso

## For mesowx

Edit [your local webserver directory]/web/meso/include/Config.json


    "dataSource" : {
        "weewx_mysql" : { // the data source ID
            "type" : "mysql",
            "host" : "localhost",
            "user" : "weewx",       // NOTE: Your mysql username/passwords must be the same as in the
            "password" : "weewx",   // [[MySQL]] section of section [DatabaseTypes] in weewx.conf
            "database" : "weewx"
        },
        "raw_mysql" : { // the data source ID
            "type" : "mysql",
            "host" : "localhost",
            "user" : "weewx",       // NOTE: Your mysql username/passwords must be the same as in the
            "password" : "weewx",   // [[MySQL]] section of section [DatabaseTypes] in weewx.conf
            "database" : "meso"
        }
    },

    "entity" : {
        // This entity definition is for a typical Weewx archive table.
        "weewx_archive" : { // the entity ID


NOTE: the following settings depend on the target_unit setting in section [StdConvert]
WARNING: Check the "columns" sections below; add or remove fields when needed

when target_unit = US:


    "columns" : {
                "dateTime" :    {"type" : "number", "unit" : "s"},
                "interval" :    {},
                "barometer" :   {"unit" : "inHg"},
                "inTemp" :      {"unit" : "f"},
                "outTemp" :     {"unit" : "f"},
                "inHumidity" :  {"unit" : "perc"},
                "outHumidity" : {"unit" : "perc"},
                "windSpeed" :   {"unit" : "mph"},
                "windDir" :     {"unit" : "deg"},
                "windGust" :    {"unit" : "mph"},
                "windGustDir" : {"unit" : "deg"},
                "rainRate" :    {"unit" : "inHr"},
                "rain" :        {"unit" : "in"},
                "dewpoint" :    {"unit" : "f"},
                "windchill" :   {"unit" : "f"},
                "heatindex" :   {"unit" : "f"}
            },


when target_unit = METRIC:


    "columns" : {
                "dateTime" :    {"type" : "number", "unit" : "s"},
                "interval" :    {},
                "barometer" :   {"unit" : "hPa"},
                "inTemp" :      {"unit" : "c"},
                "outTemp" :     {"unit" : "c"},
                "inHumidity" :  {"unit" : "perc"},
                "outHumidity" : {"unit" : "perc"},
                "windSpeed" :   {"unit" : "kph"},
                "windDir" :     {"unit" : "deg"},
                "windGust" :    {"unit" : "kph"},
                "windGustDir" : {"unit" : "deg"},
                "rainRate" :    {"unit" : "cmHr"},
                "rain" :        {"unit" : "cm"},
                "dewpoint" :    {"unit" : "c"},
                "windchill" :   {"unit" : "c"},
                "heatindex" :   {"unit" : "c"}
            },
            // constraints on the data, only primaryKey is supported currently
            "constraints" : {
                // The primary key column of the table. Currently only a single column key is 
                // supported and this column must also be a date time value stored as seconds/ms
                // since epoch.
                "primaryKey" : "dateTime"
            }
        },
        // This example shows a configuration with a retention policy
        "weewx_raw" : {
            "type" : "table",
            "dataSource" : "raw_mysql",
            "tableName" : "raw",
            "accessControl" : {
                "update" : {
                    "allow" : true,
                    "securityKey" : ""
                }
            },
            // The retention policy defines how this data is retained over time. It is only really
            // revevant when allowing this entity to be updated. Curently the only supported
            // policy type is "window" which will retain data within the specified time window.
            "retentionPolicy" : {
                "type" : "window",
                // The trigger defines when the policy is applied. Currently only "update" is
                // supported, which means each time the entity is updated.
                "trigger" : "update",
                // The amount of time in seconds since the current date/time to retain. All records
                // before this time window will be permanently deleted!
                "windowSize" : 86400  // 24 hours)
            },


NOTE: the following settings depend on the target_unit setting in section [StdConvert]
when target_unit = US:



    "columns" : {
                "dateTime" :    {"unit" : "s"},
                "barometer" :   {"unit" : "inHg"},
                "inTemp" :      {"unit" : "f"},
                "outTemp" :     {"unit" : "f"},
                "inHumidity" :  {"unit" : "perc"},
                "outHumidity" : {"unit" : "perc"},
                "windSpeed" :   {"unit" : "mph"},
                "windDir" :     {"unit" : "deg"},
                "rainRate" :    {"unit" : "inHr"},
                "dayRain" :     {"unit" : "in"},
                "dewpoint" :    {"unit" : "f"},
                "windchill" :   {"unit" : "f"},
                "heatindex" :   {"unit" : "f"}
            },


when target_unit = METRIC:


    "columns" : {
                "dateTime" :    {"type" : "number", "unit" : "s"},
                "barometer" :   {"unit" : "hPa"},
                "inTemp" :      {"unit" : "c"},
                "outTemp" :     {"unit" : "c"},
                "inHumidity" :  {"unit" : "perc"},
                "outHumidity" : {"unit" : "perc"},
                "windSpeed" :   {"unit" : "kph"},
                "windDir" :     {"unit" : "deg"},
                "windGust" :    {"unit" : "kph"},
                "windGustDir" : {"unit" : "deg"},
                "rainRate" :    {"unit" : "cmHr"},
                "rain" :        {"unit" : "cm"},
                "dewpoint" :    {"unit" : "c"},
                "windchill" :   {"unit" : "c"},
                "heatindex" :   {"unit" : "c"}
            },

Start weewx

### Release notes raw_0.4.2-lh:
1. No longer raise exception when prune fails
2. To retain all raw data: set data_limit to None (data_limit = None)

























# Lirpa notes 
What follows are the original descriptions and instructions from Lirpa : https://bitbucket.org/lirpa/mesowx/src/default/

## MesoWx

MesoWx is a real-time HTML front-end for visualizing personal weather station data. It provides a real-time graph and console display, and dynamic graphs of your weather station history allowing you to explore the details of any recorded time period in your data.

MesoWx displays data from a database and does not itself iterface with any weather station hardware directly, however, being built upon Meso it supports an HTTP API for remotely adding data, which allows integration with existing weather station software. Currently, MesoWx integrates well with Weewx and should support any weather station that it supports. Included with MesoWx are several extensions for Weewx to integrate with MesoWx. Integrations with other weather station software is possible, but must be implemented. Or, depending upon your setup, you can simply configure Meso to access existing database tables containing your data.

Please join the meso-user forum to keep up on releases, get assistance, make suggestions, etc.

### Limitations

    A modern web browser is required for the out of the box front-end (Chrome, Firefox, Safari, IE10+)
    Extremely large archive databases likely won't perform very well at the moment (my archive database contains 350,000+ records and has performed adequately), especially on a low power server

### Warnings

This software is in early stages of development and as such the code, configurations, and APIs are subject to drastic changes between versions. Because of this, it's recommended to do a fresh install instead of attempting to upgrade to a newer version until version 1.0 is released (which is a long way off :).

### Installation Guide

There are two primary ways that MesoWx can be setup. The configuration needed revolves around where your weather station database resides:

    Shared database
        To be able to use this setup your web server must be able to access your weather station database, or you have done your own database synchronization using some other process
    Remote database
        In this setup, your web server has no access to your weather station database, so remote integration and data synchronization is necessary.
        For this setup, we'll assume that you'll be leveraging the HTTP APIs provided by Meso to synchronize your data to a local database.

These instructions will help guide the configuration for your needs. Please determine your desired/necessary setup path and note the specific instructions for each below. The initial setup is all about getting your data accessible for consumption by MesoWx.

#### Install Prerequisites

MesoWx requires a web server with PHP and a database. You must first install the following:

    A web server that supports PHP (e.g. Apache HTTP server, Nginx)
    PHP 5.4+ w/MySQL PDO (PDO is typically installed by default) and JSON
    MySQL 5+ (For remote database setup only)

How to install and manage these is outside the scope of these instructions.

#### Database Setup

If your weather station database isn't available to your web server (remote database setup), you'll need to setup a database that it can access and where you will synchronize your remote data. If you web server can access your weather station database, you may still want to create a separate database user for MesoWx to access your database.

To create a database to house your data (remote database setup only):

 mysql> create database mesowx;

To create a user with access to this database (replace <PASSWORD> with a password for the user):

 mysql> CREATE USER 'mesowx'@'localhost' IDENTIFIED BY '<PASSWORD>';

Grant access to your database (note: only needed for remote database setup):

 mysql> GRANT select, update, create, delete, insert ON mesowx.* TO mesowx@localhost;

Grant access to your database (note: only needed for shared database setup, replace <DATABASE> with your database name):

 mysql> GRANT select ON <DATABASE>.* TO mesowx@localhost;

#### Install MesoWx

    Expose the web folder via your web server
    Once done, you can test by trying to access /js/Config-example.js in a browser.
    Also make sure that the /meso/include/.htaccess file is being applied by trying to access the configuration file /meso/include/config-example.json in a browser. If not using Apache, use a similar means to prevent access to the files in the include folder. This is extremely important for protecting your configuration file which includes your database credentials.

#### Configure Meso

Meso is included in meso sub-directory within MesoWx's web directory and has it's own configuration file. An example configuration file exists in web/meso/include/ named config-example.json is stubbed for a typical Weewx integration and includes documentation explaining the various options. The actual configuration file must be named config.json and should be in the same directory. You can rename or make a copy of the example file to use as a starting point. See the comments in the example file for further instructions on how to configure Meso for MesoWx, and refer to the Meso documentation for further assistance.

#### Configure MesoWx

An example MesoWx configuration is defined in /web/js/Config-example.js. The actual configuration file must be named Config.js and live in the same directly. You can rename or make a copy of this file to use as a starting point. See the comments in the example file for further explainations of the various configuration options.

Next, either rename or make a copy of the /web/index-example.html and call it index.html. This file contains the HTML markup and core containers for the user interface and can be customized, if desired, but knowledge of HTML and CSS is necessary. See the comments in the file for some easy tweaks that could be made depending on your weather station. If you're wanting to customize the CSS style, it's recommended to create a new CSS file rather than editing mesowx.css, so that future updates don't overwrite your changes.

#### Weewx Plugins

Included with MesoWx are several plugins/extensions for Weewx that help provide the weather station data for use by MesoWx:

    raw.py - Allows Weewx to store raw/LOOP data from the weather station into a database, something that Weewx doesn't provide out of the box. If you're doing a shared database setup such that MesoWx and Weewx are able to access the same database, this plugin should be installed to provide the real-time data from your station to MesoWx.
    sync.py - Supports the remote database setup and allows both archive and raw/LOOP data from Weewx to be sent to a remote database over HTTP via Meso. Archive data is synchronized such that the records are kept in sync even if one or both of the servers are down for a period of time. This plugin is intended for setups where Weewx isn't being run on the same server or network as your web server that is hosting MesoWx.
    retain.py - This plugin is for Weewx station drivers that don't emit complete raw/LOOP data with each update. It retains prior values and fills in the gaps of future packets with these values to mimic a complete packet of data. Unless you know your driver won't emit partial packets (e.g. vantagepro), this plugin should be installed, and even if it does it won't hurt to install it.

Usually either the raw or sync plugins will be installed depending on your setup; both plugins don't need to be run, but they can be, if desired. The retain plugin is intended to be used in conjuction with the other two plugins.

See the instructions below for how to install and configure these plugins.

#### Weewx Raw/LOOP Data Plugin (raw.py)

    Stop Weewx
    Copy the extra/plugins/weewx/raw.py file into $WEEWX_HOME/bin/user/

    Edit your weewx.conf

        Add the following section:

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

        If necessary, add a new database under the [Databases] section that should corresponds with the raw_database property value that you specified in step #2. (Note that as of Weewx 2.2, it is possible to use the same database as your archive database if using MySQL).
        Tweak the raw_database setting under [Raw] to point to the database
        Add user.raw.RawService to the archive_services setting list found under [Engines] [[WxEngine]]

    Restart Weewx
        Check syslog for errors if it doesn't start up (see the Troubleshooting section below)

    Edit web/meso/include/config.json file of your MesoWx install
        Specify the configuration for your archive and raw databases as configured in Weewx
            Note that if you are using a different database user that you may need to update the grants of the user to access the new raw table.

#### Weewx Remote Synchronization Plugin (sync.py)

MesoWx also provides a solution to synchronize both the archive and raw/LOOP data directly to MesoWx via a Meso's HTTP-based API. This allows Weewx to be run on a completely separate server and network from your web server, and stil allow you to view your data through MesoWx with near real-time updates. All it requires is the ability to connect to the internet. To install this Weewx plugin:

    Stop Weewx
    Copy the extra/plugins/weewx/sync.py file into $WEEWX_HOME/bin/user/

    Edit your weewx.conf:

        Add the following section:

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

            Update the remote_server_url to your MesoWx web server base URL
            Update the entity IDs and security keys to correspond to the values specified in your MesoWx web/meso/include/config.json for each entity

        Add user.sync.SyncService to the restful_services setting list found under [Engines] [[WxEngine]]

    Restart Weewx
        Check syslog for errors if it doesn't start up (see the Troubleshooting section below)

#### Weewx Retain Raw/LOOP Values Plugin (retain.py)

    Stop Weewx
    Copy the extra/plugins/weewx/retain.py file into $WEEWX_HOME/bin/user/

    Edit your weewx.conf:

        Add the following section:

        ############################################################################################

        [RetainLoopValues]

            # The exclude_fields parameter optionally specifies a list (comma-separated) of fields to 
            # exclude from retention, this is useful for fields that may have meaning at each interval 
            # even when not present (e.g. rain).
            exclude_fields = rain

        ############################################################################################

            Add/remove any applicable fields to the list

        Add user.retain.RetainLoopValues to the archive_services setting list found under [Engines] [[WxEngine]]
            Note: If only using the SyncService plugin, you can add it to the restful_services list
            Important Note: make sure to add it just before the SyncService or RawService and after the weewx StdArchive service.

    Restart Weewx
        Check syslog for errors if it doesn't start up (see the Troubleshooting section below)

#### Testing

At this point it should now be possible to view your weather station data in MesoWx in your browser by visiting your site. If all is successful you should see a the current readings of your station console that should be updating regularly (in close to real-time) and a (likely sparsely populated) graph of your data (it will take time to fully populate). View the 'Real-time' chart (the links below the chart) and see the chart dynamically update as the time progresses. View the 'Archive' chart and see your archive data (if you are using the remote sync plugin, it will take some time to synchronize all of your data, but over time it should fill up). See the troubleshooting section below if any issues are encoutnered.
#### Upgrading

As mentioned in the warning, upgrading is not supported at this time as the project take shape and works toward a more stable 1.0 release. Until then it's recommended to completely re-install newer versions.

#### Troubleshooting

Check your web server/PHP logs for errors. Make sure that logging is enabled in your php.ini. To confirm, check your php.ini for the following diretives:

    log_errors enabled
    error_log (where to look for logs)
    error_reporting should be set to E_ALL & ~E_NOTICE & ~E_STRICT & ~E_DEPRECATED

To help pinpoint the issues, it can be helpful to inspect the browser network traffic using a development tool such as Firebug, and keep an eye out for javascript errors. Using these tools you can inspect the HTTP responses for more details about what the root cause may be.

If using the Weewx plugins, errors will be logged to syslog. Try putting Weewx in debug mode (set debug=1 in your weewx.conf) to gather more information.

If you're unable to figure out the issue, post a message on the meso-user group along with as much information as you can supply to help track down the issue (e.g. your setup, any error messages, your syslog, etc). And once you've solved your issue, feel free to help others out who encounter similar issues! :)

