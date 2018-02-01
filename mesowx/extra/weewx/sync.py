import Queue
import json
import syslog
import weewx
import socket
import urllib3
import threading
import itertools
import weeutil.weeutil
import weewx.engine


class SyncError(Exception):
    """Raised when a non-fatal synchronization error occurs. May succeed if retried."""


class FatalSyncError(Exception):
    """Raised when a fatal synchronization error occurs. Likely to occur again if retried."""


class AbortAndExit(Exception):
    """Raised when it's time to shut down the thread."""

#
# Filename: sync_lh7.py
# 2015-11-02 Modified sync.py (of mesowx 0.4.0) by Luc Heijst to work with weewx version 3.2.1 and later
# 2015-11-02 version 3 Don't use this version; works only with a MySQL database
# 2015-11-02 version 4 Works with both local weewx MySQL and sqlite databases
# 2016-03-01 version 5 Don't use this version; it has a lockup in backfill when the remote routines can't be found
# 2016-03-02 version 6 Works only with a local weewx MySQL database; no fatal messages when problems occur
#                      with the remote computer
# 2016-03-02 version 7 Changed timeouts from 90 s to 300 s; polished the code some more
#
# archive sync:
#   premise
#     data always sent in sequential order
#     failures aren't tolerated (will either fail or retry forever on all errors)
#   thread
#     watches queue and publishes data to remote server in order
#     IO failures result in a retry after X seconds, indefintely
#   back_fill
#     on start up
#       query remote server for most recent date
#       sync all records since date to queue
#     new archive packets
#       date of packet added to queue (have to make sure it's not already sent by the back_fill)
# raw sync:
#   premise
#     data sent immediately from packet (not db)
#     failures are tolerated (errors will skip)
#   thread
#     watches queue and publishes data to remote server
#     IO failures are logged and skipped
#
# error handling
#   3 general categories of errors:
#     1) can't communicate w/server (IO)
#     2) configuration/logical error (400 status response)
#     3) unknown/unexpected error (500 status)
#   all errors are possible when initially setting it up, but only #1 and possibly #3 should occur 
#     after that, thus always fail for #2, and retry for #1 and #3
#   
# TODO rename to meso sync as this is not general purpose


