import Queue

import json
import syslog
import weewx
import socket
import urllib3
import threading
import itertools
import weeutil.weeutil
from weewx.wxengine import StdService

class SyncError(Exception):
    """Raised when a non-fatal synchronization error occurs. May succeed if retried."""

class FatalSyncError(Exception):
    """Raised when a fatal synchronization error occurs. Likely to occur again if retried."""

class AbortAndExit(Exception):
    """Raised when it's time to shut down the thread."""

#
# archive sync:
#   premise
#     data always sent in sequential order
#     failures aren't tolerated (will either fail or retry forever on all errors)
#   thread
#     watches queue and publishes data to remote server in order
#     IO failures result in a retry after X seconds, indefintely
#   backfill
#     on start up
#       query remote server for most recent date
#       sync all records since date to queue
#     new archive packets
#       date of packet added to queue (have to make sure it's not already sent by the backfill)
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
class SyncService(StdService):

    def __init__(self, engine, config_dict):
        super(SyncService, self).__init__(engine, config_dict)

        self.config_dict = config_dict
        self.sync_config = self.config_dict['RemoteSync']

        # used to signal the thread to exit, see shutDown()
        self.exit_event = threading.Event()

        self.archive_queue = Queue.Queue()
        self.raw_queue = Queue.Queue()

        # keeps track of the dateTime of the last loop packet seen in order to prevent sending 
        # packets with the same dateTime value, see newLoopPacket() for more info
        self.lastLoopDateTime = 0;

        # using a http connection pool to potentially save some overhead and server
        # burden if keep alive is enabled, maxsize is set to 2 since there are two threads
        # using the pool. Note that keep alive will need to be longer than the loop interval 
        # to be effective (which may not make sense for longer intervals)
        self.http_pool = urllib3.connectionpool.connection_from_url(self.sync_config['remote_server_url'], maxsize=2)

        # if a archive_entity_id is configured, then bind & create the thead to sync archive records
        if 'archive_entity_id' in self.sync_config:
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.newArchiveRecord)
            self.archive_db_dict = self.config_dict['Databases'][self.config_dict['StdArchive']['archive_database']]
            self.archive_thread = ArchiveSyncThread(self.archive_db_dict, self.archive_queue, self.exit_event, self.http_pool, **self.sync_config)
            self.archive_thread.start()
            syslog.syslog(syslog.LOG_INFO, "sync: will sync archive records")
        else:
            syslog.syslog(syslog.LOG_INFO, "sync: won't sync archive records (archive_entity_id not configured)")

        # if a raw_entity_id is configured, then bind & create the thead to sync raw records
        if 'raw_entity_id' in self.sync_config:
            self.bind(weewx.NEW_LOOP_PACKET, self.newLoopPacket)
            self.raw_thread = RawSyncThread(self.raw_queue, self.exit_event, self.http_pool, **self.sync_config)
            self.raw_thread.start()
            syslog.syslog(syslog.LOG_INFO, "sync: will sync raw records")
        else:
            syslog.syslog(syslog.LOG_INFO, "sync: won't sync raw records (raw_entity_id not configured)")

    def newArchiveRecord(self, event):
        if self.archive_thread.isAlive():
            self.archive_queue.put(event.record['dateTime'])
        else:
            syslog.syslog(syslog.LOG_NOTICE, "sync: not synching archive record (%d) due to previous error." % event.record['dateTime'])

    def newLoopPacket(self, event):
        if self.raw_thread.isAlive():
            packet = event.packet;
            # It's possible for records with duplicate dateTimes - this occurs when an archive packet
            # is processed since the LOOP packets are queued up and then returned immediately when
            # looping resumes, coupled with the fact that for Vantage Pro consoles the dateTime value is
            # added by weewx. So, for database storage, skip the duplicates until we get a new one to 
            # avoid a duplicate key error
            dateTime = packet['dateTime']
            if dateTime != self.lastLoopDateTime:
                self.raw_queue.put(packet)
                self.lastLoopDateTime = dateTime
        # not going to spam the logs by logging each time we don't sync one due to frequency

    def shutDown(self):
        """Shut down the sync threads"""
        # signal the threads to shutdown
        self.exit_event.set()
        self.archive_queue.put(None)
        self.raw_queue.put(None)
        # join the threads
        self._joinThread(self.archive_thread)
        self._joinThread(self.raw_thread)
        # close the http pool
        self.http_pool.close()

    def _joinThread(self, thread):
        if thread is not None and thread.isAlive():
            # Wait up to 20 seconds for the thread to exit:
            self.thread.join(20.0)
            if self.thread.isAlive():
                syslog.syslog(syslog.LOG_ERR, "sync: Unable to shut down syncing thread: %s" % thread.name)
            else:
                syslog.syslog(syslog.LOG_DEBUG, "sync: Shut down syncing thread: %s" % thread.name)



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
        except AbortAndExit, e:
            syslog.syslog(syslog.LOG_DEBUG, "sync: thread shutting down")
            return
        except FatalSyncError, e:
            syslog.syslog(syslog.LOG_ERR, "sync: fatal syncronization error")
            syslog.syslog(syslog.LOG_ERR, "   ****  Reason: %s" % (e,))
            return
        except Exception, e:
            syslog.syslog(syslog.LOG_CRIT, "sync: unexpected error: %s" % (e,))
            weeutil.weeutil.log_traceback("   ****  ")
            syslog.syslog(syslog.LOG_CRIT, "   ****  Thread terminating.")
            raise

    def _run(self):
        pass

    def postRecords(self, records):
        datajson = json.dumps(records)
        postdata = {'entity_id': self.entity_id, 'data': datajson, 'security_key': self.security_key}
        #syslog.syslog(syslog.LOG_DEBUG, "sync: post body: %s" % postdata)

        self.makeHttpRequest(self.update_url, postdata)

    def makeHttpRequest(self, url, postdata):
        syslog.syslog(syslog.LOG_DEBUG, "sync: postdata size %d" % (len(postdata)))
        for count in range(self.http_max_tries):
            retry = False
            try:
                response = self.http_pool.request('POST', url, postdata)
                if response.status == 200:
                    return response
                else:
                    # from here must either set retry=True or raise a FatalSyncError
                    syslog.syslog(syslog.LOG_ERR, "sync: http request failed (%s %s): %s" % (response.status, response.reason, response.data))
                    syslog.syslog(syslog.LOG_ERR, "sync: postdata: %s" % (postdata,))
                    if response.status >= 500:
                        message = "Request to %s failed, server returned %s status with reason '%s'." % (url, response.status, response.reason)
                        syslog.syslog(syslog.LOG_ERR, "sync: %s" % (message,))
                        retry = True
                    else:
                        message = "Request to %s failed, server returned %s status with reason '%s'." % (url, response.status, response.reason)
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
                syslog.syslog(syslog.LOG_ERR, "sync: retrying again in %s seconds" % (self.http_retry_interval,))
                self._wait(self.http_retry_interval)
        else:
            raise SyncError, "Failed to invoke %s after %d tries" % (url, self.http_max_tries)

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

    def _run(self):
        self.syncQueuedRecords()

    def syncQueuedRecords(self):
        syslog.syslog(syslog.LOG_INFO, "rawsync: waiting for new records")
        while True:
            try:
                # XXX always empty the queue - send as a batch
                # XXX option to always send in a batch, wait for X records before sending
                raw_record = self.queue.get()
                # a value of None is a signal to exit
                if raw_record is None:
                    syslog.syslog(syslog.LOG_DEBUG, "rawsync: exit event signaled, exiting queue loop")
                    raise AbortAndExit
                self.postRecords(raw_record)
            except SyncError, e:
                syslog.syslog(syslog.LOG_ERR, "rawsync: unable to sync record, skipping")
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
    def __init__(self, archive_db_dict, queue, exit_event, http_pool, **sync_params):
        SyncThread.__init__(self, queue, exit_event, http_pool, "ArchiveSyncThread", **sync_params)
        self.archive_db_dict = archive_db_dict

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
        # the maximum number of reords to backfill (defualt: no limit)
        self.backfill_limit = int(sync_params.get('archive_backfill_limit', 0))
        # the max number of records to send in a request (default: 200)
        self.batch_size = int(sync_params.get('archive_batch_size', 200))
        # the number of seconds to wait between sending batches (default .5 seconds)
        self.batch_send_interval = float(sync_params.get('archive_batch_send_interval', 0.5))

        # the url that will be used to query for the latest dateTime on the remote server
        self.latest_url = self.remote_server_url + self.server_data_path
        # the datetime of the most recently synced archive record, this is used to prevent potentially re-sendind
        # queued records that a backfill already sent (the queue is still populated during this process)
        self.last_datetime_synced = None

    def _run(self):
        with weewx.archive.Archive.open(self.archive_db_dict) as self.archive:
            while True:
                try:
                    self.backFill()
                    self.syncQueuedRecords()
                except SyncError, e:
                    syslog.syslog(syslog.LOG_ERR, "archivesync: synchronization failed, starting over in %s seconds" % self.failure_retry_interval)
                    syslog.syslog(syslog.LOG_ERR, "   ****  Reason: %s" % (e,))
                    self._wait(self.failure_retry_interval)

    def backFill(self):
        latest_datetime = self.fetchLatestRemoteDateTime()
        if latest_datetime is None:
            num_to_sync = self.archive.getSql("select count(*) from archive")[0]
        else:
            num_to_sync = self.archive.getSql("select count(*) from archive where dateTime > ?", (latest_datetime,))[0]
        syslog.syslog(syslog.LOG_INFO, "archivesync: %d records to sync since last synced record wth dateTime: %s" % (num_to_sync, latest_datetime))
        if num_to_sync > 0:
            if self.backfill_limit is not None and self.backfill_limit != 0 and num_to_sync[0] > self.backfill_limit:
                raise FatalSyncError, "Too many to sync: %d exeeds the limit of %d" % (num_to_sync, self.backfill_limit)
            syslog.syslog(syslog.LOG_INFO, "archivesync: backfilling %d records" % num_to_sync)
            self.syncAllSinceDatetime(latest_datetime)
            syslog.syslog(syslog.LOG_INFO, "archivesync: done backfilling %d records" % num_to_sync)

    def syncAllSinceDatetime(self, datetime):
        if datetime is None:
            query = self.archive.genSql("select * from archive order by dateTime asc")
        else:
            query = self.archive.genSql("select * from archive where dateTime > ? order by dateTime asc", (datetime,))

        total_sent = 0
        while True:
            batch = []
            for row in itertools.islice(query, self.batch_size):
                datadict = dict(zip(self.archive.sqlkeys, row))
                batch.append(datadict)
                
            if len(batch) > 0:
                self.postRecords(batch)
                total_sent += len(batch)
                self.last_datetime_synced = batch[len(batch)-1]['dateTime']
                # XXX add start/end datetime to log message
                syslog.syslog(syslog.LOG_INFO, "archivesync: synchronized %d records to %s" % (total_sent, self.update_url))
            else:
                # no more to send
                break

            # breath a bit so as not to don't bombard the remote server
            # also backfilling could take some time, so make sure an exit event hasn't been signaled
            self._wait(self.batch_send_interval)

    def fetchLatestRemoteDateTime(self):
        syslog.syslog(syslog.LOG_DEBUG, "archivesync: requesting latest dateTime from %s" % (self.latest_url))
        # http://wxdev.ruskers.com/data.php?entity_id=weewx_archive&data=dateTime&order=desc&limit=1
        postdata = {'entity_id': self.entity_id, 'data': 'dateTime', 'order': 'desc', 'limit': 1}
        syslog.syslog(syslog.LOG_DEBUG, "archivesync: post body: %s" % postdata)

        http_response = self.makeHttpRequest(self.latest_url, postdata)
        response_json = http_response.data
        syslog.syslog(syslog.LOG_DEBUG, "sync: response json: %s" % response_json)
        response = json.loads(response_json)
        if len(response) is 0:
            datetime = None
        else:
            datetime = response[0][0]
        syslog.syslog(syslog.LOG_DEBUG, "archivesync: recieved latest dateTime: %s" % datetime)
        return datetime

    def syncQueuedRecords(self):
        syslog.syslog(syslog.LOG_INFO, "archivesync: waiting for new records")
        while True:
            try:
                record_datetime = self.queue.get()
                # a value of None is a signal to exit
                if record_datetime is None:
                    syslog.syslog(syslog.LOG_DEBUG, "archivesync: exit event signaled, exiting queue loop")
                    raise AbortAndExit
                if self.last_datetime_synced is not None and record_datetime <= self.last_datetime_synced:
                    syslog.syslog(syslog.LOG_DEBUG, "archivesync: skipping already synced record with dateTime %d" % record_datetime)
                else:
                    self.postArchiveRecord(record_datetime)
                    last_datetime_synced = record_datetime
            finally:
                # mark the queue item as done whether it succeeded or not
                self.queue.task_done()

    def postArchiveRecord(self, record_datetime):
        syslog.syslog(syslog.LOG_DEBUG, "archivesync: posting archive record %s" % record_datetime)

        # fetch the entire record
        archive_record = self.archive.getRecord(record_datetime)

        self.postRecords(archive_record)
        syslog.syslog(syslog.LOG_INFO, "archivesync: synchronized archive record %s to %s" % (record_datetime, self.update_url))
    
        


