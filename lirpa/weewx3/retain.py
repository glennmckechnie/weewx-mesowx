import syslog
import weewx
import weeutil.weeutil
from weewx.wxengine import StdService

class RetainLoopValues(StdService):
    """Service retains previous loop packet values updating any value that isn't None from new
    packets. It then replaces the original packet with a new packet that contains all of the values; 
    the original unmodified packet will be stored on the event in a property named 'originalPacket'."""

    def __init__(self, engine, config_dict):
        super(RetainLoopValues, self).__init__(engine, config_dict)
        self.bind(weewx.NEW_LOOP_PACKET, self.newLoopPacket)
        self.retainedLoopValues = {}
        self.excludeFields = set([])
        if 'RetainLoopValues' in config_dict:
            if 'exclude_fields' in config_dict['RetainLoopValues']:
                self.excludeFields = set(weeutil.weeutil.option_as_list(config_dict['RetainLoopValues'].get('exclude_fields', [])))
                syslog.syslog(syslog.LOG_INFO, "RetainLoopValues: excluding fields: %s" % (self.excludeFields,))

    def newLoopPacket(self, event):
        event.originalPacket = event.packet
        # replace the values in the retained packet if they have a value other than None or the field is listed in excludeFields
        self.retainedLoopValues.update( dict((k,v) for k,v in event.packet.iteritems() if (v is not None or k in self.excludeFields)) )
        # if the new packet doesn't contain one of the excludeFields then remove it from the retainedLoopValues
        for k in self.excludeFields - set(event.packet.keys()):
            if k in self.retainedLoopValues:
                self.retainedLoopValues.pop(k)
        event.packet = self.retainedLoopValues.copy()