class SyncService(weewx.engine.StdService):

    def __init__(self, engine, config_dict):
        super(SyncService, self).__init__(engine, config_dict)
        self.engine = engine
        self.config_dict = config_dict
        self.sync_config = self.config_dict['RemoteSync']
        # used to signal the thread to exit, see shutDown()
        self.exit_event = threading.Event()
        self.archive_queue = Queue.Queue()
        self.raw_queue = Queue.Queue()
        self.backfill_queue = Queue.Queue()
        # keeps track of the dateTime of the last loop packet seen in order to prevent sending 
        # packets with the same dateTime value, see new_loop_packet() for more info
        self.lastLoopDateTime = 0
        # using a http connection pool to potentially save some overhead and server
        # burden if keep alive is enabled, maxsize is set to 2 since there are two threads
        # using the pool. Note that keep alive will need to be longer than the loop interval
        # to be effective (which may not make sense for longer intervals)
        self.http_pool = urllib3.connectionpool.connection_from_url(self.sync_config['remote_server_url'], maxsize=2)
        # Last dateTime synced records on webserver
        global last_datetime_synced
        last_datetime_synced = None
        self.debug_count = 0
        self.max_times_to_print = 5

        # if a archive_entity_id is configured, then bind & create the thead to sync archive records
        if 'archive_entity_id' in self.sync_config:
            # start backfill thread
            self.backfill_thread = BackfillSyncThread(self.backfill_queue, self.engine, self.config_dict,
                                                      self.exit_event, self.http_pool, **self.sync_config)
            self.backfill_thread.start()
            syslog.syslog(syslog.LOG_DEBUG, "sync backfill: will backfill archive records")
            # start archive theread
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
            self.archive_thread = ArchiveSyncThread(self.archive_queue, self.engine, self.config_dict,
                                                    self.exit_event, self.http_pool, **self.sync_config)
            self.archive_thread.start()
            syslog.syslog(syslog.LOG_DEBUG, "sync archive: will sync archive records")

        else:
            syslog.syslog(syslog.LOG_DEBUG, "sync archive: won't sync records (archive_entity_id not configured)")

        # if a raw_entity_id is configured, then bind & create the thead to sync raw records
        if 'raw_entity_id' in self.sync_config:
            # start raw thread
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
            self.raw_thread = RawSyncThread(self.raw_queue, self.engine, self.config_dict,
                                            self.exit_event, self.http_pool, **self.sync_config)
            self.raw_thread.start()
            syslog.syslog(syslog.LOG_DEBUG, "sync raw: will sync raw records")
        else:
            syslog.syslog(syslog.LOG_DEBUG, "sync raw: won't sync raw records (raw_entity_id not configured)")

    def new_archive_record(self, event):
        if self.archive_thread.isAlive():
            self.archive_queue.put(event.record)
            syslog.syslog(syslog.LOG_DEBUG, "sync archive: put record in queue %s" %
                          weeutil.weeutil.timestamp_to_string(event.record['dateTime']))
        else:
            syslog.syslog(syslog.LOG_ERR, "sync archive: not synching archive record (%d) due to previous error." %
                          event.record['dateTime'])

    def new_loop_packet(self, event):
        if self.raw_thread.isAlive():
            packet = event.packet
            # It's possible for records with duplicate dateTimes - this occurs when an archive packet
            # is processed since the LOOP packets are queued up and then returned immediately when
            # looping resumes, coupled with the fact that for Vantage Pro consoles the dateTime value is
            # added by weewx. So, for database storage, skip the duplicates until we get a new one to 
            # avoid a duplicate key error
            date_time = packet['dateTime']
            if date_time != self.lastLoopDateTime:
                self.raw_queue.put(packet)
                self.lastLoopDateTime = date_time
                self.debug_count += 1
                if self.debug_count <= self.max_times_to_print:
                    syslog.syslog(syslog.LOG_DEBUG, "sync raw: put loop record in queue %s" %
                                  (weeutil.weeutil.timestamp_to_string(event.packet['dateTime'])))
                if self.debug_count == self.max_times_to_print:
                    syslog.syslog(syslog.LOG_DEBUG, "sync raw: print message above only the first %s times" %
                                  self.max_times_to_print)
        # not going to spam the logs by logging each time we don't sync one due to frequency

    def shutDown(self):
        """Shut down the sync threads"""
        # signal the threads to shutdown
        self.exit_event.set()
        self.archive_queue.put(None)
        self.raw_queue.put(None)
        global last_datetime_synced
        last_datetime_synced = -1
        # join the threads
        self._join_thread(self.archive_thread)
        self._join_thread(self.raw_thread)
        self._join_thread(self.backfill_thread)
        # close the http pool
        self.http_pool.close()

    @staticmethod
    def _join_thread(thread):
        if thread is not None and thread.isAlive():
            # Wait up to 20 seconds for the thread to exit:
            thread.join(20.0)
            if thread.isAlive():
                syslog.syslog(syslog.LOG_ERR, "sync: Unable to shut down syncing thread: %s" % thread.name)
            else:
                syslog.syslog(syslog.LOG_DEBUG, "sync: Shut down syncing thread: %s" % thread.name)


