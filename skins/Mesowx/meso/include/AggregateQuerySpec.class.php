<?php
require_once('Agg.class.php');

class AggregateQuerySpec {

    public $start;
    public $end;
    public $group;
    // TODO rename data -> fields
    public $data = array();
    public $order;
    public $limit;

    public $table;
    public $dateTimeColoumn;

    public $entityId;
    public $entityConfig;

    function __construct($entityId, $entityConfig) {
        $this->entityId = $entityId;
        $this->entityConfig = $entityConfig;

        $this->table = $this->entityConfig['tableName'];
        $this->dateTimeColumn = $this->getDateTimeColumn();
    }

    public function setStart($start) {
        if($start != NULL && !is_numeric($start)) {
            throw new Exception("Invaild start value: '$start'");
        }
        $this->start = $start;
        return $this;
    }

    public function setEnd($end) {
        if($end != NULL && !is_numeric($end)) {
            throw new Exception("Invaild end value: '$end'");
        }
        $this->end = $end;
        return $this;
    }

    public function setData($data) {
        if(!$data || !is_array($data)) {
            throw new Exception("Must specify at least one data field");
        }
        // validate each field
        foreach($data as $index => $field) {
            $this->validateField($field, $index);
        }
        $this->data = $data;
        return $this;
    }

    // validations based on the entity configuration
    private function validateField($field, $index) {
        // field
        $fieldName = $field->field;
        if(!array_key_exists($fieldName, $this->entityConfig['columns'])) {
            throw new Exception("Undefined field: '$fieldName' at index: '$index'");
        }
        $fieldConfig = $this->entityConfig['columns'][$fieldName];
        // unit
        $unit = $field->unit;
        if($unit != NULL ) {
            // no unit defined on column
            if(!array_key_exists('unit', $fieldConfig)) {
                throw new Exception("Can't convert field '$fieldName' to unit '$unit'. Field has no defined unit.");
            }
            $columnUnit = $fieldConfig['unit'];
            if($unit != $columnUnit && (!array_key_exists($columnUnit, UnitConvert::$FORMULA) 
                    || !array_key_exists($unit, UnitConvert::$FORMULA[$columnUnit]))) {
                throw new Exception("No converter found for unit '$columnUnit' to '$unit' for field '$fieldName'.");
            }
        }
    }

    public function setGroup(Group $group=NULL) {
        $this->group = $group;
        return $this;
    }

    public function setOrder($order) {
        if( $order != Order::asc && $order != Order::desc ) {
            throw new Exception("Invaild order value: '$order'");
        }
        $this->order = $order;
        return $this;
    }

    public function setLimit($limit) {
        if($limit != NULL) {
            if(!is_numeric($limit)) {
                throw new Exception("Invalid limit: $limit");
            }
            if($limit < 1) {
                throw new Exception("Limit must be >0: '$limit'" );
            }
        }
        $this->limit = (int) $limit;
        return $this;
    }

    public function isGrouped() {
        return $this->group != NULL;
    }

    // TODO replace this function with a call to TableEntity
    protected function getDateTimeColumn() {
        // XXX for now dateTime column must be the primary key
        $primaryKey = $this->entityConfig['constraints']['primaryKey'];
        if(!$primaryKey) {
            throw new Exception("Entity must define a primaryKey constraint");
        }
        if(!array_key_exists($primaryKey, $this->entityConfig['columns'])) {
            throw new Exception("Primary key column $primaryKey is undenfined");
        }
        return $primaryKey;
    }
}


class Data {
    public $field;
    public $agg;
    public $unit;
    public $decimals;

    private static $VALID_AGGS = array( Agg::avg, Agg::min, Agg::max, Agg::sum );

    function __construct( $field, $agg, $unit, $decimals ) {
        self::validate($field, $agg, $unit, $decimals);
        $this->field = $field;
        $this->agg = $agg;
        $this->unit = $unit;
        $this->decimals = $decimals;
    }

    private static function validate($field, $agg, $unit, $decimals) {
        if(!$field) {
            throw new Exception("Must specify a field ID");
        }
        if($agg != NULL) {
            if(!in_array($agg, self::$VALID_AGGS)) {
                throw new Exception("Invalid aggregation: '$agg' for field '$field'");
            }
        }
        // TODO make sure unit is defined
        if( $decimals !== NULL && (!is_numeric($decimals) || $decimals < 0)) {
            throw new Exception("Invalid decimals value: '$decimals' for field '$field'");
        }
    }
}

class Group {
    public $value;
    public $type;
    public $unit;

    private static $VALID_UNITS = array( Unit::ms, Unit::s );

    function __construct($value, $type, $unit) {
        self::validate($value, $type, $unit);
        $this->value = (int)$value;
        $this->type = $type;
        $this->unit = $unit;
    }

    public function isSingle() {
        return ($this->type == GroupType::seconds && 
            ($this->value == NULL || $this->value == 0) ||
            ($this->type == GroupType::groups &&
                $this->value < 2)); 
    }

    private static function validate($value, $type, $unit) {
        if( $type == GroupType::seconds ) {
            // NULL means one group (i.e. aggregate with no group by)
            if( $value != NULL ) {
                if( !is_numeric($value) ) {
                    throw new Exception("Invalid group value: '$value' for type '$type'" );
                }
                if( $value < 1 ) {
                    throw new Exception("Group value must be greater than zero: '$value' for type '$type'" );
                }
            }
        } else if( $type == GroupType::groups ) {
            if( !is_numeric($value) ) {
                throw new Exception("Invalid group value: '$value' for type '$type'" );
            }
            if( $value < 1 ) {
                throw new Exception("Group value must be greater than zero: '$value' for type '$type'" );
            }
        } else if( $type == GroupType::months || $type == GroupType::days || $type == GroupType::years ) {
            if( !is_numeric($value) ) {
                throw new Exception("Invalid group value: '$value' for type '$type'" );
            }
            if( $value < 1 ) {
                throw new Exception("Group value must be greater than zero: '$value' for type '$type'" );
            }
        } else {
            throw new Exception("Invalid group type: '$type'" );
        }
        if($unit != NULL && !in_array($unit, self::$VALID_UNITS)) {
            throw new Exception("Invalid grouping unit: '$unit'.");
        }
    }
}

class GroupType {
    const groups = "groups";
    const seconds = "seconds";
    const days = "days";
    const months = "months";
    const years = "years";
}

class Order {
    const asc = "asc";
    const desc = "desc";
}

?>
