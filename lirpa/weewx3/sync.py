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
# 2015-11-02 Modified by Luc Heijst to work with weewx version 3.2.1
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
# 09-02-2018     supply a user agent string to satisfy hosting servers


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
        # keeps track of the dateTime of the last loop packet seen in order to prevent sending 
        # packets with the same dateTime value, see new_loop_packet() for more info
        self.lastLoopDateTime = 0
        # supply a user agent string to satisfy hosting servers
        self.u_agent= ({'User-Agent':'MesoWX-sync/0.10 (https://github.com/glennmckechnie/weewx-mesowx)'})
        # using a http connection pool to potentially save some overhead and server
        # burden if keep alive is enabled, maxsize is set to 2 since there are two threads
        # using the pool. Note that keep alive will need to be longer than the loop interval
        # to be effective (which may not make sense for longer intervals)
        self.http_pool = urllib3.connectionpool.connection_from_url(self.sync_config['remote_server_url'], maxsize=2, headers=self.u_agent)


        # the maximum number of reords to back_fill (defualt: no limit)
        self.backfill_limit = int(self.sync_config.get('archive_backfill_limit', 0))
        # the max number of records to send in a request (default: 200)
        self.batch_size = int(self.sync_config.get('archive_batch_size', 200))
        # the path on the remote server of the data update api (usually won't ever change this)
        self.update_url_path = self.sync_config.get('server_update_path', "updateData.php")
        # default number of times to retry http requests before giving up
        self.http_max_tries = 3
        # default time to wait in seconds before retrying http requests
        self.http_retry_interval = 0
        # the base url of the remote server to sync to
        self.remote_server_url = self.sync_config['remote_server_url']
        # the url that will be used to update data to on the remote server
        self.update_url = self.remote_server_url + self.update_url_path
        # the url that will be used to query for the latest dateTime on the remote server
        # the path on the remote server of the data query api (usually won't ever change this)
        self.server_data_path = self.sync_config.get('server_data_path', "data.php")
        self.latest_url = self.remote_server_url + self.server_data_path
        # the number of seconds to wait between sending batches (default .5 seconds)
        self.batch_send_interval = float(self.sync_config.get('archive_batch_send_interval', 0.5))
        # the entity id to sync to on the remote server
        self.entity_id = self.sync_config['archive_entity_id']
        # the security key that will be sent along with updates to the entity
        self.security_key = self.sync_config['archive_security_key']
        # Last dateTime synced records on webserver
        global last_datetime_synced
        last_datetime_synced = None
        # Open default database
        self.dbm = self.engine.db_binder.get_manager()

        # if a archive_entity_id is configured, then back-fill missed records and bind & create the thead to sync archive records
        if self.entity_id <> "":
            # back_fill missed records on webserver
            self.back_fill()
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
            self.archive_thread = ArchiveSyncThread(self.archive_queue, self.exit_event,
                                                    self.http_pool, **self.sync_config)
            self.archive_thread.start()
            syslog.syslog(syslog.LOG_DEBUG, "sync archive: will sync archive records")
        else:
            syslog.syslog(syslog.LOG_DEBUG, "sync archive: won't sync records (archive_entity_id not configured)")

        # if a raw_entity_id is configured, then bind & create the thead to sync raw records
        if 'raw_entity_id' in self.sync_config:
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
            self.raw_thread = RawSyncThread(self.raw_queue, self.exit_event, self.http_pool, **self.sync_config)
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
        # not going to spam the logs by logging each time we don't sync one due to frequency

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
                syslog.syslog(syslog.LOG_ERR, "sync: Unable to shut down syncing thread: %s" % thread.name)
            else:
                syslog.syslog(syslog.LOG_DEBUG, "sync: Shut down syncing thread: %s" % thread.name)

    def back_fill(self):
        global last_datetime_synced
        last_datetime_synced = self.fetch_latest_remote_datetime()
        if last_datetime_synced is None:
            num_to_sync = self.dbm.getSql("select count(*) from %s" % self.dbm.table_name)[0]
        else:
            num_to_sync = self.dbm.getSql("select count(*) from %s where dateTime > ?" %
                                          self.dbm.table_name, (last_datetime_synced,))[0]
        syslog.syslog(syslog.LOG_DEBUG, "sync archive: %d records to sync since last synced record with dateTime: %s"
                      % (num_to_sync, weeutil.weeutil.timestamp_to_string(last_datetime_synced)))
        if num_to_sync > 0:
                if self.backfill_limit is not None and self.backfill_limit != 0 \
                        and num_to_sync[0] > self.backfill_limit:
                    raise FatalSyncError, "sync archive: Too many to sync: %d exeeds the limit of %d" % \
                                          (num_to_sync, self.backfill_limit)
                syslog.syslog(syslog.LOG_DEBUG, "sync archive: back_filling %d records" % num_to_sync)
                self.sync_all_since_datetime(last_datetime_synced)
                syslog.syslog(syslog.LOG_DEBUG, "sync archive: done back_filling %d records" % num_to_sync)

    def sync_all_since_datetime(self, datetime):
        global last_datetime_synced
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
                self.post_records(batch)
                total_sent += len(batch)
                last_datetime_synced = batch[len(batch)-1]['dateTime']
                # XXX add start/end datetime to log message
                syslog.syslog(syslog.LOG_DEBUG, "sync archive: back_filled %d records; timestamp last record: %s" %
                              (total_sent, weeutil.weeutil.timestamp_to_string(last_datetime_synced)))
            else:
                # no more to send
                break
            # breath a bit so as not to don't bombard the remote server
            # also back_filling could take some time, so make sure an exit event hasn't been signaled
            self._wait(self.batch_send_interval)

    def fetch_latest_remote_datetime(self):
        syslog.syslog(syslog.LOG_DEBUG, "sync archive: requesting latest dateTime from %s" % self.latest_url)
        # the entity id to sync to on the remote server
        self.entity_id = self.sync_config['archive_entity_id']
        # the security key that will be sent along with updates to the entity
        self.security_key = self.sync_config['archive_security_key']
        # http://wxdev.ruskers.com/data.php?entity_id=weewx_archive&data=dateTime&order=desc&limit=1
        postdata = {'entity_id': self.entity_id, 'data': 'dateTime', 'order': 'desc', 'limit': 1}
        http_response = self.make_http_request(self.latest_url, postdata)
        response_json = http_response.data
        response = json.loads(response_json)
        if len(response) is 0:
            datetime = None
        else:
            datetime = response[0][0]
        return datetime

    def post_records(self, records):
        datajson = json.dumps(records)
        postdata = {'entity_id': self.entity_id, 'data': datajson, 'security_key': self.security_key}
        self.make_http_request(self.update_url, postdata)

    def make_http_request(self, url, postdata):
        for count in range(self.http_max_tries):
            try:
                response = self.http_pool.request('POST', url, postdata)
                if response.status == 200:
                    return response
                else:
                    # from here must either set retry=True or raise a FatalSyncError
                    syslog.syslog(syslog.LOG_ERR, "sync archive: http request failed (%s %s): %s" %
                                  (response.status, response.reason, response.data))
                    if response.status >= 500:
                        # Don't retry if Duplicate entry error
                        if response.data.find('Duplicate entry') >= 0:
                            # continue
                            return response
                        else:
                            retry = True
                    else:
                        message = "sync archive: Request to %s failed, server returned %s status with reason '%s'." % \
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
                        raise FatalSyncError, message
            except (socket.error, urllib3.exceptions.MaxRetryError), e:
                syslog.syslog(syslog.LOG_ERR, "sync: failed http request attempt #%d to %s" % (count+1, url))
                syslog.syslog(syslog.LOG_ERR, "   ****  Reason: %s" % (e,))
                retry = True
            if retry and count+1 < self.http_max_tries:
                # wait a bit before retrying, ensuring that we exit if signaled
                syslog.syslog(syslog.LOG_DEBUG, "sync: retrying again in %s seconds" % (self.http_retry_interval,))
                self._wait(self.http_retry_interval)
        else:
            raise SyncError, "sync archive: Failed to invoke %s after %d tries" % (url, self.http_max_tries)

    def _wait(self, duration):
        if duration is not None:
            if self.exit_event.wait(duration):
                syslog.syslog(syslog.LOG_DEBUG, "sync: exit event signaled, aborting")
                raise AbortAndExit