class SyncThread(threading.Thread):

    def __init__(self, queue, engine, config_dict, exit_event, http_pool, thread_name="SyncThread", **sync_params):
        threading.Thread.__init__(self, name=thread_name)
        self.setDaemon(True)
        self.queue = queue
        self.engine = engine
        self.config_dict = config_dict
        self.exit_event = exit_event
        self.http_pool = http_pool
        # the base url of the remote server to sync to
        self.remote_server_url = sync_params['remote_server_url']
        # the path on the remote server of the data update api (usually won't ever change this)
        self.update_url_path = sync_params.get('server_update_path', "updateData.php")
        # the url that will be used to update data to on the remote server
        self.update_url = self.remote_server_url + self.update_url_path
        # the entity_id and security_key must be set by sub-classes
        self.entity_id = None
        self.security_key = None
        # time to wait in seconds before retrying http requests (default: 1 minute)
        self.http_retry_interval = float(sync_params.get('archive_http_retry_interval', 60.0))
        # number of times to retry http requests before giving up for a while (default: 1)
        self.http_max_tries = int(sync_params.get('archive_http_max_tries', 1))
        # time to wait in seconds before retrying after a failure (default: 5 minutes)
        self.failure_retry_interval = float(sync_params.get('archive_failure_retry_interval', 300.0))

    def run(self):
        try:
            self._run()
        except AbortAndExit:
            syslog.syslog(syslog.LOG_DEBUG, "sync: thread shutting down")
            return
        except FatalSyncError, e:
            syslog.syslog(syslog.LOG_ERR, "sync: fatal syncronization error")
            syslog.syslog(syslog.LOG_ERR, "   ****  Reason: %s" % (e,))
            return
        except Exception, e:
            syslog.syslog(syslog.LOG_ERR, "sync: unexpected error: %s" % (e,))
            weeutil.weeutil.log_traceback("   ****  ")
            syslog.syslog(syslog.LOG_ERR, "   ****  Thread terminating.")
            raise

    def _run(self):
        pass

    def post_records(self, records):
        datajson = json.dumps(records)
        postdata = {'entity_id': self.entity_id, 'data': datajson, 'security_key': self.security_key}
        http_response = self.make_http_request(self.update_url, postdata)
        if http_response is None:
            return -1
        else:
            return http_response.status

    def make_http_request(self, url, postdata):
        retry = False
        try:
            for count in range(self.http_max_tries):
                try:
                    response = self.http_pool.request('POST', url, postdata)
                    if response.status == 200:
                        return response
                    else:
                        # from here must either set retry=True or raise a FatalSyncError
                        if response.status != 404:
                            syslog.syslog(syslog.LOG_ERR, "sync: http request FAILED (%s %s): %s" %
                                          (response.status, response.reason, response.data))
                        if response.status >= 500:
                            # Don't retry if Duplicate entry error
                            if response.data.find('Duplicate entry') >= 0:
                                # continue
                                return response
                            else:
                                retry = True
                        else:
                            message = "sync: Request to %s FAILED, server returned %s status with reason '%s'." % \
                                      (url, response.status, response.reason)
                            # invalid credentials
                            if response.status == 403:
                                message += " Do your entity security keys match?"
                            # page not found
                            if response.status == 404:
                                message += " Is the url correct?"
                            # bad request (likely an invalid setup)
                            if response.status == 400:
                                message += " Check your entity configuration."
                            syslog.syslog(syslog.LOG_ERR, "%s" % message)
                except (socket.error, urllib3.exceptions.MaxRetryError), e:
                    syslog.syslog(syslog.LOG_ERR, "%s" % e)
                    syslog.syslog(syslog.LOG_ERR, "sync: FAILED http request attempt #%d to %s" % (count+1, url))
                    retry = True
                if retry and count+1 < self.http_max_tries:
                    # wait a bit before retrying, ensuring that we exit if signaled
                    syslog.syslog(syslog.LOG_DEBUG, "sync: FAILED, retrying again in %s seconds, count=%d" %
                                  (self.http_retry_interval, count+1))
                    self._wait(self.http_retry_interval)
            else:
                raise SyncError
        except SyncError:
            syslog.syslog(syslog.LOG_ERR, "sync: FAILED to invoke %s after %d tries, retrying in %s seconds" %
                          (url, self.http_max_tries, self.failure_retry_interval))
            self._wait(self.failure_retry_interval)

    def _wait(self, duration):
        if duration is not None:
            if self.exit_event.wait(duration):
                syslog.syslog(syslog.LOG_DEBUG, "sync: exit event signaled, aborting")
                raise AbortAndExit


class RawSyncThread(SyncThread):

    def __init__(self, queue, engine, config_dict, exit_event, http_pool, **sync_params):
        SyncThread.__init__(self, queue, engine, config_dict, exit_event, http_pool, "RawSyncThread", **sync_params)
        # the entity id to sync to on the remote server
        self.entity_id = sync_params['raw_entity_id']
        # the security key that will be sent along with updates to the entity
        self.security_key = sync_params['raw_security_key']
        self.debug_count = 0
        self.max_times_to_print = 5

    def _run(self):
        self.sync_queued_records()

    def sync_queued_records(self):
        syslog.syslog(syslog.LOG_DEBUG, "sync raw: waiting for new records")
        while True:
            try:
                # XXX always empty the queue - send as a batch
                # XXX option to always send in a batch, wait for X records before sending
                raw_record = self.queue.get()
                # a value of None is a signal to exit
                if raw_record is None:
                    syslog.syslog(syslog.LOG_DEBUG, "sync raw: exit event signaled, exiting queue loop")
                    raise AbortAndExit
                post_status = self.post_records(raw_record)
                if post_status == 200:
                    self.debug_count += 1
                    if self.debug_count <= self.max_times_to_print:
                        syslog.syslog(syslog.LOG_DEBUG, "sync raw: send record OK %s" %
                                      weeutil.weeutil.timestamp_to_string(raw_record['dateTime']))
                    if self.debug_count == self.max_times_to_print:
                        syslog.syslog(syslog.LOG_DEBUG, "sync raw: print message above only the first %s times" %
                                      self.max_times_to_print)
                else:
                    self.debug_count = 0  # reset good packet counter
                    syslog.syslog(syslog.LOG_ERR, "sync raw: FAILED to send record %s" %
                                  weeutil.weeutil.timestamp_to_string(raw_record['dateTime']))

            except SyncError, e:
                syslog.syslog(syslog.LOG_ERR, "sync raw: unable to sync record, skipping")
                syslog.syslog(syslog.LOG_ERR, "   ****  Reason: %s" % (e,))
            finally:
                # mark the queue item as done whether it succeeded or not
                self.queue.task_done()


