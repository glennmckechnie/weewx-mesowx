<?php

// if display_errors = on, errors will result in a 200 status, so setting the 
// status to 500 ahead of time, then resetting to 200 on success
// see: https://bugs.php.net/bug.php?id=50921
header('HTTP/1.0 500 Internal Server Error');

/**
 * RESTful Query Params:
 *   - start
 *   - end
 *      - seconds since epoch
 *         - e.g. "X:datetime"
 *      - seconds ago
 *         - e.g. "Y:ago"
 *   - group
 *      - can group by a period of time or an automatic period to return a specific 
 *        number of groups
 *      - if grouping by more than one group, you must specify the time unit of the 
 *        returned group value, either milliseconds or seconds (ms/s) since epoch
 *      - by desired number of groups (approximate)
 *          - e.g. "200:groups:s"
 *      - by time period
 *          - TODO add support for milliseconds
 *          - seconds, e.g. "84600:seconds:ms"
 *          - days, e.g. "7:days:ms"
 *          - months, e.g. "1:months:ms"
 *          - year, e.g. "1:years:s"
 *   - data
 *      - fieldId:agg:unit:decimals (agg, unit, and decimals are optional)
 *      - i.e. "outTemp,outDew:mean::1,bar::mb"
 *   - order
 *      - sort (by datetime only for now), "asc"/"desc"
 *   - limit
 *      - the number of records to return
 *
 */
require_once("include/HttpUtil.class.php");
require_once("include/JsonConfig.class.php");
require_once("include/AggregateParameterParser.class.php");
require_once("include/AggregateQuery.class.php");
require_once("include/PDOConnectionFactory.class.php");
require_once 'include/TableEntity.class.php';

// always try to prevent caching of this page
HttpUtil::sendPreventCacheHeaders();

$config = JsonConfig::getInstance();

$parser = new AggregateParameterParser($_REQUEST, $config);

$spec = $parser->parse();

// XXX for now assuming all entities are tables
$entity = new TableEntity($spec->entityId, $config);

$db_config = $config['dataSource'][$spec->entityConfig['dataSource']];
$db = PDOConnectionFactory::openConnection($db_config);

// TODO need to support calculated fields (i.e. actual rainRate)
$query = new AggregateQuery($spec, $db);

header( "X-Meso-Query: ". str_replace("\n", " ", $query->sql) );

$_start = microtime(true);

try {
    $data = $db->query( $query->sql );
} catch(PDOException $e) { // XXX a quick and dirty fix for automatically creating the table if it doesn't yet exist
    // table doesn't exist eror code: 42S02
    if($e->getCode() == '42S02') {
        // attempt to create the table and retry
        $entity->createTable();
        $data = $db->query( $query->sql );
    } else {
        // re-throw all other errors encountered
        throw $e;
    }
}

header( "X-Meso-Query-Time: ". (microtime(true) - $_start) );

$data->setFetchMode(PDO::FETCH_NUM);

// success! reset to 200 status
header('HTTP/1.0 200 OK');

echo '[';

$i = 1;
while( $row = $data->fetch() ) {
    if( $i != 1 ) echo ",";
    $row = array_map( function($column) {
        return $column === NULL ? "null" : $column;
    }, $row);
    echo "[" . join( ",", $row ) . "]";
    $i++;
}

echo ']';

?>