class SyncThread(threading.Thread):

    def __init__(self, queue, exit_event, http_pool, thread_name="SyncThread", **sync_params):
        threading.Thread.__init__(self, name=thread_name)
        self.setDaemon(True)
        self.queue = queue
        self.exit_event = exit_event
        self.http_pool = http_pool
        # the base url of the remote server to sync to
        self.remote_server_url = sync_params['remote_server_url']
        # the path on the remote server of the data update api (usually won't ever change this)
        self.update_url_path = sync_params.get('server_update_path', "updateData.php")
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
        self.make_http_request(self.update_url, postdata)

    def make_http_request(self, url, postdata):
        for count in range(self.http_max_tries):
            try:
                response = self.http_pool.request('POST', url, postdata)
                if response.status == 200:
                    return response
                else:
                    # from here must either set retry=True or raise a FatalSyncError
                    syslog.syslog(syslog.LOG_ERR, "sync: http request failed (%s %s): %s" %
                                  (response.status, response.reason, response.data))
                    if response.status >= 500:
                        # Don't retry if Duplicate entry error
                        if response.data.find('Duplicate entry') >= 0:
                            # continue
                            return response
                        else:
                            retry = True
                    else:
                        message = "sync: Request to %s failed, server returned %s status with reason '%s'." % \
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
                        raise FatalSyncError, message
            except (socket.error, urllib3.exceptions.MaxRetryError), e:
                syslog.syslog(syslog.LOG_ERR, "sync: failed http request attempt #%d to %s" % (count+1, url))
                syslog.syslog(syslog.LOG_ERR, "   ****  Reason: %s" % (e,))
                retry = True
            if retry and count+1 < self.http_max_tries:
                # wait a bit before retrying, ensuring that we exit if signaled
                syslog.syslog(syslog.LOG_DEBUG, "sync: retrying again in %s seconds" % (self.http_retry_interval,))
                self._wait(self.http_retry_interval)
        else:
            raise SyncError, "sync: Failed to invoke %s after %d tries" % (url, self.http_max_tries)

    def _wait(self, duration):
        if duration is not None:
            if self.exit_event.wait(duration):
                syslog.syslog(syslog.LOG_DEBUG, "sync: exit event signaled, aborting")
                raise AbortAndExit