class ArchiveSyncThread(SyncThread):

    # has a queue used by the service to add new archive records as they arrive
    # run
    #    query for latest remote date
    #    send data since that date
    #    then load data from queue
    def __init__(self, queue, engine, config_dict, exit_event, http_pool, **sync_params):
        SyncThread.__init__(self, queue, engine, config_dict, exit_event, http_pool, "ArchiveSyncThread", **sync_params)
        # the entity id to sync to on the remote server
        self.entity_id = sync_params['archive_entity_id']
        # the security key that will be sent along with updates to the entity
        self.security_key = sync_params['archive_security_key']

    def _run(self):
        self.sync_queued_records()

    def sync_queued_records(self):
        global last_datetime_synced
        syslog.syslog(syslog.LOG_DEBUG, "sync archive: waiting for new records")
        while True:
            try:
                archive_record = self.queue.get()
                # a value of None is a signal to exit
                if archive_record is None:
                    syslog.syslog(syslog.LOG_DEBUG, "sync archive: exit event signaled, exiting queue loop")
                    raise AbortAndExit
                if last_datetime_synced is not None:
                    if last_datetime_synced > 0:
                        syslog.syslog(syslog.LOG_DEBUG, "sync archive: get record %s; last synced %s" %
                                      (weeutil.weeutil.timestamp_to_string(archive_record['dateTime']),
                                       weeutil.weeutil.timestamp_to_string(last_datetime_synced)))
                        if last_datetime_synced is not None and (archive_record['dateTime'] <= last_datetime_synced):
                            syslog.syslog(syslog.LOG_DEBUG, "sync archive: skip already synced record %s" %
                                          weeutil.weeutil.timestamp_to_string(archive_record['dateTime']))
                        else:
                            post_status = self.post_records(archive_record)
                            if post_status == 200:
                                syslog.syslog(syslog.LOG_DEBUG, "sync archive: send record OK %s" %
                                              weeutil.weeutil.timestamp_to_string(archive_record['dateTime']))
                                last_datetime_synced = archive_record['dateTime']
                            else:
                                # Force a fetch_latest_remote_datetime call to resync archive records again
                                last_datetime_synced = None
                                syslog.syslog(syslog.LOG_DEBUG, "sync archive: FAILED to send record %s" %
                                              weeutil.weeutil.timestamp_to_string(archive_record['dateTime']))
            finally:
                # mark the queue item as done whether it succeeded or not
                self.queue.task_done()


