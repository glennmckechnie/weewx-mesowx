# Copyright to its respective owners
# Modified to install using wee_extension with various code fixes
#     https://github.com/glennmckechnie/weewx-mesowx
#        Copyright 2018-2020 Glenn McKechnie
#
# This script combines the original 3 scripts from lirpa MesoWX,
# mesowx/raw.py and mesowx/sync.py and mesowx/retain.py .
# As of 09/2022 the lirpa MesoWX repository has gone.
#
# They have also been modified to run under either python2.7 or python3.X, for
# use with weewx4.X
#
#
# https://github.com/weewx/weewx/wiki/WeeWX-v4-and-logging
#
# As needed, paste into weewx.conf Section [Logging]
# [Logging]
#    [[loggers]]
#        [[[user.mesowx]]]
#            level = DEBUG
#            handlers = syslog,
#            propagate = 0
#
# vim
# :%s/("[0-9]*[0-9]:/\=printf("(\"%d:", line('.'))/g

try:
    import queue
except ImportError:
    import Queue as queue
import json
import itertools
import time
import threading
import urllib3

import weewx
import weewx.restx
import weewx.manager
import weewx.engine
from weewx.engine import StdService
from weewx.cheetahgenerator import SearchList
import weeutil.weeutil

VERSION = "0.6.5"

try:
    # Test for new-style weewx logging by trying to import weeutil.logger
    import weeutil.logger
    import logging
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    log = logging.getLogger(__name__)

    def logdbg(msg):
        log.debug(msg)

    def loginf(msg):
        log.info(msg)

    def logerr(msg):
        log.error(msg)

except ImportError:
    # Old-style weewx logging
    import syslog

    def logmsg(level, msg):
        syslog.syslog(level, 'user.mesowx: %s:' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)

# original sync.py script -- start

if weewx.__version__ < "4":
    raise weewx.UnsupportedFeature("weewx 4 is required, found %s" %
                                   weewx.__version__)
