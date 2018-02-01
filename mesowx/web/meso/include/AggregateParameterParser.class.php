<?php
require_once('AggregateQuerySpec.class.php');

class AggregateParameterParser {

    const ENTITY_ID_PARAM = "entity_id";
    const START_PARAM = "start";
    const END_PARAM = "end";
    const GROUP_PARAM = "group";
    const DATA_PARAM = "data";
    const ORDER_PARAM = "order";
    const LIMIT_PARAM = "limit";

    protected $get;
    protected $config;

    function __construct($get, $config) {
        $this->get = $get;
        $this->config = $config;
    }

    public function parse() {
        $entityId = $this->parseEntityId();
        $entityConfig = $this->getEntityConfig($entityId);

        $spec = new AggregateQuerySpec($entityId, $entityConfig);

        $spec->setStart($this->parseStart());
        $spec->setEnd($this->parseEnd());
        $spec->setGroup($this->parseGroup());
        $spec->setData($this->parseData());
        $spec->setOrder($this->parseOrder());
        $spec->setLimit($this->parseLimit());

        return $spec;
    }

    protected function parseEntityId() {
        $entityId = $this->getParam(self::ENTITY_ID_PARAM);

        if($entityId == NULL) {
            throw new Exception("Must specify a entity_id");
        }
        return $entityId;
    }

    protected function getEntityConfig($entityId) {

        // make sure it's in the config
        if(!array_key_exists($entityId, $this->config['entity'])) {
            throw new Exception("Entity with entity_id $entityId has no configuration.");
        }
        $entityConfig = $this->config['entity'][$entityId];

        return $entityConfig;
    }

    protected function parseStart() {
        $start = self::parseTime($this->getParam(self::START_PARAM));
        return self::processTime($start);
    }

    protected function parseEnd() {
        $end = self::parseTime($this->getParam(self::END_PARAM));
        return self::processTime($end);
    }

    protected static function processTime($param) {
        $time = NULL;
        if($param != NULL) {
            $value = $param->value;
            if(!self::isInteger($value)) {
                throw new Exception("Invaild time value: '$value'");
            }
            $type = self::defaultParam($param->type, DateType::datetime);
            if($type == DateType::datetime) {
                $time = (int) $value;
            } else if ($type == DateType::ago) {
                $time = time() - $value;
            } else {
                throw new Exception("Invalid time type: '$type'");
            }
        }
        return $time;
    }

    protected function parseGroup() {
        $group = NULL;
        $value = $this->getParam(self::GROUP_PARAM);
        if( $value != NULL ) {
            $parts = explode( ":", $value, 3 );
            $val = self::getPart(0, $parts);
            $type = self::getPart(1, $parts, GroupType::seconds);
            $unit = self::getPart(2, $parts);
            $group = new GroupParam($val, $type, $unit);
        }
        return $this->processGroup($group);
    }

    // TODO make static
    protected function processGroup($groupParam) {
        $group = NULL;
        if($groupParam != NULL) {
            $value = NULL;
            $type = $groupParam->type;
            if( $type == GroupType::seconds ) {
                // NULL means one group (i.e. aggregate with no group by)
                $value = self::defaultParam( $groupParam->value, NULL );
            } else if( $type == GroupType::groups ) {
                $value = self::defaultParam( $groupParam->value, 1 );
            } else {
                $value = self::defaultParam( $groupParam->value, 1 );
            }

            $group = new Group($value, $type, $groupParam->unit);
        }
        return $group;
    }

    protected function parseData() {
        $data = array();
        $value = $this->getParam(self::DATA_PARAM);
        if($value) {
            $fields = explode( ",", $value );
            foreach( $fields as $field ) {
                // skip empty ones
                if( trim($field) ) {
                    $data[] = self::parseDataField($field);
                }
            }
        }
        return $data;
    }

    protected static function parseDataField($value) {
        $parts = explode( ":", $value, 4 );

        $field = self::getPart(0, $parts);
        $agg = self::getPart(1, $parts, Agg::avg);
        $unit = self::getPart(2, $parts);
        $decimals = self::getPart(3, $parts);

        return new Data( $field, $agg, $unit, $decimals );
    }

    protected function parseOrder() {
        $order = $this->getParam(self::ORDER_PARAM, Order::asc);
        return $order;
    }

    protected function parseLimit() {
        $limit = $this->getParam(self::LIMIT_PARAM);
        return $limit;
    }

    protected static function parseTime($value) {
        if( !$value ) {
            return NULL;
        } else {
            $parts = explode( ":", $value, 2 );
            $val = self::getPart(0, $parts);
            $type = self::getPart(1, $parts);

            return new TimeParam( $val, $type );
        }
    }

    protected function getParam($name, $default=NULL) {
        $value = $default;
        if( array_key_exists($name, $this->get) ) {
            $value = $this->get[$name];
        }
        return self::trim($value);
    }

    protected static function defaultParam( $param, $default=NULL ) {
        if( $param == NULL ) {
            $param = $default;
        }
        return $param;
    }

    protected static function trim($value) {
        $value = trim($value);
        return $value == "" ? NULL : $value;
    }

    private static function getPart($key, $parts, $default=NULL) {
        $part = $default;
        if( array_key_exists($key, $parts) ) {
            $partValue = self::trim($parts[$key]);
            if(strlen($partValue) != 0) $part = $partValue;
        }
        return $part;
    }

    protected static function isInteger( $value ) {
        return preg_match("/^-?\d+$/", $value ) === 1;
    }

}

class Parameters {
    public $entityId;
    public $start;
    public $end;
    public $group;
    public $data;
    public $options;
    public $order;
    public $limit;
}

class TimeParam {
    public $value;
    public $type;

    function __construct($value, $type) {
        $this->value = $value;
        $this->type = $type;
    }
}

class DateType {
    const datetime = "datetime";
    const ago = "ago";
}

class GroupParam {
    public $value;
    public $type;
    public $unit;

    function __construct($value, $type, $unit) {
        $this->value = $value;
        $this->type = $type;
        $this->unit = $unit;
    }
}

class DataParam {
    public $field;
    public $agg;
    public $unit;
    public $decimals;

    function __construct($field, $agg, $unit, $decimals) {
        $this->field = $field;
        $this->agg = $agg;
        $this->unit = $unit;
        $this->decimals = $decimals;
    }
}

class OptionsParam {
}

?>