class BackfillSyncThread(SyncThread):

    # has a queue used by the service to add new archive records as they arrive
    # run
    #    query for latest remote date
    #    send data since that date
    #    then load data from queue
    def __init__(self, queue, engine, config_dict, exit_event, http_pool, **sync_params):
        SyncThread.__init__(self, queue, engine, config_dict,
                            exit_event, http_pool, "BackfillSyncThread", **sync_params)
        self.config_dict = config_dict
        self.sync_config = self.config_dict['RemoteSync']
        # the base url of the remote server to sync to
        self.remote_server_url = sync_params['remote_server_url']
        # the path on the remote server of the data query api (usually won't ever change this)
        self.server_data_path = sync_params.get('server_data_path', "data.php")
        # the url that will be used to query for the latest dateTime on the remote server
        self.latest_url = self.remote_server_url + self.server_data_path
        # the entity id to sync to on the remote server
        self.entity_id = sync_params['archive_entity_id']
        # the security key that will be sent along with updates to the entity
        self.security_key = sync_params['archive_security_key']
        # time to wait in seconds before retrying http requests (default: 1 minute)
        self.http_retry_interval = float(sync_params.get('archive_http_retry_interval', 60.0))
        # number of times to retry http requests before giving up for a while (default: 1)
        self.http_max_tries = int(sync_params.get('archive_http_max_tries', 1))
        # time to wait in seconds before retrying after a failure (default: 5 minutes)
        self.failure_retry_interval = float(sync_params.get('archive_failure_retry_interval', 300.0))
        # the maximum number of reords to back_fill (defualt: no limit)
        self.backfill_limit = int(sync_params.get('archive_backfill_limit', 0))
        self.batch_size = int(sync_params.get('archive_batch_size', 300))
        # the number of seconds to wait between sending batches (default .5 seconds)
        self.batch_send_interval = float(sync_params.get('archive_batch_send_interval', 0.5))
        self.engine = engine
        # Open default database
        self.dbm = self.engine.db_binder.get_manager()

    def _run(self):
        self.back_fill()

    def back_fill(self):
        try:
            global last_datetime_synced
            num_to_sync = 0
            if last_datetime_synced == 1:
                syslog.syslog(syslog.LOG_DEBUG, "sync backfill: exit event signaled, exiting queue loop")
                raise AbortAndExit
            while last_datetime_synced is None:
                last_datetime_synced = self.fetch_latest_remote_datetime()
                syslog.syslog(syslog.LOG_DEBUG, "sync backfill: fetch_latest_remote_datetime returned %s" %
                              last_datetime_synced)
            if last_datetime_synced is not None:
                if last_datetime_synced == 0:
                    num_to_sync = self.dbm.getSql("select count(*) from %s" % self.dbm.table_name)[0]
                elif last_datetime_synced > 0:
                    num_to_sync = self.dbm.getSql("select count(*) from %s where dateTime > ?" %
                                                  self.dbm.table_name, (last_datetime_synced,))[0]
                syslog.syslog(syslog.LOG_DEBUG,
                              "sync backfill: %d records to sync since last synced record with dateTime: %s" %
                              (num_to_sync, weeutil.weeutil.timestamp_to_string(last_datetime_synced)))
                if num_to_sync > 0:
                    if self.backfill_limit is not None and self.backfill_limit != 0 \
                            and num_to_sync[0] > self.backfill_limit:
                        syslog.syslog(syslog.LOG_ERR, "sync backfill: Too many to sync: %d exeeds the limit of %d" %
                                      (num_to_sync, self.backfill_limit))
                        raise FatalSyncError
                    syslog.syslog(syslog.LOG_DEBUG, "sync backfill: back_filling %d records" % num_to_sync)
                    self.sync_all_since_datetime(last_datetime_synced)
                    syslog.syslog(syslog.LOG_DEBUG, "sync backfill: done back_filling %d records" % num_to_sync)
        except Exception, e:
            syslog.syslog(syslog.LOG_ERR, "sync: back_fill unexpected error: %s" % (e,))

    def sync_all_since_datetime(self, datetime):
        global last_datetime_synced
        try:
            if datetime is None:
                query = self.dbm.genSql("select * from %s order by dateTime asc" % self.dbm.table_name)
            else:
                query = self.dbm.genSql("select * from %s where dateTime > ? order by dateTime asc" %
                                        self.dbm.table_name, (datetime,))
            total_sent = 0
            while True:
                batch = []
                for row in itertools.islice(query, self.batch_size):
                    datadict = dict(zip(self.dbm.sqlkeys, row))
                    batch.append(datadict)
                if len(batch) > 0:
                    post_status = self.post_records(batch)
                    if post_status == 200:
                        total_sent += len(batch)
                        last_datetime_synced = batch[len(batch)-1]['dateTime']
                        # XXX add start/end datetime to log message
                        syslog.syslog(syslog.LOG_DEBUG, "sync backfill: back_filled OK %d records; timestamp last record: "
                                      "%s" % (total_sent, weeutil.weeutil.timestamp_to_string(last_datetime_synced)))
                    else:
                        syslog.syslog(syslog.LOG_ERR, "sync backfill: FAILED to back_fill batch; timestamp last record: "
                                      "%s" % weeutil.weeutil.timestamp_to_string(last_datetime_synced))

                else:
                    # no more to send
                    break
                # breath a bit so as not to don't bombard the remote server
                # also back_filling could take some time, so make sure an exit event hasn't been signaled
                self._wait(self.batch_send_interval)
        except Exception, e:
            syslog.syslog(syslog.LOG_ERR, "sync: sync_all_since_datetime error: %s" % (e,))
            # wait a bit before retrying, ensuring that we exit if signaled
            syslog.syslog(syslog.LOG_DEBUG, "sync backfill: FAILED, retrying again in %s seconds" %
                          (self.http_retry_interval,))
            self._wait(self.http_retry_interval)

    def fetch_latest_remote_datetime(self):
        syslog.syslog(syslog.LOG_DEBUG, "sync backfill: requesting latest dateTime from %s" % self.latest_url)
        # http://wxdev.ruskers.com/data.php?entity_id=weewx_archive&data=dateTime&order=desc&limit=1
        postdata = {'entity_id': self.entity_id, 'data': 'dateTime', 'order': 'desc', 'limit': 1}
        http_response = self.make_http_request(self.latest_url, postdata)
        if http_response is None:
            datetime = None  # no answer from remote server
        else:
            response_json = http_response.data
            response = json.loads(response_json)
            if len(response) is 0:
                datetime = 0
            else:
                datetime = json.loads(response_json)[0][0]
        return datetime

    def post_records(self, records):
        datajson = json.dumps(records)
        postdata = {'entity_id': self.entity_id, 'data': datajson, 'security_key': self.security_key}
        http_response = self.make_http_request(self.update_url, postdata)
        if http_response is None:
            return -1
        else:
            return http_response.status

    def make_http_request(self, url, postdata):
        try:
            for count in range(self.http_max_tries):
                try:
                    response = self.http_pool.request('POST', url, postdata)
                    if response.status == 200:
                        return response
                    else:
                        # from here must either set retry=True or raise a FatalSyncError
                        if response.status != 404:
                            syslog.syslog(syslog.LOG_ERR, "sync backfill: http request FAILED (%s %s): %s" %
                                          (response.status, response.reason, response.data))
                        if response.status >= 500:
                            # Don't retry if Duplicate entry error
                            if response.data.find('Duplicate entry') >= 0:
                                # continue
                                return response
                            else:
                                retry = True
                        else:
                            message = \
                                "sync backfill: Request to %s FAILED, server returned %s status with reason '%s'" % \
                                (url, response.status, response.reason)
                            # invalid credentials
                            if response.status == 403:
                                message += " Do your entity security keys match?"
                            # page not found
                            if response.status == 404:
                                message += " Is the url correct?"
                            # bad request (likely an invalid setup)
                            if response.status == 400:
                                message += " Check your entity configuration."
                            syslog.syslog(syslog.LOG_ERR, "%s" % message)
                            raise SyncError
                except (socket.error, urllib3.exceptions.MaxRetryError), e:
                    syslog.syslog(syslog.LOG_ERR, "%s" % e)
                    syslog.syslog(syslog.LOG_ERR, "sync backfill: FAILED http request attempt #%d to %s" %
                                  (count+1, url))
                    retry = True
                if retry and count+1 < self.http_max_tries:
                    # wait a bit before retrying, ensuring that we exit if signaled
                    syslog.syslog(syslog.LOG_DEBUG, "sync backfill: FAILED, retrying again in %s seconds" %
                                  (self.http_retry_interval,))
                    self._wait(self.http_retry_interval)
                elif retry and count+1 >= self.http_max_tries:
                    # now wait failure_retry_interval
                    syslog.syslog(syslog.LOG_DEBUG, "sync backfill: FAILED, retrying again in %s seconds" %
                                  self.failure_retry_interval)
                    self._wait(self.failure_retry_interval)
            else:
                raise SyncError
        except SyncError:
            syslog.syslog(syslog.LOG_ERR, "sync backfill: FAILED to invoke %s after %d tries, retrying in %s seconds" %
                          (url, self.http_max_tries, self.failure_retry_interval))
            self._wait(self.failure_retry_interval)

    def _wait(self, duration):
        if duration is not None:
            if self.exit_event.wait(duration):
                syslog.syslog(syslog.LOG_DEBUG, "sync backfill: exit event signaled, aborting")
                raise AbortAndExit