# FIXME
# Should fetch schema from weewx.conf! bin/schemas
schema = [
    ('dateTime', 'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
    ('usUnits', 'INTEGER NOT NULL'),
    ('barometer', 'REAL'),
    ('pressure', 'REAL'),
    ('altimeter', 'REAL'),
    ('appTemp', 'REAL'),
    ('inTemp', 'REAL'),
    ('outTemp', 'REAL'),
    ('inHumidity', 'REAL'),
    ('outHumidity', 'REAL'),
    ('windSpeed', 'REAL'),
    ('windDir', 'REAL'),
    ('windGust', 'REAL'),
    ('windGustDir', 'REAL'),
    ('rainRate', 'REAL'),
    ('rain', 'REAL'),
    #('dayrain', 'REAL'),  # dayRain for DAVIS stations
    ('dewpoint', 'REAL'),
    ('windchill', 'REAL'),
    ('heatindex', 'REAL'),
    ('rxCheckPercent', 'REAL'),
    ('dayET', 'REAL'),  # ET
    ('radiation', 'REAL'),
    ('UV', 'REAL'),
    ('extraTemp1', 'REAL'),
    ('extraTemp2', 'REAL'),
    ('extraTemp3', 'REAL'),
    ('soilTemp1', 'REAL'),
    ('soilTemp2', 'REAL'),
    ('soilTemp3', 'REAL'),
    ('soilTemp4', 'REAL'),
    ('leafTemp1', 'REAL'),
    ('leafTemp2', 'REAL'),
    ('extraHumid1', 'REAL'),
    ('extraHumid2', 'REAL'),
    ('soilMoist1', 'REAL'),
    ('soilMoist2', 'REAL'),
    ('soilMoist3', 'REAL'),
    ('soilMoist4', 'REAL'),
    ('leafWet1', 'REAL'),
    ('leafWet2', 'REAL'),
    ('txBatteryStatus', 'REAL'),
    ('consBatteryVoltage', 'REAL'),
    ('hail', 'REAL'),
    ('hailRate', 'REAL'),
    ('heatingTemp', 'REAL'),
    ('heatingVoltage', 'REAL'),
    ('supplyVoltage', 'REAL'),
    ('referenceVoltage', 'REAL'),
    ('windBatteryStatus', 'REAL'),
    ('rainBatteryStatus', 'REAL'),
    ('outTempBatteryStatus', 'REAL'),
    ('inTempBatteryStatus', 'REAL')]


class SyncError(Exception):
    """
    Raised when a non-fatal synchronization error occurs.
    May succeed if retried.
    """


class FatalSyncError(Exception):
    """
    Raised when a fatal synchronization error occurs.
    Likely to occur again if retried.
    """


class AbortAndExit(Exception):
    """
    Raised when it's time to shut down the thread.
    """


class SyncService(weewx.engine.StdService):
    """
    Important...
    Original notes for SyncService.

    archive sync:
      premise
        data always sent in sequential order
        failures aren't tolerated (will either fail or retry forever on all
         errors)
      thread
        watches queue and publishes data to remote server in order
        IO failures result in a retry after X seconds, indefinitely
      back_fill
        on start up
          query remote server for most recent date
          sync all records since date to queue
        new archive packets
          date of packet added to queue (have to make sure it's not already
           sent by the back_fill)

    raw sync:
      premise
        data sent immediately from packet (not db)
        failures are tolerated (errors will skip)
      thread
        watches queue and publishes data to remote server
        IO failures are logged and skipped

    error handling
      3 general categories of errors:
        1) can't communicate w/server (IO)
        2) configuration/logical error (400 status response)
        3) unknown/unexpected error (500 status)
      all errors are possible when initially setting it up, but only #1
        and possibly #3 should occur after that, thus always fail for #2,
        and retry for #1 and #3

    TODO rename to meso sync as this is not general purpose

    *sync.py changes

    2015-11-02 Modified by Luc Heijst to work with weewx version 3.2.1
    09-02-2018     supply a user agent string to satisfy hosting servers

    ** May 2020

    The 3 original mesowx scripts have been combined into one script which are
    installed as a SLE - a skin named Mesowx, a script named mesowx.py and
    a database named mesowx.

    wee_extension will install and configure this skin as much as it can.
    Because it has control over the local setup ... Raw ... you will find
    that version fully configured and ready to view in your browser at
    http://localhost/weewx/mesowx/

    The skin is populated with values sourced from weewx.conf and the
    provided wee_extension install.py values. It applies them to both the
    Raw and RemoteSync versions.

    Local Installation.

    The local (Raw) mesowx database will be automatically generated and
    consists of just the raw (loop) table. The archive (REC) values will be
    sourced from your existing mysql weewx database.

    Once all the mesowx files are generated (45 of them) and transferred to
    your local web server the [StdReport][[Mesowx]] skin can be disabled by
    changing the enable = True stanza to...
    enable = False

    Why false? A working installation does not require that skin to be
    regenerated, it's a one time requirement; unless you later decide to
    change any of the [Mesowx] entries in weewx.conf in which case you'll need
    to renable the skin to allow the config files to be recreated.

    Remote Installation.

    The RemoteSync version will need action on your part as all the files that
    are generated and transferred to the local web server need to be
    transferred to your remote web server. This is the exact same directory and
    structure as the local, Raw version uses.
    (ie:- That www/html/weewx/mesowx directory is portable.)

    Copy that whole mesowx directory to your remote webserver and then; once
    all the files and directories are moved to that remote machine; then rename
    config-RemoteSync.json to config.json to allow that remote installation to
    work correctly.

    ie:- the file...

    mesowx/meso/include/config-RemoteSync.json

    needs to be renamed as...

    mesowx/meso/include/config.json

    With that done you should have a working installation; once the database
    is created and populated with data then you will know for certain.

    Enhance or Break??

    You now have a working setup, but it makes a few assumptions about fields
    and units. These can all be modified but you might end up with some
    breakage.

    As configured, it will only use the database fields as harcoded within the
    file config.json. They are listed under "columns", in two places. Once at
    line 58 for the archive table, then again at line 107 for the raw (loop)
    values.
    This is also one of the places to change the units, default is in US units.
    The other location is under mesowx/js/Config.js
    If you change from the defaults, by editing these files; then be careful as
    typos can be silent code breakers. Take a backup and use a lot of care.

    Testing the default installation
              (ie: excluding the above modifications).

    A quick test of the configuration is to point the browser to the remote
    site using...

    http://<your_site>/weewx/mesowx/meso/data.php?entity_id=weewx_archive&data=dateTime&order=desc&limit=1

    and a date should be returned...
    [[1592045160]]

    A database with nothing in it will return...
    []

    A database that doesn't exist will throw a Fatal error...
    Fatal error: Uncaught PDOException: SQLSTATE[HY000] [1049] Unknown database
    [...]
     /var/www/html/weewx/mesowx/meso/include/PDOConnectionFactory.class.php on
    line 31

    To create the remote database and give the appropriate permissions that
    match the wee_extension installation values, then...

    mysql -uroot -p
    create database mesowx;
    GRANT ALL ON *.* to mesowx@'localhost' IDENTIFIED BY 'weewx';
    quit;

    The remote mysql database - mesowx - contains 2 tables archive and raw
    (weewx, the mesowx.py script, will create those).
    The archive section should be copied from your existing weewx database via
    a mysqldump command, or other means.
    mesowx.py can backfill an empty database but it takes a long time to
    complete when you start from scratch. If it's too large it may refuse, or
    your machine may be brought to it's knees while the database is being
    queried.
    While it's doing that weewx will be stalled, no records generated,
    no graphs, nothing, nada, zilch. The only activity may be in your logs - if
    debug is turned on.

    Once the database is populated (or starting to be) then pointing your
    browser to the remote machines webserver mesowx/index.html file should
    result in a working mesowx website.


    To repeat:
        Use wee_extension to install MesoWX.
        Restart weewx
        Copy the webserver mesowx directories and files from the local
            webserver and place them into the remote servers path - keep the
            same directory paths as the local installation, unless you really
            know what you are doing.
        That will have created the remote website. Make sure the permissions
        are correct.
        Create the remote database, with permissions.
        Populate the remote database with the archive table from weewxs
            database, (that's all it requires from that database. The raw table
            will be created when he first loop value hits it.)
        Check the weewx.conf values are correct - pay attention to the site URL
            (Review the above hint)
        Restart weewx with debug turned on (debug = 1)
        Check your logs.
        Wait.

    Further notes:

    The backfill operation will perform a bulk transfer of historical records.
    It only runs on start up and only deals with archive (REC) records.
    You basically get one chance to do a (database) backfill operation.

    After that operation has finished (or been interrupted) the Queue takes
    over and archive and/or loop values will be available as weewx generates
    them.

    If the data flow to the remote server is interrupted, those records will
    be permanently dropped. Loop are gone forever, archive records will be
    available from the weewx database.
    (Loop values are already restricted to a 24 hour period before they are
    deleted from the database although 24 hours can be overridden in the
    weewx.conf [[Raw]] section).

    Restarting weewx will start the backfill operation again but if a current
    archive packet has been written to the remote database then as far as the
    backfill operation knows, all is golden. There is nothing for it to do.

    If you are certain there are gaps in the remote data, then you need to fill
    them manually. You could do a mysqldump style operation, or...
    You can stop weewx, delete everything at the remote end that covers the
    missing data upto the present time; then restart weewx and the backfill
    process should pick up on that deletion and perform the required backfill.

    There are 2 README files in the github repo (also in the downloaded zip
    file).
    If you have problems read those. They cover the history of the setup and
    while out of date they may fill in some knowledge gaps.

    RetainLoopValues.py is not a file I've ever used. It's included within
    this script, nothings been changed except to incorporate it as a function.

    Security: !!!

    You are responsible for security of your webserver.

    The installer will generate 2 random passwords and insert them into the
    script as well as the relevant config files. If you don't trust them change
    them but don't make any typos in the process or you will break the remote
    access granted to weewx and the database.

    With those passwords, and others available to anyone with webserver access,
    you need to prevent them being accessed.
    For the apache2 installation here I've added the following to
    /etc/apache2/apache2.conf to prevent the files being accessed.

    <Directory /var/www/html/weewx/mesowx>
            Options -Indexes
            AllowOverride None
            Require all granted
    </Directory>

    You will need to do the same, or similar depending on your webserver and
    installation. You'll then check that it does what is intended.

    Finally:

    Bug reports to github...

    https://github.com/glennmckechnie/weewx-mesowx

    Comments, enhancements, code for conversion to use MQTT :-))
    Send them to github. Failing that weewx-user.

    """

    def __init__(self, engine, config_dict):
        super(SyncService, self).__init__(engine, config_dict)
        loginf("remote sync: service version is %s" % VERSION)
        self.engine = engine
        self.config_dict = config_dict
        self.sync_config = self.config_dict['Mesowx']['RemoteSync']
        # used to signal the thread to exit, see shutDown()
        self.exit_event = threading.Event()
        self.archive_queue = queue.Queue()
        self.raw_queue = queue.Queue()
        # keeps track of the dateTime of the last loop packet seen in order to
        # prevent sending packets with the same dateTime value, see
        # new_loop_packet() for more info
        self.lastLoopDateTime = 0
        # supply a user agent string to satisfy hosting servers
        self.u_agent= ({'User-Agent':'MesoWX/0.6.3 (https://github.com/glennmckechnie/weewx-mesowx)'})
        # self.u_agent= ({'User-Agent':'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:76.0) Gecko/20100101 Firefox/76.0'})
        # using a http connection pool to potentially save some overhead and
        # server burden if keep alive is enabled, maxsize is set to 2 since
        # there are two threads using the pool. Note that keep alive will need
        # to be longer than the loop interval to be effective (which may not
        # make sense for longer intervals)
        self.http_pool = urllib3.connectionpool.connection_from_url(
                         self.sync_config['remote_server_url'],
                         maxsize=2, headers=self.u_agent)
        # the maximum number of reords to back_fill (defualt: no limit)
        self.backfill_limit = int(self.sync_config.get(
                              'archive_backfill_limit', 0))
        # the max number of records to send in a request (default: 200)
        self.batch_size = int(self.sync_config.get('archive_batch_size', 200))
        # the path on the remote server of the data update api (usually won't
        # ever change this)
        self.update_url_path = self.sync_config.get('server_update_path',
                                                    "updateData.php")
        # default number of times to retry http requests before giving up
        self.http_max_tries = 3
        # default time to wait in seconds before retrying http requests
        self.http_retry_interval = 0
        # the base url of the remote server to sync to
        self.remote_server_url = self.sync_config['remote_server_url']
        # the url that will be used to update data to on the remote server
        self.update_url = self.remote_server_url + self.update_url_path
        # the url that will be used to query for the latest dateTime on the
        # remote server the path on the remote server of the data query api
        # (usually won't ever change this)
        self.server_data_path = self.sync_config.get('server_data_path',
                                                     "data.php")
        self.latest_url = self.remote_server_url + self.server_data_path
        # the number of seconds to wait between sending batches
        # (default .5 seconds)
        self.batch_send_interval = float(self.sync_config.get(
                                   'archive_batch_send_interval', 0.5))
        # the entity id to sync to on the remote server
        self.entity_id = self.sync_config.get('archive_entity_id')
        # the security key that will be sent along with updates to the entity
        self.security_key = self.sync_config['archive_security_key']
        # Last dateTime synced records on webserver
        global last_datetime_synced
        last_datetime_synced = None
        # Open default database
        self.dbm = self.engine.db_binder.get_manager()

        # if an archive_entity_id is configured, then back-fill missed records
        # and bind & create the thead to sync archive records
        if self.entity_id:
            # back_fill missed records on webserver
            self.back_fill()
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
            self.archive_thread = ArchiveSyncThread(self.archive_queue,
                                                    self.exit_event,
                                                    self.http_pool,
                                                    **self.sync_config)
            self.archive_thread.start()
            loginf("remote sync of archive records is enabled")
        else:
            logdbg("won't sync archive rec (archive_entity_id not configured)")

        # if a raw_entity_id is configured, then bind & create the thead to
        # sync raw records
        if 'raw_entity_id' in self.sync_config:
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
            self.raw_thread = RawSyncThread(self.raw_queue,
                                            self.exit_event,
                                            self.http_pool,
                                            **self.sync_config)
            self.raw_thread.start()
            loginf("remote sync of raw (loop) records is enabled")
        else:
            logdbg("won't sync raw records (raw_entity_id not configured)")

    def new_archive_record(self, event):
        if self.archive_thread.isAlive():
            self.archive_queue.put(event.record)
            logdbg("remote archive: put record in queue %s" %
                   weeutil.weeutil.timestamp_to_string(
                    event.record['dateTime']))
        else:
            logerr("remote: not syncing archive record (%d) "
                   "due to previous error." % event.record['dateTime'])

    def new_loop_packet(self, event):
        if self.raw_thread.isAlive():
            packet = event.packet
            # It's possible for records with duplicate dateTimes - this occurs
            # when an archive packet  is processed since the LOOP packets are
            # queued up and then returned immediately when looping resumes,
            # coupled with the fact that for Vantage Pro consoles the dateTime
            # value is added by weewx. So, for database storage, skip the
            # duplicates until we get a new one to avoid a duplicate key error
            date_time = packet['dateTime']
            if date_time != self.lastLoopDateTime:
                self.raw_queue.put(packet)
                self.lastLoopDateTime = date_time
        # not going to spam the logs by logging each time we don't sync one
        # due to frequency

    def shutDown(self):
        """Shut down the sync threads"""
        # signal the threads to shutdown
        self.exit_event.set()
        self.archive_queue.put(None)
        self.raw_queue.put(None)
        # join the threads
        self._join_thread(self.archive_thread)
        self._join_thread(self.raw_thread)
        # close the http pool
        self.http_pool.close()

    @staticmethod
    def _join_thread(thread):
        if thread is not None and thread.isAlive():
            # Wait up to 20 seconds for the thread to exit:
            thread.join(20.0)
            if thread.isAlive():
                logerr("sync: Unable to shut down syncing thread: %s" %
                       thread.name)
            else:
                logdbg("sync: Shut down syncing thread: %s" %
                       thread.name)

    def back_fill(self):
        global last_datetime_synced
        last_datetime_synced = self.fetch_latest_remote_datetime()
        # last_datetime_synced = int("1593342453") # Hmmm, debug left in ??
        if last_datetime_synced is None:
            num_to_sync = self.dbm.getSql("select count(*) from %s" %
                                          self.dbm.table_name)[0]
        else:
            num_to_sync = self.dbm.getSql("select count(*) from %s "
                                          "where dateTime > ?" %
                                          self.dbm.table_name,
                                          (last_datetime_synced,))[0]
        logdbg("remote: %d records to sync since last record "
               "with dateTime: %s" %
               (num_to_sync, weeutil.weeutil.timestamp_to_string(
                last_datetime_synced)))
        if num_to_sync > 0:
            if self.backfill_limit is not None and self.backfill_limit != 0 \
                        and num_to_sync[0] > self.backfill_limit:
            # except FatalSyncError:
                loginf("remote: Too many to sync: %d exeeds the limit of %d" %
                       (num_to_sync, self.backfill_limit))
            #      raise
            else:
                logdbg("remote: back_filling %d records" % num_to_sync)
                self.sync_all_since_datetime(last_datetime_synced)
                logdbg("remote: done back_filling %d records" %
                       num_to_sync)

    def sync_all_since_datetime(self, datetime):
        global last_datetime_synced
        if datetime is None:
            query = self.dbm.genSql("select * from %s order by dateTime asc" %
                                    self.dbm.table_name)
        else:
            query = self.dbm.genSql("select * from %s where "
                                    "dateTime > ? order by dateTime asc" %
                                    self.dbm.table_name, (datetime,))
        total_sent = 0
        while True:
            batch = []
            for row in itertools.islice(query, self.batch_size):
                datadict = dict(zip(self.dbm.sqlkeys, row))
                batch.append(datadict)
            if len(batch) > 0:
                self.post_records(batch)
                total_sent += len(batch)
                last_datetime_synced = batch[len(batch)-1]['dateTime']
                # XXX add start/end datetime to log message
                logdbg("remote: back_filled %d records; "
                       "timestamp last record: %s" %
                       (total_sent, weeutil.weeutil.timestamp_to_string(
                        last_datetime_synced)))
            else:
                # no more to send
                break
            # breath a bit so as not to bombard the remote server. Also
            # back_filling could take some time, so make sure an exit event
            # hasn't been signaled
            self._wait(self.batch_send_interval)

    def fetch_latest_remote_datetime(self):
        logdbg("remote backfill: requesting latest dateTime from %s" %
               self.latest_url)
        # A valid timestamp to be used to halt the backfill on an invalid
        # json response (which means no datetime was returned)
        current_time = int(time.time())
        # the entity id to sync to on the remote server
        # redundant # self.entity_id = self.sync_config['archive_entity_id']
        # the security key that will be sent along with updates to the entity
        # red'nt # self.security_key = self.sync_config['archive_security_key']
        # http://wxdev.ruskers.com/
        # data.php?entity_id=weewx_archive&data=dateTime&order=desc&limit=1
        postdata = {'entity_id': self.entity_id, 'data': 'dateTime',
                    'order': 'desc', 'limit': 1}
        http_response = self.make_http_request(self.latest_url, postdata)
        try:
            response_json = http_response.data.decode('utf-8')
        except Exception as e:
            # NoneType object has no attribute data - server not responding
            logdbg("remote: Exception as %s" % e)
            logerr("remote backfill: no datetime available. Returning current"
                   " time %s to halt any backfill operation."
                   " ( is the server running? )" % current_time)
            return current_time
        try:
            response = json.loads(response_json)
        except Exception as e:
            logerr("remote: no datetime available: http response.data % and "
                   "error %s" % (response_json, e))
            return current_time
            # datetime = None
            # return
        if len(response) == 0:
            datetime = None
        else:
            datetime = response[0][0]
        return datetime

    def post_records(self, records):
        datajson = json.dumps(records)
        postdata = {'entity_id': self.entity_id, 'data': datajson,
                    'security_key': self.security_key}
        self.backfill_http_request(self.update_url, postdata)

    def backfill_http_request(self, url, postdata):
        # data.php (backfilling)
        for count in range(self.http_max_tries):
            try:
                response = self.http_pool.request('POST', url, postdata)
                logdbg("backfill: archive http response.data %s" %
                       response.data)
                if response.status == 200:
                    return response
                else:
                    # from here must either set retry=True or raise a
                    # FatalSyncError
                    logerr("backfill: http request failed (%s %s): %s" %
                           (response.status,
                            response.reason,
                            response.data))
                    if response.status >= 500:
                        # Don't retry if Duplicate entry error
                        if response.data.find(b'Duplicate entry') >= 0:
                            # continue
                            return response
                        else:
                            retry = True
                    else:
                        message = ("backfill: Request to %s failed, server "
                                   "returned %s status with reason '%s'." %
                                   (url, response.status, response.reason))
                        # invalid credentials
                        if response.status == 403:
                            message += " Do your entity security keys match?"
                        # page not found
                        if response.status == 404:
                            message += " Is the url correct?"
                        # bad request (likely an invalid setup)
                        if response.status == 400:
                            message += " Check your entity configuration."
                        loginf(message)
                        # don't retry on these errors
                        retry = False
            except (urllib3.exceptions.NewConnectionError) as e:
                logerr("backfill: failed to connect to %s" % url)
                logdbg("   ****  Reason: %s" % (e,))
                retry = False  # if we can't find it on start up, assume *we*
                               # made an error and stop retrying
            except (urllib3.exceptions.MaxRetryError) as e:
                logerr("backfill: failed http request attempt #%d to %s" % (
                       count+1, url))
                logdbg("   ****  Reason: %s" % (e,))
                retry = True
            if retry and count+1 < self.http_max_tries:
                # wait a bit before retrying, ensuring that we exit if signaled
                logdbg("backfill: retrying again in %s seconds" % (
                       self.http_retry_interval,))
                self._wait(self.http_retry_interval)
        else:
            logerr("backfill: failed to invoke %s after %d tries" % (
                   url, self.http_max_tries))

    def _wait(self, duration):
        if duration is not None:
            if self.exit_event.wait(duration):
                logdbg("backfill: exit event signaled, aborting")
                raise AbortAndExit


class SyncThread(threading.Thread):
    """
    It's a Threading thread so some duplicated code appears to be present - but
    a threading thread *is* a duplicate so it remains...such is life.
    """
    def __init__(self, queue, exit_event, http_pool,
                 thread_name="SyncThread", **sync_params):
        threading.Thread.__init__(self, name=thread_name)
        self.setDaemon(True)
        self.queue = queue
        self.exit_event = exit_event
        self.http_pool = http_pool
        # the base url of the remote server to sync to
        self.remote_server_url = sync_params['remote_server_url']
        # the path on the remote server of the data update api (usually won't
        # ever change this)
        self.update_url_path = sync_params.get('server_update_path',
                                               "updateData.php")
        # the entity_id and security_key must be set by sub-classes
        self.entity_id = None
        self.security_key = None
        # default number of times to retry http requests before giving up
        self.http_max_tries = 3
        # default time to wait in seconds before retrying http requests
        self.http_retry_interval = 0
        # the url that will be used to update data to on the remote server
        self.update_url = self.remote_server_url + self.update_url_path

    def run(self):
        try:
            self._run()
        except AbortAndExit:
            logdbg("sync: thread shutting down")
            return
        except FatalSyncError as e:
            logerr("sync: fatal syncronization error")
            logerr("   ****  Reason: %s" % (e,))
            return
        except Exception as e:
            logerr("sync: unexpected error: %s" % (e,))
            weeutil.logger.log_traceback("   ****  ")
            logerr("   ****  Thread terminating.")
            raise

    def _run(self):
        pass

    def post_records(self, records):
        datajson = json.dumps(records)
        postdata = {'entity_id': self.entity_id, 'data': datajson,
                    'security_key': self.security_key}
        self.make_http_request(self.update_url, postdata)

    def make_http_request(self, url, postdata):
        # updatedata.php (loop, raw data, real time)
        for count in range(self.http_max_tries):
            try:
                response = self.http_pool.request('POST', url, postdata)
                logdbg("loop: http response.data %s" % response.data)
                logdbg("loop: http response.status %s" % response.status)
                logdbg("loop: http response.reason %s" % response.reason)
                if response.status == 200:
                    return response
                else:
                    # from here must either set retry=True or raise a
                    # FatalSyncError
                    logerr("loop: http request failed (%s %s): %s" %
                           (response.status,
                            response.reason,
                            response.data))
                    if response.status >= 500:
                        # Don't retry if Duplicate entry error
                        if response.data.find(b'Duplicate entry') >= 0:
                            # continue
                            return response
                        else:
                            retry = True
                    else:
                        message = ("loop: Request to %s failed, server "
                                   "returned %s status with reason '%s'." %
                                   (url, response.status, response.reason))
                        # invalid credentials
                        if response.status == 403:
                            message += " Do your entity security keys match?"
                        # page not found
                        if response.status == 404:
                            message += " Is the url correct?"
                        # bad request (likely an invalid setup)
                        if response.status == 400:
                            message += " Check your entity configuration."
                        loginf(message)
                        retry = False
            except (urllib3.exceptions.NewConnectionError) as e:
                logerr("loop: failed to connect to %s" % url)
                logdbg("   ****  Reason: %s" % (e,))
                retry = True  # maybe only a temporary outage.
            except (urllib3.exceptions.MaxRetryError) as e:
                logerr("loop: failed http request attempt #%d to %s" % (
                       count+1, url))
                logdbg("   ****  Reason: %s" % (e,))
                retry = True
            if retry and count+1 < self.http_max_tries:
                # wait a bit before retrying, ensuring that we exit if signaled
                logdbg("loop: retrying again in %s seconds" % (
                       self.http_retry_interval,))
                self._wait(self.http_retry_interval)
        else:
            loginf("loop: Failed to invoke %s after %d tries" % (
                   url, self.http_max_tries))

    def _wait(self, duration):
        if duration is not None:
            if self.exit_event.wait(duration):
                logdbg("sync: exit event signaled, aborting")
                raise AbortAndExit


class RawSyncThread(SyncThread):

    def __init__(self, queue, exit_event, http_pool, **sync_params):
        SyncThread.__init__(self, queue, exit_event, http_pool,
                            "RawSyncThread", **sync_params)
        # the entity id to sync to on the remote server
        self.entity_id = sync_params['raw_entity_id']
        # the security key that will be sent along with updates to the entity
        self.security_key = sync_params['raw_security_key']
        # time to wait in seconds before retrying http requests
        self.http_retry_interval = float(sync_params.get(
                                   'raw_http_retry_interval',
                                   self.http_retry_interval))
        # number of times to retry http requests (default: 1)
        self.http_max_tries = int(sync_params.get('raw_http_max_tries', 1))
        self.debug_count = 0
        self.max_times_to_print = 5

    def _run(self):
        self.sync_queued_records()

    def sync_queued_records(self):
        logdbg("sync raw: waiting for new records")
        while True:
            try:
                # XXX always empty the queue - send as a batch
                # XXX option to always send in a batch, wait for X records
                # before sending
                raw_record = self.queue.get()
                # a value of None is a signal to exit
                if raw_record is None:
                    logdbg("remote raw: exit event signaled, exiting "
                           "queue loop")
                    raise AbortAndExit
                self.debug_count += 1
                if self.debug_count <= self.max_times_to_print:
                    logdbg("remote raw: send record %s" %
                           (weeutil.weeutil.timestamp_to_string(
                            raw_record['dateTime'])))
                if self.debug_count == self.max_times_to_print:
                    logdbg("remote raw: print message above only the "
                           "first %s times" %
                           self.max_times_to_print)
                self.post_records(raw_record)
            except SyncError as e:
                logerr("remote raw: unable to sync record, skipping")
                logerr("   ****  Reason: %s" % (e,))
            finally:
                # mark the queue item as done whether it succeeded or not
                self.queue.task_done()


class ArchiveSyncThread(SyncThread):

    # has a queue used by the service to add new archive records as they arrive
    # run
    #    query for latest remote date
    #    send data since that date
    #    then load data from queue
    def __init__(self, queue, exit_event, http_pool, **sync_params):
        SyncThread.__init__(self, queue, exit_event, http_pool,
                            "ArchiveSyncThread", **sync_params)

        # the path on the remote server of the data query api (usually won't
        # ever change this)
        self.server_data_path = sync_params.get('server_data_path', "data.php")
        # the entity id to sync to on the remote server
        self.entity_id = sync_params['archive_entity_id']
        # the security key that will be sent along with updates to the entity
        self.security_key = sync_params['archive_security_key']
        # time to wait in seconds before retrying http requests
        # (default: 1 minute)
        self.http_retry_interval = float(sync_params.get(
                                   'archive_http_retry_interval', 60))
        # number of times to retry http requests before giving up for a while
        # (default: 10)
        self.http_max_tries = int(sync_params.get(
                              'archive_http_max_tries', 10))
        # time to wait in seconds before retrying after a failure
        # (default: 15 minutes)
        self.failure_retry_interval = float(sync_params.get(
                                      'archive_failure_retry_interval', 900))
        # the url that will be used to query for the latest dateTime on the
        # remote server
        self.latest_url = self.remote_server_url + self.server_data_path
        # the datetime of the most recently synced archive record, this is
        # used to prevent potentially re-sending queued records that a
        # back_fill already sent (the queue is still populated during this
        # process)

    def _run(self):
        while True:
            try:
                self.sync_queued_records()
            except SyncError as e:
                logerr("remote archive: synchronization failed, starting "
                       "over in %s seconds" %
                       self.failure_retry_interval)
                logerr("   ****  Reason: %s" % (e,))
                self._wait(self.failure_retry_interval)

    def sync_queued_records(self):
        global last_datetime_synced
        logdbg("remote archive: waiting for new records")
        while True:
            try:
                archive_record = self.queue.get()
                # a value of None is a signal to exit
                if archive_record is None:
                    logdbg("remote archive: exit event signaled, "
                           "exiting queue loop")
                    raise AbortAndExit
                logdbg("remote archive: get record %s; last synced %s" %
                       (weeutil.weeutil.timestamp_to_string(
                        archive_record['dateTime']),
                        weeutil.weeutil.timestamp_to_string(
                        last_datetime_synced)))
                if last_datetime_synced is not None and (
                        archive_record['dateTime'] <= last_datetime_synced):
                    logdbg("remote archive: skip already synced record %s" %
                           weeutil.weeutil.timestamp_to_string(
                            archive_record['dateTime']))
                else:
                    logdbg("remote archive: send record %s" %
                           weeutil.weeutil.timestamp_to_string(
                            archive_record['dateTime']))
                    self.post_records(archive_record)
            finally:
                # mark the queue item as done whether it succeeded or not
                self.queue.task_done()

###############################
# start of original raw.0.4.1-lh.py script
################################
# VERSION = "0.4.1-lh"
#
# 2015-12-28 Modified by Luc Heijst to work with weewx version 3.3.1
#


class RawService(StdService):

    def __init__(self, engine, config_dict):
        super(RawService, self).__init__(engine, config_dict)
        loginf("local raw: service version is %s" % VERSION)

        self.config_dict = config_dict
        d = self.config_dict['Mesowx']['Raw']
        self.dataLimit = int(d.get('data_limit', 24))
        self.skip_loop = int(d.get('skip_loop', 2))

        # get the database parameters we need to function
        # self.binding = self.config_dict['DataBindings'].get('mesowx_binding')
        self.data_binding = self.config_dict.get('data_binding',
                                                 'mesowx_binding')
        # loginf("self.binding = %s" % self.data_binding)
        self.dbm = self.engine.db_binder.get_manager(
                   data_binding=self.data_binding,
                   initialize=True)

        # be sure schema in database matches the schema we have
        dbcol = self.dbm.connection.columnsOf(self.dbm.table_name)
        dbm_dict = weewx.manager.get_manager_dict(
            config_dict['DataBindings'], config_dict['Databases'],
            self.data_binding)
        # loginf("dbm_dict is %s" % dbm_dict)
        memcol = [x[0] for x in dbm_dict['schema']]
        if dbcol != memcol:
            raise Exception('mesowx raw: schema mismatch: %s != %s' %
                            (dbcol, memcol))

        self.lastLoopDateTime = 0
        self.lastPrunedDateTime = 0
        self.bind(weewx.NEW_LOOP_PACKET, self.newLoopPacket)

    def prune_rawdata(self, dbm, ts, max_tries=3, retry_wait=10):
        """remove rawdata older than data_limit hours from the database"""
        sql = "delete from %s where dateTime < %d" % (dbm.table_name, ts)
        for count in range(max_tries):
            try:
                dbm.getSql(sql)
                loginf('local raw: deleted rawdata prior to %s' %
                       weeutil.weeutil.timestamp_to_string(ts))
                break
            except Exception as e:
                logerr("local raw: prune failed (attempt %d of %d): %s" %
                       ((count + 1), max_tries, e))
                loginf("local raw: waiting %d seconds before retry" %
                       retry_wait)
                time.sleep(retry_wait)
        else:
            raise Exception('local raw: prune failed after %d attemps' %
                            max_tries)

    def newLoopPacket(self, event):
        packet = event.packet
        prune_period = 300
        # It's possible for records with duplicate dateTimes - this occurs when
        # an archive packet is processed since the LOOP packets are queued up
        # and then returned immediately when looping resumes, coupled with the
        # fact that for Vantage Pro consoles the dateTime value is added by
        # weewx. So, for database storage, skip the duplicates until we get a
        # new one to avoid a duplicate key error, but publish them all to avoid
        # a duplicate key error
        dateTime = packet['dateTime']
        # loginf('if dateTime (%s) > lastloopDateTime + 42 (%s)' % (dateTime,
        #        (self.lastLoopDateTime +42)))
        if dateTime > (self.lastLoopDateTime + self.skip_loop):
            self.dbm.addRecord(packet)
            self.lastLoopDateTime = dateTime
        if dateTime > (self.lastPrunedDateTime + prune_period):
            if self.dataLimit is not None:
                ts = ((dateTime - (self.dataLimit * 3600)) /
                      prune_period) * prune_period  # preset on 5-min boundary
                self.prune_rawdata(self.dbm, ts, 2, 5)
            self.lastPrunedDateTime = dateTime

# LOOP packet data example #
#   {
#      'monthET' : 0.0,
#      'dewpoint' : 32.89591611995311,
#      'yearET' : 0.0,
#      'outHumidity' : 88.0,
#      'rain' : 0.0,
#      'dayET' : 0.0,
#      'consBatteryVoltage' : 4.67,
#      'extraTemp2' : None,
#      'monthRain' : 0.24,
#      'insideAlarm' : 0,
#      'barometer' : 30.217,
#      'dateTime' : 1352423356,
#      'stormRain' : 0.0,
#      'extraTemp4' : None,
#      'sunrise' : 1352380980,
#      'windchill' : 36.1,
#      'windDir' : 260.0,
#      'extraTemp5' : None,
#      'extraTemp3' : None,
#      'outTemp' : 36.1,
#      'outsideAlarm1' : 0,
#      'rainRate' : 0.0,
#      'outsideAlarm2' : 0,
#      'radiation' : None,
#      'forecastRule' : 9,
#      'leafTemp2' : None,
#      'rainAlarm' : 0,
#      'stormStart' : None,
#      'inTemp' : 69.6,
#      'inHumidity' : 45.0,
#      'windSpeed10' : 0.0,
#      'yearRain' : 34.52,
#      'extraAlarm1' : 0,
#      'extraAlarm2' : 0,
#      'extraAlarm3' : 0,
#      'extraAlarm4' : 0,
#      'extraAlarm5' : 0,
#      'extraAlarm6' : 0,
#      'extraAlarm7' : 0,
#      'extraAlarm8' : 0,
#      'soilTemp1' : None,
#      'soilTemp2' : None,
#      'soilTemp3' : None,
#      'soilTemp4' : None,
#      'soilLeafAlarm2' : 0,
#      'extraHumid6' : None,
#      'extraHumid7' : None,
#      'extraHumid4' : None,
#      'extraHumid5' : None,
#      'extraHumid2' : None,
#      'extraHumid3' : None,
#      'extraHumid1' : None,
#      'extraTemp6' : None,
#      'extraTemp7' : None,
#      'soilLeafAlarm4' : 0,
#      'leafTemp4' : None,
#      'leafTemp3' : None,
#      'soilLeafAlarm3' : 0,
#      'leafTemp1' : None,
#      'extraTemp1' : None,
#      'leafWet4' : 0.0,
#      'forecastIcon' : 6,
#      'soilLeafAlarm1' : 0,
#      'leafWet1' : 0.0,
#      'leafWet2' : 0.0,
#      'txBatteryStatus' : 0,
#      'leafWet3' : 0.0,
#      'heatindex' : 36.1,
#      'UV' : None,
#      'dayRain' : 0.01,
#      'soilMoist3' : 0.0,
#      'soilMoist2' : 0.0,
#      'soilMoist1' : 0.0,
#      'sunset' : 1352417700,
#      'windSpeed' : 0.0,
#      'soilMoist4' : 0.0,
#      'usUnits' : 1
#   }


# start of original retain.py script

class RetainLoopValues(StdService):
    """Service retains previous loop packet values updating any value that
    isn't None from new packets. It then replaces the original packet with a
    new packet that contains all of the values; the original unmodified packet
    will be stored on the event in a property named 'originalPacket'."""

    def __init__(self, engine, config_dict):
        super(RetainLoopValues, self).__init__(engine, config_dict)
        self.bind(weewx.NEW_LOOP_PACKET, self.newLoopPacket)
        self.retainedLoopValues = {}
        self.excludeFields = set([])
        if 'RetainLoopValues' in config_dict:
            if 'exclude_fields' in config_dict['Mesowx']['RetainLoopValues']:
                self.excludeFields = set(weeutil.weeutil.option_as_list
                                         (config_dict['Mesowx']
                                          ['RetainLoopValues'].get
                                          ('exclude_fields', [])))
                loginf("mesowx RetainLoopValues: excluding fields: %s" %
                       (self.excludeFields,))

    def newLoopPacket(self, event):
        event.originalPacket = event.packet
        # replace the values in the retained packet if they have a value other
        # than None or the field is listed in excludeFields
        self.retainedLoopValues.update(dict((k, v) for k, v in
                                            event.packet.iteritems() if
                                            (v is not None or k in
                                             self.excludeFields)))
        # if the new packet doesn't contain one of the excludeFields then
        # remove it from the retainedLoopValues
        for k in self.excludeFields - set(event.packet.keys()):
            if k in self.retainedLoopValues:
                self.retainedLoopValues.pop(k)
        event.packet = self.retainedLoopValues.copy()


class Mesowx(SearchList):
    """
    Weewx essential
    This generates values for cheetah to work its magic and allows the original
    mesowx scripts to be incorporated (seamlessly) into weewx via wee_extension
    weewx.conf and the install.py file.
    """
    def __init__(self, generator):
        SearchList.__init__(self, generator)
        """
        """
        self.mesowx_version = VERSION
        loginf('Version is %s' % (self.mesowx_version))

        self.mesowx_dbase = self.generator.config_dict[
                            'DataBindings'][
                            'mesowx_binding'].get('database', 'mesowx_mysql')
        self.mesowx_data = self.generator.config_dict[
                           'Databases'][
                           'mesowx_mysql'].get('database_name', 'mesowx')
        self.mesowx_table = self.generator.config_dict[
                           'Databases']['mesowx_mysql'].get('table_name',
                                                            'raw')
        self.weewx_conf = self.generator.config_dict['DatabaseTypes']['MySQL']
        self.weewx_host = self.weewx_conf.get('host', 'localhost')
        self.weewx_user = self.weewx_conf.get('user', 'weewx')
        self.weewx_pass = self.weewx_conf.get('password', 'weewx')
        self.weewx_data = self.generator.config_dict[
                          'Databases'][
                          'archive_mysql'].get('database_name', 'weewx')

        self.sync_config = self.generator.config_dict['Mesowx']['RemoteSync']
        self.weewx_archive = self.sync_config.get('archive_identity_id',
                                                  'weewx_archive')
        self.weewx_raw = self.sync_config.get('raw_identity_id_', 'weewx_raw')
        self.mesowx_host = self.sync_config.get('mesowx_host', 'localhost')
        self.mesowx_user = self.sync_config.get('mesowx_user', 'mesowx')
        self.mesowx_pass = self.sync_config.get('mesowx_pass', 'weewx')

        self.data_limit = int(self.generator.config_dict[
                                  'Mesowx']['Raw'].get('data_limit', 24))
        # retention policy limit for raw database, in seconds
        self.data_limit_seconds = int(self.data_limit * 3600)
        # polling interval: time between loop packets in seconds (for dash
        # refresh rate)
        self.poll_ms = int(self.generator.config_dict['Mesowx'].get(
                       'loop_polling_interval', '60')) * 1000
        wee_units = self.generator.config_dict['StdConvert'].get(
                         'target_unit', 'METRICWX')

        def allot_colors():
            for _k, _i in chart_colors.items():
                if "out_temp" in _k:
                    self.out_temp = _i
                elif "bar_ometer" in _k:
                    self.bar_ometer = _i
                elif "wind_speed" in _k:
                    self.wind_speed = _i
                elif "wind_dir" in _k:
                    self.wind_dir = _i
                elif "r_ain" in _k:
                    self.r_ain = _i
                elif "rain_rate" in _k:
                    self.rain_rate = _i
                elif "out_humidity" in _k:
                    self.out_humidity = _i
                elif "in_temp" in _k:
                    self.in_temp = _i
                elif "dew_point" in _k:
                    self.dew_point = _i
                elif "wind_chill" in _k:
                    self.wind_chill = _i
                elif "heat_index" in _k:
                    self.heat_index = _i
                elif "wind_gustdir" in _k:
                    self.wind_gustdir = _i
                elif "wind_gust" in _k:
                    self.wind_gust = _i
                elif "day_rain" in _k:
                    self.day_rain = _i
                elif "in_humidity" in _k:
                    self.in_humidity = _i
            return

        chart_colors = self.generator.skin_dict.get('ChartColors', {})

        # Fetch one of two default color pallets, or use a configurable set
        color_default_a = weeutil.weeutil.to_bool(self.generator.skin_dict[
                          'ChartColors'].get('colorset_a', 'false'))
        color_default_b = weeutil.weeutil.to_bool(self.generator.skin_dict[
                          'ChartColors'].get('colorset_b', 'false'))
        # the third, itemized option is the last 'else:' option and is user
        # configurable.

        if color_default_a:
            chart_colors = {'out_temp': '#2f7ed8',  'bar_ometer': '#0d233a',
                            'wind_speed': '#8bbc21', 'wind_dir': '#910000',
                            'r_ain': '#1aadce', 'rain_rate': '#492970',
                            'out_humidity': '#f28f43', 'in_temp': '#77a1e5',
                            'dew_point': '#c42525', 'wind_chill': '#a6c96a',
                            'heat_index': '#4572A7', 'wind_gust': '#AA4643',
                            'wind_gustdir': '#89A54E', 'day_rain': '#80699B',
                            'in_humidity': '#3D96AE'}
            # logdbg("Using chart_color_a which  are %s : %s" % (
            #                             color_default_a, chart_colors))
            allot_colors()
        elif color_default_b:
            chart_colors = {'out_temp': '#DB843D', 'bar_ometer': '#92A8CD',
                            'wind_speed': '#A47D7C', 'wind_dir': '#B5CA92',
                            'r_ain': '#7cb5ec', 'rain_rate': '#434348',
                            'out_humidity': '#90ed7d', 'in_temp':  '#f7a35c',
                            'dew_point': '#8085e9', 'wind_chill':  '#f15c80',
                            'heat_index': '#e4d354', 'wind_gust': '#2b908f',
                            'wind_gustdir': '#f45b5b', 'day_rain': '#91e8e1',
                            'in_humidity': ' #2f7ed8'}
            # logdbg("Using chart_color_b which are %s : %s" % (
            #                             color_default_b, chart_colors))
            allot_colors()
        else:
            chart_colors = self.generator.skin_dict.get('ChartColors', {})
            # logdbg("Using chart_color c are %s" % chart_colors)
            allot_colors()

        # logdbg("in_humidity is %s" % self.in_humidity) # quick sanity check

        # database units and display units may differ
        """
        Units that are available in Units.class.php
        along with the chosen target / base and according to weewx
        US, Metric, MetricWX
        f , c , c
        inHg , (mb , hPa), mmHg , kPa
        in , cm , mm
        inHr , cmHr , mmHr
        mph , kph , mps  : knot
        deg, deg, deg
        perc, perc, perc
        s , ms
        """
        # single digit entries (p_f, m_f, rr_f) are decimal format instructions
        if 'US' in wee_units:
            self.degr = self.disp_degr = 'f'
            self.press = self.disp_press = 'inHg'
            self.p_f = self.disp_p_f = '3'
            self.meas = self.disp_meas = 'in'
            self.m_f = self.disp_m_f = '2'
            self.speed = self.disp_speed = 'mph'
            self.rainR = self.disp_rainR = 'inHr'
            self.rr_f = self.disp_rr_f = '2'
        elif 'METRICWX' in wee_units:
            self.degr = self.disp_degr = 'c'
            self.press = self.disp_press = 'hPa'
            self.p_f = self.disp_p_f = '1'
            self.meas = self.disp_meas = 'mm'
            self.m_f = self.disp_m_f = '1'
            # self.speed = self.disp_speed = 'mps' # owfs returns mps if under METRICWX
            self.speed = self.disp_speed = 'kph'
            self.rainR = self.disp_rainR = 'mmHr'
            self.rr_f = self.disp_rr_f = '1'
        else:  # it must be METRIC !
            self.degr = self.disp_degr = 'c'
            self.press = self.disp_press = 'hPa'
            self.p_f = self.disp_p_f = '1'
            self.meas = self.disp_meas = 'cm'
            self.m_f = self.disp_m_f = '1'
            self.speed = self.disp_speed = 'kph'
            self.rainR = self.disp_rainR = 'cmHr'
            self.rr_f = self.disp_rr_f = '1'

        # fallback to the database units above if these next ones (used in
        # the actual display) are missing or foobar'd
        #
        # these are from meso/include/Units.class.php
        available_units = ('f', 'c', 'inHg', 'mb', 'hPa', 'mmHg',
                           'kPa', 'in', 'cm', 'mm', 'inHr', 'cmHr',
                           'mmHr', 'mph', 'kph', 'mps', 'knot')
        # degrees
        disp_degr = self.generator.skin_dict['Units'].get(
                                               'display_temp', self.degr)
        if disp_degr in available_units:
            self.disp_degr = disp_degr
        # pressure
        disp_press = self.generator.skin_dict['Units'].get(
                                               'display_pressure', self.press)
        if disp_press in available_units:
            self.disp_press = disp_press
        # measure (rain)
        disp_meas = self.generator.skin_dict['Units'].get(
                                               'display_rain', self.meas)
        if disp_meas in available_units:
            self.disp_meas = disp_meas
        # speed
        disp_speed = self.generator.skin_dict['Units'].get(
                                               'display_speed', self.speed)
        if disp_speed in available_units:
            self.disp_speed = disp_speed
        # rain rate
        disp_rainR = self.generator.skin_dict['Units'].get(
                                               'display_rainrate', self.rainR)
        if disp_rainR in available_units:
            self.disp_rainR = disp_rainR

        # We can at least make sure the format overrides are integers
        try:
            self.disp_p_f = int(self.generator.skin_dict['Units'].get(
                                               'format_pressure', self.p_f))
        except ValueError as e:
            self.disp_p_f = self.p_f
            logdbg("Invalid integer given for format_pressure : %s" % e)
        try:
            self.disp_m_f = int(self.generator.skin_dict['Units'].get(
                                               'format_rain', self.m_f))
        except ValueError as e:
            self.disp_m_f = self.m_f
            logdbg("Invalid integer given for format_rain : %s" % e)

        try:
            self.disp_rr_f = int(self.generator.skin_dict['Units'].get(
                                               'format_rainrate', self.rr_f))
        except ValueError as e:
            self.disp_rr_f = self.rr_f
            logdbg("Invalid integer given for format_rainrate : %s" % e)

        def js_bool(_i):
            # shamelessly ripped of from weeutils.to_bool and adjusted to
            # return all lowercase. This ensures Config.js.tmpl accepts the
            # values without complaining. It's javascipt rules over there.
            # In this instance we need eg:- 'false', not 'False'!
            try:
                if _i.lower() in ['true', 'yes', 'y']:
                    return 'true'
                elif _i.lower() in ['false', 'no', 'n']:
                    return 'false'
                else:
                    loginf("Invalid value: \"%s\" in [ChartVisible] section"
                           "of Mesowx/skin.conf using 'false' instead" % _i)
                    return 'false'
            except AttributeError as e:
                loginf("AttributeError as %s" % e)

        chart_visible = self.generator.skin_dict.get('ChartVisible', {})
        for _k, _i in chart_visible.items():
            if "outtemp_sw" in _k:
                # one chart has to be enabled for highcharts to start
                # properly. This is the annointed one, a completely arbitary
                # choice except that it should always have data.
                # self.out_bool = js_bool(_i)
                self.out_bool = 'true'
            elif "intemp_sw" in _k:
                self.int_bool = js_bool(_i)
            elif "dewpoint_sw" in _k:
                self.dp_bool = js_bool(_i)
            elif "heatindex_sw" in _k:
                self.hi_bool = js_bool(_i)
            elif "windchill_sw" in _k:
                self.wc_bool = js_bool(_i)
            elif "barometer_sw" in _k:
                self.bar_bool = js_bool(_i)
            elif "windspeed_sw" in _k:
                self.ws_bool = js_bool(_i)
            elif "winddir_sw" in _k:
                self.wd_bool = js_bool(_i)
            elif "windgust_sw" in _k:
                self.wg_bool = js_bool(_i)
            elif "windgustdir_sw" in _k:
                self.wgd_bool = js_bool(_i)
            elif "dayrain_sw" in _k:
                self.drn_bool = js_bool(_i)
            elif "rain_sw" in _k:
                self.rn_bool = js_bool(_i)
            elif "rainrate_sw" in _k:
                self.rnr_bool = js_bool(_i)
            elif "outhumidity_sw" in _k:
                self.outh_bool = js_bool(_i)
            elif "inhumidity_sw" in _k:
                self.inh_bool = js_bool(_i)

        # mesowx console sections, additional areas on the mesowx console
        self.console_intemp = weeutil.weeutil.to_bool(self.generator.skin_dict[
                             'Extras'].get('console_intemp', 'false'))
        self.console_inhum = weeutil.weeutil.to_bool(self.generator.skin_dict[
                             'Extras'].get('console_inhumidity', 'false'))

        # Davis weather station specific value.
        self.davis_dayrain = weeutil.weeutil.to_bool(self.generator.skin_dict[
                             'Extras'].get('davis_dayrain', 'false'))
        # loginf("davis_dayrain is %s" % self.davis_dayrain)

        # language keys for chart labels
        # set up with english defaults
        self.chart_atemp = 'Temperature'
        self.chart_press = 'Barometer'
        self.chart_awind = 'Wind'
        self.chart_windd = 'Wind Dir'
        self.chart_humid = 'Humidity'
        self.chart_arain = 'Rain'
        self.chart_rainr = 'Rain Rate'
        # or overwrite with skin.conf values
        try:
            chart_labels = self.generator.skin_dict['Language'].get(
                                                            'ChartLabels', {})
            for _k, _i in chart_labels.items():
                if "chart_atemp" in _k:
                    self.chart_atemp = _i
                elif "chart_press" in _k:
                    self.chart_press = _i
                elif "chart_awind" in _k:
                    self.chart_awind = _i
                elif "chart_windd" in _k:
                    self.chart_windd = _i
                elif "chart_humid" in _k:
                    self.chart_humid = _i
                elif "chart_arain" in _k:
                    self.chart_arain = _i
                elif "chart_rainr" in _k:
                    self.chart_rainr = _i
        except:
            # not an error as we should be able to continue regardless
            logdbg("No language section, using default chart labels")

        # language keys for chart legend labels
        # set up with english defaults
        self.legend_outtemp = 'Out Temp'
        self.legend_dewp = 'Dewpoint'
        self.legend_arain = 'Rain'
        self.legend_rainr = 'Rain Rate'
        self.legend_raint = 'Rain Today'
        self.legend_winds = 'Wind Speed'
        self.legend_windd = 'Wind Direction'
        self.legend_windgu = 'Wind Gust'
        self.legend_windgd = 'Wind Gust Direction'
        self.legend_ohumid = 'Out Humidity'
        self.legend_pressb = 'Barometric Pressure'
        self.legend_windc = 'Wind Chill'
        self.legend_heati = 'Heat Index'
        self.legend_intemp = 'In Temp'
        self.legend_ihumid = 'In Humidity'
        # or overwrite with skin.conf values
        try:
            legend_labels = self.generator.skin_dict['Language'].get(
                                                            'LegendLabels', {})
            for _k, _i in legend_labels.items():
                if "legend_outtemp" in _k:
                    self.legend_outtemp = _i
                elif "legend_dewp" in _k:
                    self.legend_dewp = _i
                elif "legend_arain" in _k:
                    self.legend_arain = _i
                elif "legend_rainr" in _k:
                    self.legend_rainr = _i
                elif "legend_raint" in _k:
                    self.legend_raint = _i
                elif "legend_winds" in _k:
                    self.legend_winds = _i
                elif "legend_windd" in _k:
                    self.legend_windd = _i
                elif "legend_windgd" in _k:
                    self.legend_windgd = _i
                elif "legend_windgu" in _k:
                    self.legend_windgu = _i
                elif "legend_ohumid" in _k:
                    self.legend_ohumid = _i
                elif "legend_pressb" in _k:
                    self.legend_pressb = _i
                elif "legend_windc" in _k:
                    self.legend_windc = _i
                elif "legend_heati" in _k:
                    self.legend_heati = _i
                elif "legend_intemp" in _k:
                    self.legend_intemp = _i
                elif "legend_ihumid" in _k:
                    self.legend_ihumid = _i
        except:
            # not an error as we should be able to continue regardless
            logdbg("No language section, using default legend values")

        # language keys for index.html labels
        # set up with english defaults

        self.index_feels = 'feels like'
        self.index_otemp = 'outside temperature'
        self.index_itemp = 'inside temperature'
        self.index_dewp = 'dewpoint'
        self.index_awind = 'wind'
        self.index_ohumid = 'outside humidity'
        self.index_ihumid = 'inside humidity'
        self.index_press = 'pressure'
        self.index_arain = 'rain'
        self.index_realt = 'Real-time'
        self.index_sphours = 'hours'
        self.index_archive = 'Archive'
        # or overwrite with skin.conf values
        try:
            index_labels = self.generator.skin_dict['Language'].get(
                                                            'IndexLabels', {})
            for _k, _i in index_labels.items():
                if "index_feels" in _k:
                    self.index_feels = _i
                if "index_otemp" in _k:
                    self.index_otemp = _i
                if "index_itemp" in _k:
                    self.index_itemp = _i
                elif "index_dewp" in _k:
                    self.index_dewp = _i
                elif "index_awind" in _k:
                    self.index_awind = _i
                elif "index_ohumid" in _k:
                    self.index_ohumid = _i
                elif "index_ihumid" in _k:
                    self.index_ihumid = _i
                elif "index_press" in _k:
                    self.index_press = _i
                elif "index_arain" in _k:
                    self.index_arain = _i
                elif "index_realt" in _k:
                    self.index_realt = _i
                elif "index_sphours" in _k:
                    self.index_sphours = _i
                elif "index_archive" in _k:
                    self.index_archive = _i
        except:
            # not an error as we should be able to continue regardless
            logdbg("No language section, using default index.html values")

        # the wee_extension install process will create 2 unique keys and add
        # them to weewx.conf. Change them if you like but the psuedo warranty
        # goes with it :)
        self.arch_sec_key = self.sync_config.get('archive_security_key', "")
        self.raw_sec_key = self.sync_config.get('raw_security_key', "")

        """
        loginf("Fillers wh=%s : wu=%s : wp=%s : wd=%s " %
               (self.weewx_host,
                self.weewx_user,
                self.weewx_pass,
                self.weewx_data,
                ))
        loginf("mh=%s : mu=%s : mp=%s : mdb=%s :"
               "md=%s : mas=%s : mrs=%s" %
               (self.mesowx_host,
                self.mesowx_user,
                self.mesowx_pass,
                self.mesowx_dbase,
                self.mesowx_data,
                self.arch_sec_key,
                self.raw_sec_key,
                ))
        """