class RawSyncThread(SyncThread):

    def __init__(self, queue, exit_event, http_pool, **sync_params):
        SyncThread.__init__(self, queue, exit_event, http_pool, "RawSyncThread", **sync_params)
        # the entity id to sync to on the remote server
        self.entity_id = sync_params['raw_entity_id']
        # the security key that will be sent along with updates to the entity
        self.security_key = sync_params['raw_security_key']
        # time to wait in seconds before retrying http requests
        self.http_retry_interval = float(sync_params.get('raw_http_retry_interval', self.http_retry_interval))
        # number of times to retry http requests (default: 1)
        self.http_max_tries = int(sync_params.get('raw_http_max_tries', 1))
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
                self.debug_count += 1
                if self.debug_count <= self.max_times_to_print:
                    syslog.syslog(syslog.LOG_DEBUG, "sync raw: send record %s" %
                                  (weeutil.weeutil.timestamp_to_string(raw_record['dateTime'])))
                if self.debug_count == self.max_times_to_print:
                    syslog.syslog(syslog.LOG_DEBUG, "sync raw: print message above only the first %s times" %
                                  self.max_times_to_print)
                self.post_records(raw_record)
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
    def __init__(self, queue, exit_event, http_pool, **sync_params):
        SyncThread.__init__(self, queue, exit_event, http_pool, "ArchiveSyncThread", **sync_params)

        # the path on the remote server of the data query api (usually won't ever change this)
        self.server_data_path = sync_params.get('server_data_path', "data.php")
        # the entity id to sync to on the remote server
        self.entity_id = sync_params['archive_entity_id']
        # the security key that will be sent along with updates to the entity
        self.security_key = sync_params['archive_security_key']
        # time to wait in seconds before retrying http requests (default: 1 minute)
        self.http_retry_interval = float(sync_params.get('archive_http_retry_interval', 60))
        # number of times to retry http requests before giving up for a while (default: 10)
        self.http_max_tries = int(sync_params.get('archive_http_max_tries', 10))
        # time to wait in seconds before retrying after a failure (defualt: 15 minutes)
        self.failure_retry_interval = float(sync_params.get('archive_failure_retry_interval', 900))
        # the url that will be used to query for the latest dateTime on the remote server
        self.latest_url = self.remote_server_url + self.server_data_path
        # the datetime of the most recently synced archive record, this is used to prevent potentially re-sendind
        # queued records that a back_fill already sent (the queue is still populated during this process)

    def _run(self):
        while True:
            try:
                self.sync_queued_records()
            except SyncError, e:
                syslog.syslog(syslog.LOG_ERR, "sync archive: synchronization failed, starting over in %s seconds" %
                              self.failure_retry_interval)
                syslog.syslog(syslog.LOG_ERR, "   ****  Reason: %s" % (e,))
                self._wait(self.failure_retry_interval)

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
                syslog.syslog(syslog.LOG_DEBUG, "sync archive: get record %s; last synced %s" %
                              (weeutil.weeutil.timestamp_to_string(archive_record['dateTime']),
                               weeutil.weeutil.timestamp_to_string(last_datetime_synced)))
                if last_datetime_synced is not None and (archive_record['dateTime'] <= last_datetime_synced):
                    syslog.syslog(syslog.LOG_DEBUG, "sync archive: skip already synced record %s" %
                                  weeutil.weeutil.timestamp_to_string(archive_record['dateTime']))
                else:
                    syslog.syslog(syslog.LOG_DEBUG, "sync archive: send record %s" %
                                  weeutil.weeutil.timestamp_to_string(archive_record['dateTime']))
                    self.post_records(archive_record)
            finally:
                # mark the queue item as done whether it succeeded or not
                self.queue.task_done()
