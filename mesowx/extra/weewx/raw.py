import json
import datetime
import syslog
import time
import weedb
import weewx
import weeutil.weeutil

from weewx.wxengine import StdService

class RawService(StdService):

    def __init__(self, engine, config_dict):
        super(RawService, self).__init__(engine, config_dict)
        self.dataLimit = int(config_dict['Raw']['data_limit'])
        self.setupRawDatabase(config_dict)
        self.lastLoopDateTime = 0;
        self.redisPublishEnabled = 0;
        if 'Push' in config_dict['Raw']:
            self.redisPublishEnabled = int(config_dict['Raw']['Push']['redis_enabled']) == 1
            self.redisChannel = config_dict['Raw']['Push']['redis_channel']
            self.redisConnect(config_dict)
        self.bind(weewx.NEW_LOOP_PACKET, self.newLoopPacket)

    def newLoopPacket(self, event):
        packet = event.packet;
        # It's possible for records with duplicate dateTimes - this occurs when an archive packet
        # is processed since the LOOP packets are queued up and then returned immediately when
        # looping resumes, coupled with the fact that for Vantage Pro consoles the dateTime value is
        # added by weewx. So, for database storage, skip the duplicates until we get a new one to 
        # avoid a duplicate key error, but publish them all to redis regardless.
        dateTime = packet['dateTime']
        if dateTime != self.lastLoopDateTime:
            self.rawData.addRecordAndTruncate(packet, self.dataLimit)
            self.lastLoopDateTime = dateTime
        self.redisPublish(packet)

    def jsonSerializeObject(self, obj):
        if isinstance(obj, datetime.time):
            return obj.isoformat()
        syslog.syslog(syslog.LOG_NOTICE, "Raw: defaulting json serialization of raw value of type '%s': %s" % (type(obj), obj))
        return None

    def redisPublish(self, packet):
        if self.redisPublishEnabled:
            rawWxData = json.dumps(packet, default=self.jsonSerializeObject)
            channel = self.redisChannel
            #syslog.syslog(syslog.LOG_DEBUG, "Raw: publishing raw packet to redis channel '%s': %s" % (channel, rawWxData))
            try:
                self.publisher.publish(channel, rawWxData)
            # connection problem isn't revealed until now (via ConnectionError)
            except redis.RedisError as e:
                # try again next time
                syslog.syslog(syslog.LOG_ERR, "Raw: unable to publish raw packet to redis channel. Reason: %s" % e)

    def setupRawDatabase(self, config_dict):
        raw_db = config_dict['Raw']['raw_database']
        self.rawData = RawData.open_with_create(config_dict['Databases'][raw_db], self.defaultRawSchema)
        syslog.syslog(syslog.LOG_INFO, "Raw: Using raw database: %s" % (raw_db,))

    def redisConnect(self, config_dict):
        try:
            global redis
            import redis
        except ImportError as e:
            syslog.syslog(syslog.LOG_ERR, "Raw: unable to import redis-py module. Is it installed? Reason: %s" % e)
            raise
        push_config = config_dict['Raw']['Push']
        host = push_config['redis_host']
        port = int(push_config['redis_port'])
        syslog.syslog(syslog.LOG_INFO, "Raw: Using redis server: %s:%s " % (host, port))
        self.publisher = redis.Redis(host=host, port=port, db=0)

    # schema based on wview history table 
    # TODO finalize
    defaultRawSchema = [('dateTime', 'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
        ('barometer', 'REAL'),
        #('pressure', 'REAL'),
        #('altimeter', 'REAL'),
        ('inTemp', 'REAL'),
        ('outTemp', 'REAL'),
        ('inHumidity', 'REAL'),
        ('outHumidity', 'REAL'),
        ('windSpeed', 'REAL'),
        ('windDir', 'REAL'),
        #('windGust', 'REAL'),
        #('windGustDir', 'REAL'),
        ('rainRate', 'REAL'),
        ('dayRain', 'REAL'), # rain
        ('dewpoint', 'REAL'),
        ('windchill', 'REAL'),
        ('heatindex', 'REAL'),
        #('rxCheckPercent', 'REAL'),
        ('dayET', 'REAL'), # ET
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
        ('consBatteryVoltage', 'REAL')]
        #('hail', 'REAL'),
        #('hailRate', 'REAL'),
        #('heatingTemp', 'REAL'),
        #('heatingVoltage', 'REAL'),
        #('supplyVoltage', 'REAL'),
        #('referenceVoltage', 'REAL'),
        #('windBatteryStatus', 'REAL'),
        #('rainBatteryStatus', 'REAL'),
        #('outTempBatteryStatus', 'REAL'),
        #('inTempBatteryStatus', 'REAL')i


class RawData(object):

    def __init__(self, connection):
        """Initialize an object of type RawData 
        
        If the database is uninitialized, an exception of type weewx.UninitializedDatabase
        will be raised. 
        
        connection: A weedb connection to the raw database.
        """
        self.connection = connection
        try:
            self.sqlkeys = self._getTypes()
        except weedb.OperationalError, e:
            self.close()
            raise weewx.UninitializedDatabase(e)

    @staticmethod
    def open(raw_db_dict):
        """Open a Raw database.
        
        An exception of type weedb.OperationalError will be raised if the
        database does not exist.
        
        An exception of type StandardError will be raised if the database
        exists, but has not been initialized.
        
        Returns:
        An instance of RawData."""
        connection = weedb.connect(raw_db_dict)
        return RawData(connection)

    @staticmethod
    def open_with_create(raw_db_dict, rawSchema):
        """Open a Raw database, initializing it if necessary.
        
        raw_db_dict: A database dictionary holding the information necessary
        to open the database.
        
        rawSchema: The schema to be used
        
        Returns: 
        An instance of RawData""" 

        try:
            rawData = RawData.open(raw_db_dict)
            # The database exists and has been initialized. Return it.
            return rawData
        except (weedb.OperationalError, weewx.UninitializedDatabase):
            pass
        
        # First try to create the database. If it already exists, an exception will
        # be thrown.
        try:
            weedb.create(raw_db_dict)
        except weedb.DatabaseExists:
            pass

        # List comprehension of the types, joined together with commas. Put
        # the SQL type in backquotes to avoid conflicts with reserved words
        _sqltypestr = ', '.join(["`%s` %s" % _type for _type in rawSchema])

        _connect = weedb.connect(raw_db_dict)
        try:
            with weedb.Transaction(_connect) as _cursor:
                _cursor.execute("CREATE TABLE raw (%s);" % _sqltypestr)
                
        except Exception, e:
            _connect.close()
            syslog.syslog(syslog.LOG_ERR, "raw: Unable to create database raw.")
            syslog.syslog(syslog.LOG_ERR, "****     %s" % (e,))
            raise

        syslog.syslog(syslog.LOG_NOTICE, "raw: created schema for database 'raw'")
        return RawData(_connect)

    def addRecordAndTruncate(self, record, data_limit):
        """Commit a single record to the raw data and truncate data that is outside the limit."""

        with weedb.Transaction(self.connection) as cursor:

            self._addRecord(cursor, record)
            self._truncateOldRecords(cursor, record, data_limit)

    def addRecord(self, record_obj):
        """Commit a single record or a collection of records to the raw data table.
        
        record_obj: Either a data record, or an iterable that can return data
        records. Each data record must look like a dictionary, where the keys
        are the SQL types and the values are the values to be stored in the
        database."""

        with weedb.Transaction(self.connection) as cursor:

            self._addRecord(cursor, record)

    def _addRecord(self, cursor, record_obj):
        
        # Determine if record_obj is just a single dictionary instance (in which
        # case it will have method 'keys'). If so, wrap it in something iterable
        # (a list):
        record_list = [record_obj] if hasattr(record_obj, 'keys') else record_obj

        for record in record_list:

            if record['dateTime'] is None:
                syslog.syslog(syslog.LOG_ERR, "Raw: raw record with null time encountered.")
                raise weewx.ViolatedPrecondition("Raw record with null time encountered.")

            # Only data types that appear in the database schema can be inserted.
            # To find them, form the intersection between the set of all record
            # keys and the set of all sql keys
            record_key_set = set(record.keys())
            insert_key_set = record_key_set.intersection(self.sqlkeys)
            # Convert to an ordered list:
            key_list = list(insert_key_set)
            # Get the values in the same order:
            value_list = [record[k] for k in key_list]
            
            # This will a string of sql types, separated by commas. Because
            # some of the weewx sql keys (notably 'interval') are reserved
            # words in MySQL, put them in backquotes.
            k_str = ','.join(["`%s`" % k for k in key_list])
            # This will be a string with the correct number of placeholder question marks:
            q_str = ','.join('?' * len(key_list))
            # Form the SQL insert statement:
            sql_insert_stmt = "INSERT INTO raw (%s) VALUES (%s)" % (k_str, q_str) 
            try:
                cursor.execute(sql_insert_stmt, value_list)
                syslog.syslog(syslog.LOG_DEBUG, "Raw: added raw record %s" % weeutil.weeutil.timestamp_to_string(record['dateTime']))
            except Exception, e:
                syslog.syslog(syslog.LOG_ERR, "Raw: unable to add raw record %s" % weeutil.weeutil.timestamp_to_string(record['dateTime']))
                syslog.syslog(syslog.LOG_ERR, " ****    Reason: %s" % e)

    def _truncateOldRecords(self, cursor, record, data_limit):

        # truncate the old data if enabled
        if data_limit > 0:
            sql_delete_stmt = "DELETE FROM raw WHERE dateTime < ?"
            truncate_to = int(record['dateTime']) - (data_limit * 3600)
            cursor.execute(sql_delete_stmt, (truncate_to,))
            syslog.syslog(syslog.LOG_DEBUG, "RawData: truncated raw records older than %s (%s hours)" % (weeutil.weeutil.timestamp_to_string(truncate_to), data_limit))

    def _getTypes(self):
        """Returns the types appearing in a raw database.
        
        Raises exception of type weedb.OperationalError if the 
        database has not been initialized."""
        
        # Get the columns in the table
        column_list = self.connection.columnsOf('raw')
        return column_list

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, etyp, einst, etb):
        self.close()    


##### LOOP packet data example #####

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