#===============================================================================
#                                 Testing
#===============================================================================

if __name__ == '__main__':
           
    import sys
    import configobj
    import weeutil
    from optparse import OptionParser
    import Queue
    
    def main():
        usage_string ="""Usage: 
        
        sync.py config_path [--today] [--last]
        
        Arguments:
        
          config_path: Path to weewx.conf
          
        Options:
        
            --today: Publish all of today's data
            
            --last: Just do the last archive record. [default]
          """
        parser = OptionParser(usage=usage_string)
        parser.add_option("-t", "--today", action="store_true", dest="do_today", help="Publish today\'s records")
        parser.add_option("-l", "--last", action="store_true", dest="do_last", help="Publish the last archive record only")
        (options, args) = parser.parse_args()
        
        if len(args) < 1:
            sys.stderr.write("Missing argument(s).\n")
            sys.stderr.write(parser.parse_args(["--help"]))
            exit()
            
        if options.do_today and options.do_last:
            sys.stderr.write("Choose --today or --last, not both\n")
            sys.stderr.write(parser.parse_args(["--help"]))
            exit()
    
        if not options.do_today and not options.do_last:
            options.do_last = True
            
        config_path = args[0]
        
        weewx.debug = 1
        
        try :
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            print "Unable to open configuration file ", config_path
            exit()
            
        archive_db_dict = config_dict['Databases'][config_dict['StdArchive']['archive_database']]
        with weewx.archive.Archive.open(archive_db_dict) as archive:
            stop_ts  = archive.lastGoodStamp()
            start_ts = weeutil.weeutil.startOfDay(stop_ts) if options.do_today else stop_ts
            publish(config_dict, archive, start_ts, stop_ts )

    def publish(config_dict, archive, start_ts, stop_ts):
        """Publishes records from start_ts to stop_ts. 
        Makes a useful test."""
        
        archive_db_dict = config_dict['Databases'][config_dict['StdArchive']['archive_database']]

        # Create the queue into which we'll put the timestamps of new data
        queue = Queue.Queue()
        exit_event = threading.Event()
        # Start up the thread:
        thread = ArchiveSyncThread(archive_db_dict, queue, exit_event)
        # only try once
        thread.http_max_tries = 1

        thread.start()

        queue.put(None)
        # Wait for exit:
        thread.join()
    
    main()
    
