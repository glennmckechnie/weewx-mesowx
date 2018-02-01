<?php
/*
API

Input:
    {
        entityId: 'weewx_raw',
        timeUnit: 'ms',
        start: , // period start time in ms (optinoal)
        end: , // period end time in ms (optinoal)
        data: [
            {
                fieldId: 'outTemp',
                unit: 'f',
                decimals: 1,
                stats: ['min', 'max']
            },
            {
                fieldId: 'windSpeed',
                stats: ['max'],
                // idea
                ancillaryFields: [{
                    fieldId: 'windDir',
                    unit: 'deg'
                }]
            }
        ]
    }

Output:
    {
        'outTemp': {
            min: [-12.8, 1389015300]
            max: [105.1, 1341693300]
        },
        'windSpeed': {
            max: [15, 1288100700, 270] // ancillary tacked on here in order?
        }
    }

*/

require_once 'include/HttpUtil.class.php';
require_once("include/JsonConfig.class.php");
require_once("include/PDOConnectionFactory.class.php");
require_once 'include/TableEntity.class.php';
require_once("include/Unit.class.php");

// always try to prevent caching of this page
HttpUtil::sendPreventCacheHeaders();

if($_SERVER['REQUEST_METHOD']!= 'POST') {
    HttpUtil::send405('Request method must be a POST');
    exit;
}

$params = json_decode(file_get_contents("php://input"));
if(!$params) {
    HttpUtil::send400("Invalid request JSON");
    exit;
}

if(!array_key_exists('entityId', $params)) {
    HttpUtil::send400('Must specify an entityId');
    exit;
}

$entity_id = $params->entityId;

$config = JsonConfig::getInstance();

$entity = new TableEntity($entity_id, $config);

$db = $entity->openConnection();

// create an array of the fieldIds
$fieldIds = array_map(function($field) {
    return $field->fieldId;
}, $params->data);

// create an index of the param data by fieldId
$fieldData = array();
array_walk($params->data, function($field, $index) use (&$fieldData) {
    $fieldData[$field->fieldId] = $field;
});

$dateTimeColumn = $entity->getPrimaryKeyColumn();
$dateTimeColumnQuoted = $db->quoteIdentifier($dateTimeColumn);
$columnConfigs = $entity->getColumnConfigs();
$dateTimeColumnUnit = $columnConfigs[$dateTimeColumn]['unit'];

$timeUnit = property_exists($params, 'timeUnit') ? $params->timeUnit : NULL;

$sql = "select $dateTimeColumnQuoted, ". implode(', ', $db->quoteIdentifiers($fieldIds)) ." from ". $db->quoteIdentifier($entity->getTable());

// apply the start / end where clause
$where = array();
$start = NULL;
$end = NULL;
if(property_exists($params, 'start') && $params->start) {
    $start = $params->start;
    // negative values means that it should be that many units in the past
    if($start < 0) {
        $start = time() + $start;
    }
}
if(property_exists($params, 'end') && $params->end) {
    $end = $params->end;
    // negative values means that it should be that many units in the past
    if($end < 0) {
        $end = time() + $end;
    }
}
if($start || $end) {
    if($start) {
        $startSql = ':start';
        if($timeUnit) {
            $startSql = UnitConvert::getSqlFormula($startSql, $timeUnit, $dateTimeColumnUnit);
        }
        $where[] = "$dateTimeColumnQuoted >= $startSql";
    }
    if($end) {
        $endSql = ':end';
        if($timeUnit) {
            $endSql = UnitConvert::getSqlFormula($endSql, $timeUnit, $dateTimeColumnUnit);
        }
        $where[] = "$dateTimeColumnQuoted <= $endSql";
    }
}
if(count($where) > 0) {
    $sql .= " where " . join(" and ", $where);
}


// execute the query
header( "X-Meso-Query: ". str_replace("\n", " ", $sql) . " (start: $start, end: $end)" );

$_start = microtime(true);

$stmt = $db->prepare( $sql );

if($start) $stmt->bindValue(':start', $start, PDO::PARAM_INT );
if($end) $stmt->bindValue(':end', $end, PDO::PARAM_INT );

$result = $stmt->execute();

// process the result
abstract class CompareTracker {
    public $value;
    public $dateTime;
    function __construct($initialValue=NULL) {
        $this->value = $initialValue;
    }
    protected abstract function compare( $newValue, $oldValue );
    public function test( $newValue, $newDateTime ) {
        if( $this->compare( $newValue, $this->value ) ) {
            $this->value = $newValue;
            $this->dateTime = $newDateTime;
        }
    }
    public abstract function getType();
}
class MaxTracker extends CompareTracker {
    function __construct() {
        parent::__construct(-INF); // minimum int value
    }
    protected function compare( $newValue, $oldValue ) {
        return $newValue > $oldValue;
    }
    public function getType() {
        return "max";
    }
}
class MinTracker extends CompareTracker {
    function __construct() {
        parent::__construct(INF);
    }
    protected function compare( $newValue, $oldValue ) {
        return $newValue < $oldValue;
    }
    public function getType() {
        return "min";
    }
}

// create trackers
$allTrackers = array();
foreach($params->data as $field) {
    $fieldTrackers = array();
    if(in_array('min', $field->stats)) {
        $fieldTrackers[] = new MinTracker();
    }
    if(in_array('max', $field->stats)) {
        $fieldTrackers[] = new MaxTracker();
    }
    $allTrackers[$field->fieldId] = $fieldTrackers;
}

// find the stats
while( $row = $stmt->fetch(PDO::FETCH_ASSOC) ) {
    foreach( $allTrackers as $key => $trackers ) {
        foreach( $trackers as $tracker ) {
            if( $row[$key] != null )
                $tracker->test($row[$key], $row[$dateTimeColumn]);
        }
    }
}

header( "X-Meso-Process-Time: ". (microtime(true) - $_start) );

// output
echo "{";
$addFieldSeparator = false;
foreach( $allTrackers as $fieldId => $trackers ) {
    if($addFieldSeparator) echo ",";
    echo "\"$fieldId\":{";
    $addStatSeparator = false;
    foreach($trackers as $tracker) {
        if($addStatSeparator) echo ",";
        $type = $tracker->getType();
        $value = $tracker->value;
        // convert to desired unit
        $field = $fieldData[$fieldId];
        if($field->unit) {
            $entityUnit = $columnConfigs[$fieldId]['unit'];
            if(!$entityUnit) {
                // XXX catch this before output and return bad request response
                throw new Exception("Can't convert fieldId $fieldId to unit $field->unit: entity has no unit defined");
            }
            $value = UnitConvert::convert($value, $entityUnit, $field->unit);
        }
        if(property_exists($field, 'decimals')) {
            $value = round($value, $field->decimals);
        }
        $dateTime = $tracker->dateTime;
        if($dateTime) {
            $dateTime = UnitConvert::convert($dateTime, $dateTimeColumnUnit, $timeUnit);
        } else {
            $dateTime = "null";
        }
        echo "\"$type\":[$value,$dateTime]";
        $addStatSeparator = true;
    }
    echo "}";
    $addFieldSeparator = true;
}
echo "}";

?>
