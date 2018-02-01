import syslog
import time
import weeutil.weeutil
import weewx
import weewx.engine
import weewx.manager
from weewx.engine import StdService

VERSION = "0.4.1-lh"

#
# 2015-12-28 Modified by Luc Heijst to work with weewx version 3.3.1
#

if weewx.__version__ < "3":
    raise weewx.UnsupportedFeature("weewx 3 is required, found %s" % weewx.__version__)

schema = [
    ('dateTime', 'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
    ('usUnits', 'INTEGER NOT NULL'),
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
    ('rain', 'REAL'), # rain, was: dayRain
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

def get_default_binding_dict():
    return {'database': 'raw_mysql',
            'manager': 'weewx.manager.Manager',
            'table_name': 'raw',
            'schema': 'user.raw.schema'}

class RawService(StdService):

    def __init__(self, engine, config_dict):
        self.config_dict = config_dict
        super(RawService, self).__init__(engine, config_dict)
        syslog.syslog(syslog.LOG_INFO, "raw: service version is %s" % VERSION)

        d = config_dict.get('Raw', {})
        self.dataLimit = int(d.get('data_limit', 24))

        # get the database parameters we need to function
        self.binding = d.get('data_binding', 'raw_binding')
        self.dbm = self.engine.db_binder.get_manager(data_binding=self.binding, initialize=True)

        # be sure schema in database matches the schema we have
        dbcol = self.dbm.connection.columnsOf(self.dbm.table_name)
        dbm_dict = weewx.manager.get_manager_dict(
            config_dict['DataBindings'], config_dict['Databases'], self.binding)
        memcol = [x[0] for x in dbm_dict['schema']]
        if dbcol != memcol:
            raise Exception('raw: schema mismatch: %s != %s' % (dbcol, memcol))

        self.lastLoopDateTime = 0
        self.lastPrunedDateTime = 0
        self.bind(weewx.NEW_LOOP_PACKET, self.newLoopPacket)

    def prune_rawdata(self, dbm, ts, max_tries=3, retry_wait=10):
        """remove rawdata older than data_limit hours from the database"""
        sql = "delete from %s where dateTime < %d" % (dbm.table_name, ts)
        for count in range(max_tries):
            try:
                dbm.getSql(sql)
                syslog.syslog(syslog.LOG_INFO, 'raw: deleted rawdata prior to %s' % weeutil.weeutil.timestamp_to_string(ts))
                break
            except Exception, e:
                syslog.syslog(syslog.LOG_ERR, 'raw: prune failed (attempt %d of %d): %s' % ((count + 1), max_tries, e))
                syslog.syslog(syslog.LOG_INFO, 'raw: waiting %d seconds before retry' % retry_wait)
                time.sleep(retry_wait)
        else:
            raise Exception('raw: prune failed after %d attemps' % max_tries)

    def newLoopPacket(self, event):
        packet = event.packet
        prune_period = 300
        # It's possible for records with duplicate dateTimes - this occurs when an archive packet
        # is processed since the LOOP packets are queued up and then returned immediately when
        # looping resumes, coupled with the fact that for Vantage Pro consoles the dateTime value is
        # added by weewx. So, for database storage, skip the duplicates until we get a new one to
        # avoid a duplicate key error, but publish them all to redis regardless.
        dateTime = packet['dateTime']
        if dateTime != self.lastLoopDateTime:
            self.dbm.addRecord(packet)
            self.lastLoopDateTime = dateTime
        if dateTime > (self.lastPrunedDateTime + prune_period):
            if self.dataLimit is not None:
                ts = ((dateTime - (self.dataLimit * 3600)) / prune_period) * prune_period  # preset on 5-min boundary
                self.prune_rawdata(self.dbm, ts, 2, 5)
            self.lastPrunedDateTime = dateTime

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
